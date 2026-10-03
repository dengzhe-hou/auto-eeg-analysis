#!/usr/bin/env python3
"""
Auditory Mismatch Negativity (MMN) pipeline -- ERP CORE MMN (sub-001 ... sub-040).

Implements the recipe:
  1. Preprocess : 0.1-30 Hz zero-phase FIR bandpass; drop dedicated EOG channels;
                  RANSAC bad-channel detection -> interpolate -> average reference of
                  scalp channels; resample to >= 200 Hz.
  2. ICA        : SKIPPED (see `choices` in the JSON output).  ERP CORE MMN is a clean,
                  passive paradigm and the recipe explicitly allows a plain +/-100 uV
                  epoch rejection instead.
  3. Epoch      : -0.2 to 0.5 s, baseline (-0.2, 0), +/-100 uV artifact rejection,
                  subject kept only if >= 50 deviants AND >= 150 standards survive.
  4. Measure    : per-subject deviant - standard difference wave, mean amplitude over
                  Fz / FCz / Cz in the 100-250 ms window, reported in microvolts.

Standalone: `python pipeline.py`.  Writes result.json next to this file.
"""

from __future__ import annotations

import json
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

import mne

mne.set_log_level("ERROR")

# --------------------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------------------

DATA_ROOT = Path("/home/hou/mne_data/MNE-erpcoremmn2021-data")
OUT_DIR = Path(
    "/tmp/claude-1137/-home-hou-Research-auto-eeg-analysis/"
    "b4a153ed-22fa-4b6a-ad04-d134656fecf4/scratchpad/gen_scale/L1_12"
)
OUT_JSON = OUT_DIR / "result.json"

SUBJECTS = [f"sub-{i:03d}" for i in range(1, 41)]

# 1. preprocessing
L_FREQ, H_FREQ = 0.1, 30.0          # zero-phase FIR bandpass
RESAMPLE_SFREQ = 256.0              # 1024 / 4 -> integer decimation, >= 200 Hz
EOG_NAMES = ("HEOG_left", "HEOG_right", "VEOG_lower")   # typed EEG in file; drop by name
MONTAGE = "standard_1020"
RANDOM_STATE = 97

# 3. epoching
TMIN, TMAX = -0.2, 0.5
BASELINE = (-0.2, 0.0)
REJECT_UV = 100.0                   # peak-to-peak threshold, microvolts
REJECT = dict(eeg=REJECT_UV * 1e-6)
MIN_DEVIANTS, MIN_STANDARDS = 50, 150

# events
CODE_STANDARD, CODE_DEVIANT, CODE_FIRST_STREAM = 80, 70, 180
EVENT_ID = {"deviant": CODE_DEVIANT, "standard": CODE_STANDARD}

# 4. measurement
ROI = ("Fz", "FCz", "Cz")
MEAS_TMIN, MEAS_TMAX = 0.100, 0.250


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------

def resolve_names(ch_names, wanted):
    """Case-insensitive resolution of `wanted` against the actual channel names."""
    lut = {name.lower(): name for name in ch_names}
    return [lut[w.lower()] for w in wanted if w.lower() in lut]


def load_raw(sub: str) -> mne.io.BaseRaw:
    """Read the EEGLAB .set file, drop EOG channels, attach the montage."""
    set_path = DATA_ROOT / sub / "eeg" / f"{sub}_task-MMN_eeg.set"
    if not set_path.exists():
        raise FileNotFoundError(f"missing raw file: {set_path}")

    raw = mne.io.read_raw_eeglab(str(set_path), preload=True)

    # Dedicated EOG channels are typed as EEG in these files -> drop them by name so they
    # never enter the average reference (recipe step 1).
    drop = resolve_names(raw.ch_names, EOG_NAMES)
    if drop:
        raw.drop_channels(drop)

    raw.set_channel_types({ch: "eeg" for ch in raw.ch_names})
    raw.set_montage(MONTAGE, match_case=False, on_missing="warn")
    return raw, drop


def read_events(sub: str, sfreq: float, n_times: int) -> np.ndarray:
    """Build an MNE events array from the BIDS *_events.tsv (onsets in seconds).

    Keeps only value == 80 (standard) and value == 70 (deviant); 180 (first stream of a
    block) and anything else is dropped.
    """
    tsv = DATA_ROOT / sub / "eeg" / f"{sub}_task-MMN_events.tsv"
    if not tsv.exists():
        raise FileNotFoundError(f"missing events file: {tsv}")

    df = pd.read_csv(tsv, sep="\t")
    if "onset" not in df.columns:
        raise ValueError(f"{tsv} has no 'onset' column")
    value_col = "value" if "value" in df.columns else "trial_type"
    if value_col not in df.columns:
        raise ValueError(f"{tsv} has no 'value' column")

    onset = pd.to_numeric(df["onset"], errors="coerce")
    value = pd.to_numeric(df[value_col], errors="coerce")

    keep = onset.notna() & value.isin([CODE_STANDARD, CODE_DEVIANT])
    samples = np.rint(onset[keep].to_numpy(float) * sfreq).astype(int)
    codes = value[keep].to_numpy(float).astype(int)

    inside = (samples >= 0) & (samples < n_times)
    samples, codes = samples[inside], codes[inside]

    order = np.argsort(samples, kind="stable")
    samples, codes = samples[order], codes[order]

    # MNE requires unique event samples; rounding to 256 Hz can in principle collide.
    _, first = np.unique(samples, return_index=True)
    first = np.sort(first)
    samples, codes = samples[first], codes[first]

    return np.column_stack([samples, np.zeros_like(samples), codes])


def ransac_bads(raw: mne.io.BaseRaw):
    """RANSAC bad-channel detection.

    Prefers pyprep's `NoisyChannels.find_bad_by_ransac` (operates on continuous data);
    falls back to `autoreject.Ransac` on 2 s fixed-length epochs.  Returns
    (bad_channel_names, backend_label).
    """
    # -- pyprep (if installed) ---------------------------------------------------------
    try:
        from pyprep.find_noisy_channels import NoisyChannels

        nc = NoisyChannels(raw.copy(), do_detrend=False, random_state=RANDOM_STATE)
        nc.find_bad_by_ransac(channel_wise=False)
        return sorted(set(nc.bad_by_ransac)), "pyprep.NoisyChannels.find_bad_by_ransac"
    except ImportError:
        pass
    except Exception:
        pass

    # -- autoreject fallback -----------------------------------------------------------
    try:
        from autoreject import Ransac

        probe = mne.make_fixed_length_epochs(raw, duration=2.0, preload=True)
        rsc = Ransac(random_state=RANDOM_STATE, n_jobs=1, verbose=False)
        rsc.fit(probe)
        bads = sorted(set(getattr(rsc, "bad_chs_", [])))
        del probe, rsc
        return bads, "autoreject.Ransac (2 s fixed-length epochs)"
    except Exception:
        pass

    return [], "unavailable (no bad-channel interpolation performed)"


def mean_amplitude_uv(evoked: mne.Evoked, roi_names) -> float:
    """Mean amplitude (uV) over `roi_names` and the 100-250 ms window."""
    ev = evoked.copy().pick(roi_names).crop(MEAS_TMIN, MEAS_TMAX)
    return float(ev.get_data().mean() * 1e6)


# --------------------------------------------------------------------------------------
# Per-subject pipeline
# --------------------------------------------------------------------------------------

def process_subject(sub: str) -> dict:
    info = {"subject": sub}

    raw, dropped_eog = load_raw(sub)
    info["dropped_channels"] = dropped_eog
    info["sfreq_orig"] = float(raw.info["sfreq"])

    # --- 1. bandpass: 0.1-30 Hz zero-phase FIR ---------------------------------------
    raw.filter(
        l_freq=L_FREQ,
        h_freq=H_FREQ,
        method="fir",
        phase="zero",
        fir_design="firwin",
        fir_window="hamming",
        n_jobs=1,
    )

    # --- resample (>= 200 Hz).  Done before RANSAC purely for speed; events are rebuilt
    #     from the TSV onsets in *seconds*, so no resampling jitter is introduced. -------
    if raw.info["sfreq"] > RESAMPLE_SFREQ:
        raw.resample(RESAMPLE_SFREQ, npad="auto")
    info["sfreq_final"] = float(raw.info["sfreq"])

    # --- 1. RANSAC -> interpolate -> re-reference --------------------------------------
    bads, backend = ransac_bads(raw)
    bads = [b for b in bads if b in raw.ch_names]
    info["ransac_backend"] = backend
    info["bad_channels"] = bads
    if bads:
        raw.info["bads"] = bads
        raw.interpolate_bads(reset_bads=True, mode="accurate")

    raw.set_eeg_reference("average", projection=False)

    # --- 3. epoch ---------------------------------------------------------------------
    events = read_events(sub, raw.info["sfreq"], raw.n_times)
    n_raw = {
        "standard": int((events[:, 2] == CODE_STANDARD).sum()),
        "deviant": int((events[:, 2] == CODE_DEVIANT).sum()),
    }
    info["n_events_raw"] = n_raw
    if n_raw["standard"] == 0 or n_raw["deviant"] == 0:
        raise ValueError(f"no usable events (standard={n_raw['standard']}, "
                         f"deviant={n_raw['deviant']})")

    epochs = mne.Epochs(
        raw,
        events=events,
        event_id=EVENT_ID,
        tmin=TMIN,
        tmax=TMAX,
        baseline=BASELINE,
        reject=REJECT,
        picks="eeg",
        preload=True,
        proj=False,
        reject_by_annotation=False,
        on_missing="raise",
    )

    n_kept = {cond: int(len(epochs[cond])) for cond in ("standard", "deviant")}
    info["n_epochs_kept"] = n_kept

    if n_kept["deviant"] < MIN_DEVIANTS or n_kept["standard"] < MIN_STANDARDS:
        raise ValueError(
            f"below trial minimum (deviants={n_kept['deviant']}/{MIN_DEVIANTS}, "
            f"standards={n_kept['standard']}/{MIN_STANDARDS})"
        )

    # --- 4. measure -------------------------------------------------------------------
    ev_std = epochs["standard"].average()
    ev_dev = epochs["deviant"].average()
    diff = mne.combine_evoked([ev_dev, ev_std], weights=[1.0, -1.0])  # deviant - standard

    roi = resolve_names(diff.ch_names, ROI)
    if len(roi) != len(ROI):
        raise ValueError(f"ROI channels missing: have {roi}, want {list(ROI)}")
    info["roi_channels"] = roi

    info["amplitude_uV"] = mean_amplitude_uv(diff, roi)
    return info


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    per_subject: dict[str, float] = {}
    excluded: list[str] = []
    reasons: dict[str, str] = {}
    diagnostics: dict[str, dict] = {}
    backends: set[str] = set()

    for sub in SUBJECTS:
        try:
            info = process_subject(sub)
            per_subject[sub] = round(info["amplitude_uV"], 3)
            diagnostics[sub] = {
                "n_epochs_kept": info["n_epochs_kept"],
                "bad_channels": info["bad_channels"],
                "sfreq_final": info["sfreq_final"],
            }
            backends.add(info.get("ransac_backend", "unknown"))
            print(f"[ok]   {sub}: {per_subject[sub]:+.3f} uV  "
                  f"(std={info['n_epochs_kept']['standard']}, "
                  f"dev={info['n_epochs_kept']['deviant']}, "
                  f"bads={info['bad_channels']})", flush=True)
        except Exception as exc:  # noqa: BLE001 -- one bad subject must not kill the run
            excluded.append(sub)
            reasons[sub] = f"{type(exc).__name__}: {exc}"
            print(f"[skip] {sub}: {reasons[sub]}", flush=True)
            traceback.print_exc()

    values = np.array(list(per_subject.values()), dtype=float)
    grand_mean = round(float(values.mean()), 3) if values.size else None

    notes = (
        "ICA skipped: ERP CORE MMN is a clean passive paradigm and the recipe permits a "
        "plain amplitude-based epoch rejection instead (extended-Infomax + mne-icalabel "
        "was not run). "
        "Artifact rejection implemented as MNE's native peak-to-peak criterion, "
        f"reject=dict(eeg={REJECT_UV:g}e-6 V), i.e. an epoch is dropped if any scalp "
        "channel spans more than 100 uV within -0.2..0.5 s. "
        f"Bandpass {L_FREQ}-{H_FREQ} Hz, FIR firwin/hamming, phase='zero' (zero-phase, "
        "applied at the native 1024 Hz before resampling). "
        f"Resampled to {RESAMPLE_SFREQ:g} Hz (integer /4 decimation of 1024 Hz, >= 200 Hz "
        "as required); events are rebuilt from the TSV onsets in seconds after "
        "resampling, so no event jitter is introduced. "
        "Order of operations: read .set -> drop the 3 dedicated EOG channels by name "
        "(HEOG_left, HEOG_right, VEOG_lower; they are typed EEG in the file and would "
        "otherwise contaminate the reference) -> standard_1020 montage with "
        "match_case=False -> bandpass -> resample -> RANSAC bad-channel detection -> "
        "spherical-spline interpolation -> average reference over the 30 scalp channels. "
        "RANSAC is run after resampling purely for speed; the recipe fixes the "
        "detect->interpolate->re-reference order, which is respected. "
        f"RANSAC backend(s) actually used: {sorted(backends) if backends else ['none']} "
        "(pyprep.NoisyChannels.find_bad_by_ransac preferred, autoreject.Ransac on 2 s "
        f"fixed-length epochs as fallback; random_state={RANDOM_STATE}). "
        f"Epochs {TMIN} to {TMAX} s, baseline {BASELINE}. "
        "Events: value==80 standard, value==70 deviant, value==180 (first stream) and "
        "all other codes excluded. "
        f"Inclusion: >= {MIN_DEVIANTS} deviants AND >= {MIN_STANDARDS} standards after "
        "rejection. "
        "Measure: per-subject deviant-minus-standard difference wave "
        "(mne.combine_evoked weights [1, -1]), mean amplitude across Fz/FCz/Cz over "
        f"{MEAS_TMIN * 1000:.0f}-{MEAS_TMAX * 1000:.0f} ms, in uV, rounded to 3 dp; "
        "grand mean is the unweighted mean of the per-subject values."
    )

    result = {
        "per_subject": per_subject,
        "excluded": excluded,
        "n_analyzed": len(per_subject),
        "grand_mean_uV": grand_mean,
        "choices": {
            "notes": notes,
            "bandpass_hz": [L_FREQ, H_FREQ],
            "filter": "FIR, firwin design, hamming window, phase='zero' (zero-phase)",
            "resample_hz": RESAMPLE_SFREQ,
            "reference": "average of the 30 scalp EEG channels (EOG dropped first)",
            "dropped_eog_channels": list(EOG_NAMES),
            "montage": f"{MONTAGE} (match_case=False)",
            "bad_channels": "RANSAC -> spherical-spline interpolation -> average reference",
            "ransac_backends_used": sorted(backends),
            "ica": "not applied (clean passive data; amplitude rejection used instead)",
            "epoch_window_s": [TMIN, TMAX],
            "baseline_s": list(BASELINE),
            "rejection": f"peak-to-peak {REJECT_UV:g} uV on all scalp EEG channels",
            "min_trials": {"deviant": MIN_DEVIANTS, "standard": MIN_STANDARDS},
            "contrast": "deviant - standard",
            "roi_channels": list(ROI),
            "measure_window_s": [MEAS_TMIN, MEAS_TMAX],
            "measure": "mean amplitude (uV) over ROI channels and window",
            "random_state": RANDOM_STATE,
            "exclusion_reasons": reasons,
            "per_subject_diagnostics": diagnostics,
        },
    }

    OUT_JSON.write_text(json.dumps(result, indent=2))

    print("-" * 70)
    print(f"analyzed : {result['n_analyzed']}/{len(SUBJECTS)}")
    print(f"excluded : {excluded}")
    print(f"grand mean deviant-standard, Fz/FCz/Cz, 100-250 ms: {grand_mean} uV")
    print(f"written  : {OUT_JSON}")


if __name__ == "__main__":
    main()
