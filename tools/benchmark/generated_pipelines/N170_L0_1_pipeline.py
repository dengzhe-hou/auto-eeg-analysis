#!/usr/bin/env python3
"""
N170 face-selectivity effect from the ERP CORE N170 dataset.

Per subject:
    difference wave = ERP(face) - ERP(car)
    measure         = mean amplitude over {PO7, PO8, P7, P8} in 130-200 ms (uV)

Pipeline (standard ERP practice):
    read EEGLAB .set -> channel types / montage -> 0.1-30 Hz band-pass
    -> ICA-based ocular artifact correction (EOG-guided)
    -> average reference (30 scalp electrodes)
    -> downsample to 256 Hz
    -> epoch -200..500 ms, baseline -200..0 ms
    -> peak-to-peak artifact rejection (100 uV on EEG)
    -> per-condition average -> difference wave -> ROI/time-window mean

Standalone: python pipeline.py
"""

from __future__ import annotations

import json
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

import mne

mne.set_log_level("ERROR")

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
DATA_ROOT = Path("/home/hou/mne_data/erpcore-N170")
OUT_DIR = Path(
    "/tmp/claude-1137/-home-hou-Research-auto-eeg-analysis/"
    "b4a153ed-22fa-4b6a-ad04-d134656fecf4/scratchpad/gen_p3n170/N170_L0_1"
)
OUT_JSON = OUT_DIR / "result.json"

SUBJECTS = [f"sub-{i:03d}" for i in range(1, 21)]

TASK = "N170"
EOG_NAMES = ["HEOG_left", "HEOG_right", "VEOG_lower"]

# Condition definition from the BIDS events sidecar
FACE_CODES = range(1, 41)      # 1-40  stimulus: faces
CAR_CODES = range(41, 81)      # 41-80 stimulus: cars
# 101-180 scrambled (ignored), 201/202 responses (ignored)

EVENT_ID = {"face": 1, "car": 2}

# Preprocessing parameters
L_FREQ = 0.1                   # Hz, high-pass (ERP-safe, no low-freq distortion)
H_FREQ = 30.0                  # Hz, low-pass
FILTER_DESIGN = "firwin"
RESAMPLE_SFREQ = 256.0         # Hz, well above the 30 Hz low-pass

ICA_HPF = 1.0                  # Hz, high-pass used only for fitting ICA
ICA_N_COMPONENTS = 0.99        # explained variance
ICA_RANDOM_STATE = 97
ICA_MAX_ITER = 1000

REFERENCE = "average"          # average of the 30 scalp EEG electrodes

# Epoching / measurement parameters
TMIN, TMAX = -0.2, 0.5         # s
BASELINE = (-0.2, 0.0)         # s (pre-stimulus baseline)
REJECT = {"eeg": 100e-6}       # V, peak-to-peak within an epoch
FLAT = {"eeg": 0.1e-6}         # V, drop dead channels/epochs

ROI = ["PO7", "PO8", "P7", "P8"]
WIN_TMIN, WIN_TMAX = 0.130, 0.200   # s, N170 measurement window

MIN_TRIALS_PER_CONDITION = 10  # subject-level exclusion criterion
ROUND_DP = 3


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def canonicalize_channel_names(raw: mne.io.BaseRaw) -> dict:
    """Rename channels to the canonical 10-05 casing (e.g. FP1 -> Fp1)."""
    montage = mne.channels.make_standard_montage("standard_1005")
    canonical = {name.lower(): name for name in montage.ch_names}
    mapping = {
        ch: canonical[ch.lower()]
        for ch in raw.ch_names
        if ch.lower() in canonical and canonical[ch.lower()] != ch
    }
    if mapping:
        raw.rename_channels(mapping)
    return mapping


def load_raw(subject: str) -> tuple[mne.io.BaseRaw, list[str]]:
    """Load the EEGLAB recording, attach channel types + montage.

    Returns (raw, names_of_eog_channels_present).
    """
    set_path = DATA_ROOT / subject / "eeg" / f"{subject}_task-{TASK}_eeg.set"
    if not set_path.exists():
        raise FileNotFoundError(str(set_path))

    raw = mne.io.read_raw_eeglab(set_path, preload=True)

    # The three ocular leads are stored as EEG in the .set file.
    present_eog = [ch for ch in EOG_NAMES if ch in raw.ch_names]
    if present_eog:
        raw.set_channel_types({ch: "eog" for ch in present_eog})

    canonicalize_channel_names(raw)
    raw.set_montage("standard_1005", on_missing="ignore", match_case=False)
    return raw, present_eog


def build_events(subject: str, raw: mne.io.BaseRaw) -> np.ndarray:
    """Build an MNE events array (face=1, car=2) from the BIDS events.tsv."""
    tsv = DATA_ROOT / subject / "eeg" / f"{subject}_task-{TASK}_events.tsv"
    df = pd.read_csv(tsv, sep="\t")

    onset = pd.to_numeric(df["onset"], errors="coerce")
    value = pd.to_numeric(df["value"], errors="coerce")
    keep = onset.notna() & value.notna()
    onset, value = onset[keep].to_numpy(float), value[keep].to_numpy(int)

    codes = np.zeros_like(value)
    codes[np.isin(value, list(FACE_CODES))] = EVENT_ID["face"]
    codes[np.isin(value, list(CAR_CODES))] = EVENT_ID["car"]

    sel = codes > 0
    onset, codes = onset[sel], codes[sel]

    # Onsets are in seconds relative to the start of the recording.
    samples = raw.time_as_index(onset, use_rounding=True) + raw.first_samp

    # Keep only events with a complete epoch inside the recording.
    lo = int(round(abs(TMIN) * raw.info["sfreq"]))
    hi = int(round(TMAX * raw.info["sfreq"]))
    ok = (samples - lo >= raw.first_samp) & (samples + hi < raw.first_samp + raw.n_times)
    samples, codes = samples[ok], codes[ok]

    events = np.column_stack([samples, np.zeros_like(samples), codes]).astype(int)
    order = np.argsort(events[:, 0])
    return events[order]


def clean_ocular(raw: mne.io.BaseRaw, eog_names: list[str]) -> int:
    """EOG-guided ICA correction of blinks / horizontal eye movements.

    Returns the number of excluded components. Operates in place on `raw`.
    """
    if not eog_names:
        return 0

    # Fit on a 1 Hz high-passed, downsampled copy (standard ICA practice).
    raw_fit = raw.copy().filter(ICA_HPF, None, fir_design=FILTER_DESIGN, picks=["eeg", "eog"])
    if raw_fit.info["sfreq"] > RESAMPLE_SFREQ:
        raw_fit.resample(RESAMPLE_SFREQ)

    n_eeg = len(mne.pick_types(raw_fit.info, eeg=True, exclude="bads"))
    if n_eeg < 5:
        return 0

    ica = mne.preprocessing.ICA(
        n_components=ICA_N_COMPONENTS,
        method="infomax",
        fit_params=dict(extended=True),
        max_iter=ICA_MAX_ITER,
        random_state=ICA_RANDOM_STATE,
    )
    ica.fit(raw_fit, picks="eeg")

    bad_idx: list[int] = []
    for ch in eog_names:
        try:
            idx, _ = ica.find_bads_eog(raw_fit, ch_name=ch, threshold=3.0)
            bad_idx.extend(idx)
        except Exception:
            continue

    ica.exclude = sorted(set(bad_idx))
    if ica.exclude:
        ica.apply(raw)
    return len(ica.exclude)


def measure_subject(subject: str) -> dict:
    """Full single-subject pipeline. Returns a per-subject record."""
    raw, eog_names = load_raw(subject)

    # 1) Band-pass filter (EEG + EOG so the EOG stays usable for ICA detection).
    raw.filter(L_FREQ, H_FREQ, fir_design=FILTER_DESIGN, picks=["eeg", "eog"])

    # 2) Ocular artifact correction.
    n_ica_excluded = clean_ocular(raw, eog_names)

    # 3) Re-reference the 30 scalp electrodes to the common average.
    raw.set_eeg_reference(REFERENCE, projection=False)

    # 4) Downsample, then derive event samples at the new rate (avoids jitter).
    if raw.info["sfreq"] > RESAMPLE_SFREQ:
        raw.resample(RESAMPLE_SFREQ)
    events = build_events(subject, raw)

    n_face_all = int((events[:, 2] == EVENT_ID["face"]).sum())
    n_car_all = int((events[:, 2] == EVENT_ID["car"]).sum())
    if n_face_all == 0 or n_car_all == 0:
        raise RuntimeError(f"no usable events (face={n_face_all}, car={n_car_all})")

    # 5) Epoch + baseline correct + artifact rejection.
    epochs = mne.Epochs(
        raw,
        events,
        event_id=EVENT_ID,
        tmin=TMIN,
        tmax=TMAX,
        baseline=BASELINE,
        picks="eeg",
        reject=REJECT,
        flat=FLAT,
        preload=True,
        reject_by_annotation=True,
        verbose=False,
    )

    n_face = len(epochs["face"])
    n_car = len(epochs["car"])
    if n_face < MIN_TRIALS_PER_CONDITION or n_car < MIN_TRIALS_PER_CONDITION:
        raise RuntimeError(
            f"too few surviving trials (face={n_face}, car={n_car}; "
            f"minimum {MIN_TRIALS_PER_CONDITION})"
        )

    missing_roi = [ch for ch in ROI if ch not in epochs.ch_names]
    if missing_roi:
        raise RuntimeError(f"missing ROI channels: {missing_roi}")

    # 6) Condition averages and the face-minus-car difference wave.
    ev_face = epochs["face"].average()
    ev_car = epochs["car"].average()
    diff = mne.combine_evoked([ev_face, ev_car], weights=[1.0, -1.0])

    # 7) Mean amplitude over the ROI and the 130-200 ms window, in microvolts.
    seg = diff.copy().pick(ROI).crop(WIN_TMIN, WIN_TMAX)
    amp_uv = float(seg.data.mean() * 1e6)

    return {
        "subject": subject,
        "amplitude_uV": round(amp_uv, ROUND_DP),
        "n_face": n_face,
        "n_car": n_car,
        "n_face_presented": n_face_all,
        "n_car_presented": n_car_all,
        "pct_trials_rejected": round(
            100.0 * (1.0 - (n_face + n_car) / max(n_face_all + n_car_all, 1)), ROUND_DP
        ),
        "n_ica_components_removed": n_ica_excluded,
        "n_window_samples": int(seg.data.shape[1]),
    }


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    per_subject: dict[str, float] = {}
    excluded: list[str] = []
    diagnostics: dict[str, dict] = {}
    exclusion_reasons: dict[str, str] = {}

    for subject in SUBJECTS:
        try:
            rec = measure_subject(subject)
        except Exception as exc:  # noqa: BLE001 - one bad subject must not kill the run
            excluded.append(subject)
            exclusion_reasons[subject] = f"{type(exc).__name__}: {exc}"
            print(f"[{subject}] EXCLUDED -> {exc}")
            traceback.print_exc()
            continue

        per_subject[subject] = rec["amplitude_uV"]
        diagnostics[subject] = rec
        print(
            f"[{subject}] N170 face-car = {rec['amplitude_uV']:+.3f} uV "
            f"(face n={rec['n_face']}, car n={rec['n_car']}, "
            f"{rec['pct_trials_rejected']:.1f}% trials rejected, "
            f"{rec['n_ica_components_removed']} ICA comps removed)"
        )

    values = np.array(list(per_subject.values()), dtype=float)
    grand_mean = round(float(values.mean()), ROUND_DP) if values.size else None
    grand_sd = round(float(values.std(ddof=1)), ROUND_DP) if values.size > 1 else None
    grand_sem = (
        round(float(values.std(ddof=1) / np.sqrt(values.size)), ROUND_DP)
        if values.size > 1
        else None
    )

    result = {
        "per_subject": per_subject,
        "excluded": excluded,
        "n_analyzed": len(per_subject),
        "grand_mean_uV": grand_mean,
        "choices": {
            "reference": (
                "Common average reference over the 30 scalp EEG electrodes "
                "(EOG channels excluded), applied after ocular ICA correction."
            ),
            "montage": "standard_1005; FP1/FP2 renamed to Fp1/Fp2 for montage matching",
            "channel_types": f"{EOG_NAMES} re-typed from EEG to EOG",
            "filter": (
                f"FIR ({FILTER_DESIGN}) zero-phase band-pass "
                f"{L_FREQ}-{H_FREQ} Hz on EEG and EOG channels"
            ),
            "resample_hz": RESAMPLE_SFREQ,
            "artifact_correction": (
                f"Extended-Infomax ICA (n_components={ICA_N_COMPONENTS} explained "
                f"variance, random_state={ICA_RANDOM_STATE}) fitted on a "
                f"{ICA_HPF} Hz high-passed copy; components correlating with "
                "HEOG_left / HEOG_right / VEOG_lower (z > 3) removed"
            ),
            "epoch_window_s": [TMIN, TMAX],
            "baseline_s": list(BASELINE),
            "artifact_rejection": (
                f"peak-to-peak > {REJECT['eeg'] * 1e6:.0f} uV on any EEG channel; "
                f"flat < {FLAT['eeg'] * 1e6:.1f} uV"
            ),
            "conditions": "face = event value 1-40; car = event value 41-80",
            "ignored_events": "101-180 (scrambled), 201/202 (responses)",
            "contrast": "difference wave = ERP(face) - ERP(car), computed per subject",
            "roi": ROI,
            "measurement": (
                f"mean amplitude of the difference wave averaged over the ROI "
                f"channels and the {int(WIN_TMIN * 1000)}-{int(WIN_TMAX * 1000)} ms "
                "window (inclusive), reported in uV"
            ),
            "exclusion_rule": (
                f"subject excluded if a file is unreadable or if either condition "
                f"retains < {MIN_TRIALS_PER_CONDITION} artifact-free epochs"
            ),
            "grand_mean_definition": "unweighted mean across analyzed subjects",
            "grand_sd_uV": grand_sd,
            "grand_sem_uV": grand_sem,
            "software": f"mne {mne.__version__}",
            "exclusion_reasons": exclusion_reasons,
            "per_subject_diagnostics": diagnostics,
            "notes": (
                "Standard ERP-CORE-style N170 pipeline. Data are re-referenced to the "
                "common average of the 30 scalp electrodes; the ocular leads are typed "
                "as EOG and used only to identify blink/saccade ICA components, so they "
                "never enter the reference or the ERP. Epochs are baseline-corrected on "
                "the 200 ms pre-stimulus interval and screened with a 100 uV "
                "peak-to-peak criterion. The face-selectivity measure is the mean (not "
                "peak) amplitude of the face-minus-car difference wave over the "
                "bilateral occipito-temporal ROI (PO7, PO8, P7, P8) in 130-200 ms, "
                "which is the conventional N170 latency range; a negative value means "
                "faces elicit a more negative response than cars, i.e. the expected "
                "N170 face effect. All values rounded to 3 decimal places."
            ),
        },
    }

    OUT_JSON.write_text(json.dumps(result, indent=2))
    print(f"\nAnalyzed {len(per_subject)}/{len(SUBJECTS)} subjects; "
          f"grand mean = {grand_mean} uV -> {OUT_JSON}")


if __name__ == "__main__":
    main()
