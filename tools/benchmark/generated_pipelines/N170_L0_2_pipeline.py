#!/usr/bin/env python3
"""
N170 face-selectivity effect on the ERP CORE N170 dataset (sub-001 ... sub-020).

Measure
-------
Per subject: the face-minus-car difference wave, summarised as the MEAN AMPLITUDE
over the bilateral occipito-temporal ROI {PO7, PO8, P7, P8} in the 130-200 ms
post-stimulus window, reported in microvolts.

Pipeline (standard ERP practice; every choice is recorded in result["choices"])
------------------------------------------------------------------------------
 1. Load the EEGLAB .set continuous recording (1024 Hz, 30 scalp EEG + 3 ocular).
 2. Rename FP1/FP2 -> Fp1/Fp2 and re-type HEOG_left / HEOG_right / VEOG_lower as
    EOG (they are stored as EEG in the file). Doing this BEFORE referencing keeps
    the ocular channels out of the average reference.
 3. Attach the standard_1020 montage.
 4. Band-pass 0.1-30 Hz, zero-phase FIR (firwin, Hamming). 0.1 Hz removes drift
    without distorting the N170; 30 Hz removes muscle/line noise (60 Hz here).
 5. Ocular artefact correction by ICA (extended-infomax via Picard, 20 components)
    fitted on a 1-30 Hz / 256 Hz copy; components correlated with the EOG channels
    (z > 3) are removed from the 0.1-30 Hz data. ICA is run BEFORE re-referencing
    so the data are still full-rank.
 6. Re-reference to the AVERAGE of the 30 scalp electrodes.
 7. Epoch -200 to +800 ms around face (value 1-40) and car (value 41-80) stimulus
    events taken from the BIDS events.tsv; baseline correct on -200 to 0 ms.
 8. Reject epochs with peak-to-peak amplitude > 100 uV (or flat < 0.1 uV) on any
    scalp electrode.
 9. Average each condition, form difference = face - car, then average the ROI
    channels over 130-200 ms.

A subject is EXCLUDED if a file is missing/unreadable or if fewer than 20 clean
epochs survive in either condition.

Usage:  python pipeline.py
Output: result.json next to this script.
"""

from __future__ import annotations

import json
import os
import sys
import traceback

import numpy as np
import pandas as pd

import mne

mne.set_log_level("ERROR")

# --------------------------------------------------------------------------- #
# Configuration                                                                #
# --------------------------------------------------------------------------- #

DATA_ROOT = "/home/hou/mne_data/erpcore-N170"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(OUT_DIR, "result.json")

SUBJECTS = [f"sub-{i:03d}" for i in range(1, 21)]

# Event coding in the BIDS events.tsv "value" column.
FACE_RANGE = (1, 40)        # inclusive
CAR_RANGE = (41, 80)        # inclusive
FACE_ID, CAR_ID = 1, 2

# Filtering
L_FREQ, H_FREQ = 0.1, 30.0

# ICA
ICA_HP = 1.0                # high-pass for the ICA training copy
ICA_SFREQ = 256.0           # decimate the ICA training copy for speed
N_ICA_COMPONENTS = 20
ICA_RANDOM_STATE = 97
EOG_Z_THRESHOLD = 3.0
EOG_NAMES = ["HEOG_left", "HEOG_right", "VEOG_lower"]

# Epoching
TMIN, TMAX = -0.2, 0.8
BASELINE = (-0.2, 0.0)
REJECT = dict(eeg=100e-6)   # 100 uV peak-to-peak
FLAT = dict(eeg=0.1e-6)     # 0.1 uV peak-to-peak

# Measurement
ROI = ["PO7", "PO8", "P7", "P8"]
WIN_TMIN, WIN_TMAX = 0.130, 0.200

# Quality control
MIN_EPOCHS_PER_CONDITION = 20

RENAME = {"FP1": "Fp1", "FP2": "Fp2"}


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def subject_paths(sub: str):
    eeg_dir = os.path.join(DATA_ROOT, sub, "eeg")
    return (
        os.path.join(eeg_dir, f"{sub}_task-N170_eeg.set"),
        os.path.join(eeg_dir, f"{sub}_task-N170_events.tsv"),
    )


def load_raw(set_path: str) -> mne.io.BaseRaw:
    """Read the EEGLAB file and fix channel naming / typing / montage."""
    raw = mne.io.read_raw_eeglab(set_path, preload=True)

    ren = {k: v for k, v in RENAME.items() if k in raw.ch_names}
    if ren:
        raw.rename_channels(ren)

    # The three ocular derivations are stored as EEG in the .set file; re-type
    # them so they are excluded from the average reference and from the
    # peak-to-peak epoch rejection.
    types = {ch: "eog" for ch in EOG_NAMES if ch in raw.ch_names}
    if types:
        raw.set_channel_types(types)

    montage = mne.channels.make_standard_montage("standard_1020")
    raw.set_montage(montage, on_missing="ignore", match_case=False)
    return raw


def read_condition_events(tsv_path: str, raw: mne.io.BaseRaw) -> np.ndarray:
    """Build an MNE events array (n, 3) for face and car stimulus events."""
    df = pd.read_csv(tsv_path, sep="\t")

    onset = pd.to_numeric(df["onset"], errors="coerce")
    value = pd.to_numeric(df["value"], errors="coerce")
    ok = onset.notna() & value.notna()
    onset = onset[ok].to_numpy(dtype=float)
    value = value[ok].to_numpy(dtype=float).round().astype(int)

    is_face = (value >= FACE_RANGE[0]) & (value <= FACE_RANGE[1])
    is_car = (value >= CAR_RANGE[0]) & (value <= CAR_RANGE[1])
    keep = is_face | is_car
    if not keep.any():
        return np.empty((0, 3), dtype=int)

    onset = onset[keep]
    codes = np.where(is_face[keep], FACE_ID, CAR_ID)

    sfreq = raw.info["sfreq"]
    samples = np.round(onset * sfreq).astype(int) + int(raw.first_samp)

    # Drop events whose epoch would run off either end of the recording.
    lo = int(raw.first_samp) + int(np.ceil(abs(TMIN) * sfreq))
    hi = int(raw.first_samp) + raw.n_times - int(np.ceil(TMAX * sfreq)) - 1
    inside = (samples >= lo) & (samples <= hi)
    samples, codes = samples[inside], codes[inside]

    order = np.argsort(samples, kind="stable")
    samples, codes = samples[order], codes[order]
    _, uniq = np.unique(samples, return_index=True)
    samples, codes = samples[np.sort(uniq)], codes[np.sort(uniq)]

    events = np.column_stack(
        [samples, np.zeros_like(samples), codes]
    ).astype(int)
    return events


def run_ica(raw: mne.io.BaseRaw) -> int:
    """Remove EOG-correlated components in place. Returns n components removed."""
    eog_present = [ch for ch in EOG_NAMES if ch in raw.ch_names]
    if not eog_present:
        return 0

    raw_ica = raw.copy().filter(
        l_freq=ICA_HP, h_freq=None, picks=["eeg", "eog"],
        method="fir", phase="zero", fir_design="firwin",
    )
    if raw_ica.info["sfreq"] > ICA_SFREQ:
        raw_ica.resample(ICA_SFREQ)

    n_eeg = len(mne.pick_types(raw.info, eeg=True, eog=False))
    n_comp = int(min(N_ICA_COMPONENTS, max(n_eeg - 1, 1)))

    try:
        ica = mne.preprocessing.ICA(
            n_components=n_comp,
            method="picard",
            fit_params=dict(ortho=False, extended=True),
            max_iter=500,
            random_state=ICA_RANDOM_STATE,
        )
        ica.fit(raw_ica, picks="eeg")
    except Exception:
        # Fall back to MNE's built-in extended infomax (no optional deps).
        ica = mne.preprocessing.ICA(
            n_components=n_comp,
            method="infomax",
            fit_params=dict(extended=True),
            max_iter=500,
            random_state=ICA_RANDOM_STATE,
        )
        ica.fit(raw_ica, picks="eeg")

    bad_idx, _ = ica.find_bads_eog(
        raw_ica, ch_name=eog_present, threshold=EOG_Z_THRESHOLD, measure="zscore"
    )
    ica.exclude = sorted(set(int(i) for i in bad_idx))
    if ica.exclude:
        ica.apply(raw)
    return len(ica.exclude)


def measure_difference(evoked_diff: mne.Evoked):
    """Mean amplitude (uV) of the difference wave over the ROI and time window."""
    picks = [ch for ch in ROI if ch in evoked_diff.ch_names]
    if not picks:
        raise RuntimeError("none of the ROI channels %s are present" % ROI)
    seg = evoked_diff.copy().pick(picks).crop(WIN_TMIN, WIN_TMAX)
    return float(np.mean(seg.data) * 1e6), picks, int(seg.data.shape[1])


# --------------------------------------------------------------------------- #
# Per-subject processing                                                       #
# --------------------------------------------------------------------------- #

def process_subject(sub: str) -> dict:
    set_path, tsv_path = subject_paths(sub)
    for p in (set_path, tsv_path):
        if not os.path.exists(p):
            raise FileNotFoundError(p)

    raw = load_raw(set_path)

    raw.filter(
        l_freq=L_FREQ, h_freq=H_FREQ, picks=["eeg", "eog"],
        method="fir", phase="zero", fir_design="firwin",
    )

    n_ica_removed = run_ica(raw)

    raw.set_eeg_reference("average", projection=False)

    events = read_condition_events(tsv_path, raw)
    if events.size == 0:
        raise RuntimeError("no face/car stimulus events found")

    epochs = mne.Epochs(
        raw,
        events,
        event_id={"face": FACE_ID, "car": CAR_ID},
        tmin=TMIN,
        tmax=TMAX,
        baseline=BASELINE,
        picks="eeg",
        reject=REJECT,
        flat=FLAT,
        preload=True,
        on_missing="warn",
        reject_by_annotation=True,
    )

    n_face, n_car = len(epochs["face"]), len(epochs["car"])
    if n_face < MIN_EPOCHS_PER_CONDITION or n_car < MIN_EPOCHS_PER_CONDITION:
        raise RuntimeError(
            f"too few clean epochs (face={n_face}, car={n_car}; "
            f"minimum {MIN_EPOCHS_PER_CONDITION} per condition)"
        )

    ev_face = epochs["face"].average()
    ev_car = epochs["car"].average()
    diff = mne.combine_evoked([ev_face, ev_car], weights=[1.0, -1.0])

    value_uv, picks_used, n_samples = measure_difference(diff)

    return {
        "value_uV": value_uv,
        "n_face": int(n_face),
        "n_car": int(n_car),
        "n_events_face": int(np.sum(events[:, 2] == FACE_ID)),
        "n_events_car": int(np.sum(events[:, 2] == CAR_ID)),
        "n_ica_removed": int(n_ica_removed),
        "roi_used": picks_used,
        "n_window_samples": n_samples,
    }


# --------------------------------------------------------------------------- #
# Main                                                                         #
# --------------------------------------------------------------------------- #

def main() -> int:
    per_subject = {}
    excluded = []
    exclusion_reasons = {}
    diagnostics = {}

    for sub in SUBJECTS:
        print(f"[{sub}] processing ...", flush=True)
        try:
            info = process_subject(sub)
        except Exception as exc:  # noqa: BLE001 - one bad subject must not kill the run
            excluded.append(sub)
            exclusion_reasons[sub] = f"{type(exc).__name__}: {exc}"
            print(f"[{sub}] EXCLUDED -> {exclusion_reasons[sub]}", flush=True)
            traceback.print_exc(file=sys.stderr)
            continue

        per_subject[sub] = round(info["value_uV"], 3)
        diagnostics[sub] = {
            k: v for k, v in info.items() if k != "value_uV"
        }
        print(
            f"[{sub}] N170 face-car = {per_subject[sub]:+.3f} uV "
            f"(face={info['n_face']}/{info['n_events_face']}, "
            f"car={info['n_car']}/{info['n_events_car']} epochs kept, "
            f"{info['n_ica_removed']} ocular IC(s) removed)",
            flush=True,
        )

    values = np.array(list(per_subject.values()), dtype=float)
    grand_mean = round(float(values.mean()), 3) if values.size else None

    notes = (
        "Reference: average of the 30 scalp electrodes (EOG channels re-typed to "
        "EOG first so they are excluded from the average). Preprocessing: "
        "zero-phase FIR band-pass 0.1-30 Hz on the 1024 Hz data (no resampling, "
        "so events.tsv onsets map exactly onto samples); ocular artefacts removed "
        "with extended-infomax ICA (Picard, 20 components) fitted on a 1-30 Hz / "
        "256 Hz copy, excluding components whose correlation with HEOG_left, "
        "HEOG_right or VEOG_lower exceeded z=3; then average reference. "
        "Epochs -200 to +800 ms, baseline -200 to 0 ms, epochs rejected at "
        "100 uV peak-to-peak (or flat below 0.1 uV) on any scalp electrode. "
        "Faces = events.tsv value 1-40, cars = 41-80; scrambled (101-180) and "
        "responses (201/202) ignored. Conditions averaged separately, difference "
        "wave = face - car, and the measure is the mean amplitude of that "
        "difference wave averaged over PO7, PO8, P7, P8 and over 130-200 ms "
        "(endpoints inclusive), in microvolts. Bad-channel interpolation was not "
        "performed (no protocol-defined bad-channel list). A subject is excluded "
        "if fewer than 20 clean epochs remain in either condition."
    )

    result = {
        "per_subject": per_subject,
        "excluded": excluded,
        "n_analyzed": len(per_subject),
        "grand_mean_uV": grand_mean,
        "choices": {
            "notes": notes,
            "reference": "average reference over the 30 scalp EEG channels",
            "eog_channels_retyped": EOG_NAMES,
            "filter": {
                "l_freq_hz": L_FREQ,
                "h_freq_hz": H_FREQ,
                "method": "FIR, firwin/Hamming, zero-phase (non-causal)",
            },
            "resampling": "none (analysis kept at the native 1024 Hz)",
            "artifact_correction": {
                "method": "ICA (Picard, extended infomax), fallback extended infomax",
                "n_components": N_ICA_COMPONENTS,
                "fit_on": f"copy high-passed at {ICA_HP} Hz and resampled to {ICA_SFREQ} Hz",
                "component_selection": f"find_bads_eog z-score threshold {EOG_Z_THRESHOLD}",
                "random_state": ICA_RANDOM_STATE,
            },
            "epoching": {
                "tmin_s": TMIN,
                "tmax_s": TMAX,
                "baseline_s": list(BASELINE),
                "reject_peak_to_peak_uV": 100.0,
                "flat_peak_to_peak_uV": 0.1,
            },
            "conditions": {
                "face": "events.tsv value 1-40",
                "car": "events.tsv value 41-80",
                "ignored": "101-180 (scrambled), 201/202 (responses)",
            },
            "contrast": "face-minus-car difference wave (face average - car average)",
            "roi": ROI,
            "time_window_ms": [WIN_TMIN * 1000, WIN_TMAX * 1000],
            "measure": "mean amplitude across ROI channels and time window, in uV",
            "exclusion_rule": (
                f"missing/unreadable data, or < {MIN_EPOCHS_PER_CONDITION} clean "
                "epochs in either condition"
            ),
            "exclusion_reasons": exclusion_reasons,
            "software": {
                "mne": mne.__version__,
                "numpy": np.__version__,
                "pandas": pd.__version__,
            },
            "per_subject_diagnostics": diagnostics,
        },
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w") as fh:
        json.dump(result, fh, indent=2)

    print(f"\nAnalyzed {len(per_subject)}/{len(SUBJECTS)} subjects; "
          f"grand mean = {grand_mean} uV", flush=True)
    print(f"Wrote {OUT_JSON}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
