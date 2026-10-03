#!/usr/bin/env python3
"""
Auditory Mismatch Negativity (MMN) — ERP CORE passive auditory oddball.

Per subject, computes the deviant-minus-standard difference wave and reports its
mean amplitude over Fz, FCz, Cz in the 100-250 ms window (microvolts).

Pipeline (standard ERP practice; all parameters chosen a priori, no protocol doc):
  1. Read EEGLAB .set (1024 Hz, 30 scalp EEG + 3 EOG).
  2. Rename FP1/FP2 -> Fp1/Fp2, mark the 3 ocular channels as EOG, attach the
     standard_1020 montage.
  3. Derive bipolar ocular channels: VEOG = Fp2 - VEOG_lower, HEOG = HEOG_left -
     HEOG_right (the ERP CORE convention); drop the monopolar ocular channels.
  4. Band-pass 0.1-30 Hz, zero-phase FIR (Hamming), on EEG + EOG.
  5. Ocular artifact CORRECTION by ICA (FastICA, 20 components, random_state=97),
     fitted on a 1-30 Hz copy (decim=8); components correlated with VEOG/HEOG
     (z > 3) are removed from the 0.1-30 Hz data.
  6. Re-reference to the average of P9 and P10 (near-mastoid). This is the
     conventional reference for auditory MMN: it preserves the fronto-central
     negativity that the mastoid polarity inversion defines, and it is the
     reference used by ERP CORE for this task.
  7. Epoch -200 to 800 ms on value==80 (standard) and value==70 (deviant),
     baseline corrected on -200 to 0 ms. The 15 "first stream" tones (value==180)
     are NOT analysed (they precede the oddball stream proper).
  8. Residual artifact REJECTION: drop epochs with peak-to-peak > 100 uV on any
     scalp EEG channel or > 150 uV on VEOG/HEOG.
  9. Average per condition, difference = deviant - standard, mean amplitude over
     {Fz, FCz, Cz} x [100, 250] ms.

Subject-level exclusion: fewer than 20 surviving epochs in either condition, or
the file/one of the ROI channels is unavailable.

Writes JSON to result.json next to this script. Nothing is plotted.
"""

import json
import os
import warnings

import numpy as np
import pandas as pd

import mne

mne.set_log_level("ERROR")
warnings.filterwarnings("ignore")

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
DATA_ROOT = "/home/hou/mne_data/MNE-erpcoremmn2021-data"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(OUT_DIR, "result.json")

SUBJECTS = [f"sub-{i:03d}" for i in range(1, 41)]

EOG_MONO = ["HEOG_left", "HEOG_right", "VEOG_lower"]
RENAME = {"FP1": "Fp1", "FP2": "Fp2"}

L_FREQ, H_FREQ = 0.1, 30.0          # band-pass (Hz)
ICA_HP = 1.0                         # high-pass for the ICA training copy (Hz)
N_ICA_COMPONENTS = 20
ICA_RANDOM_STATE = 97
ICA_Z_THRESH = 3.0

REF_CHANNELS = ["P9", "P10"]         # near-mastoid average reference

TMIN, TMAX = -0.2, 0.8               # epoch limits (s)
BASELINE = (-0.2, 0.0)

REJECT = dict(eeg=100e-6, eog=150e-6)  # peak-to-peak thresholds (V)

EVENT_ID = {"standard": 80, "deviant": 70}
MIN_EPOCHS = 20                      # per condition

ROI = ["Fz", "FCz", "Cz"]
WIN_START, WIN_STOP = 0.100, 0.250   # measurement window (s)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def read_events(events_tsv, sfreq, n_times):
    """Build an MNE events array from the BIDS events.tsv (onset in seconds)."""
    df = pd.read_csv(events_tsv, sep="\t")
    df = df[df["value"].astype(str).str.strip().isin(["80", "70"])].copy()
    df["value"] = df["value"].astype(int)

    samples = np.round(df["onset"].astype(float).to_numpy() * sfreq).astype(int)
    codes = df["value"].to_numpy().astype(int)

    # Keep only events whose full epoch fits inside the recording.
    lo = samples + int(np.floor(TMIN * sfreq))
    hi = samples + int(np.ceil(TMAX * sfreq))
    keep = (lo >= 0) & (hi < n_times)
    samples, codes = samples[keep], codes[keep]

    events = np.column_stack([samples, np.zeros_like(samples), codes]).astype(int)
    # Guard against duplicate sample indices after rounding.
    _, uniq = np.unique(events[:, 0], return_index=True)
    return events[np.sort(uniq)]


def preprocess(raw):
    """Rename, type, montage, bipolar EOG, band-pass filter."""
    raw.rename_channels({k: v for k, v in RENAME.items() if k in raw.ch_names})
    raw.set_channel_types({ch: "eog" for ch in EOG_MONO if ch in raw.ch_names})
    raw.set_montage("standard_1020", match_case=False, on_missing="ignore")

    raw = mne.set_bipolar_reference(
        raw,
        anode=["Fp2", "HEOG_left"],
        cathode=["VEOG_lower", "HEOG_right"],
        ch_name=["VEOG", "HEOG"],
        drop_refs=False,
    )
    raw.set_channel_types({"VEOG": "eog", "HEOG": "eog"})
    raw.drop_channels([ch for ch in EOG_MONO if ch in raw.ch_names])

    raw.filter(L_FREQ, H_FREQ, picks=["eeg", "eog"], method="fir",
               fir_design="firwin", phase="zero", verbose=False)
    return raw


def remove_ocular(raw):
    """ICA correction of blink / saccade components using the bipolar EOG."""
    raw_ica = raw.copy().filter(ICA_HP, H_FREQ, picks=["eeg", "eog"],
                                method="fir", fir_design="firwin",
                                phase="zero", verbose=False)
    n_eeg = len(mne.pick_types(raw.info, eeg=True, exclude="bads"))
    n_comp = int(min(N_ICA_COMPONENTS, n_eeg - 1))

    ica = mne.preprocessing.ICA(
        n_components=n_comp,
        method="fastica",
        random_state=ICA_RANDOM_STATE,
        max_iter="auto",
    )
    ica.fit(raw_ica, picks="eeg", decim=8, verbose=False)

    bads = []
    for ch in ("VEOG", "HEOG"):
        try:
            idx, _ = ica.find_bads_eog(raw_ica, ch_name=ch,
                                       threshold=ICA_Z_THRESH, verbose=False)
            bads.extend(idx)
        except Exception:
            pass
    ica.exclude = sorted(set(bads))
    if ica.exclude:
        ica.apply(raw, verbose=False)
    return raw, ica.exclude


def mean_amplitude(evoked):
    """Mean amplitude (uV) over ROI channels x measurement window."""
    picks = [evoked.ch_names.index(ch) for ch in ROI]
    times = evoked.times
    tol = 0.5 / evoked.info["sfreq"]
    mask = (times >= WIN_START - tol) & (times <= WIN_STOP + tol)
    data = evoked.data[np.ix_(picks, np.flatnonzero(mask))]
    return float(np.mean(data) * 1e6)


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def run_subject(sub):
    eeg_dir = os.path.join(DATA_ROOT, sub, "eeg")
    set_path = os.path.join(eeg_dir, f"{sub}_task-MMN_eeg.set")
    tsv_path = os.path.join(eeg_dir, f"{sub}_task-MMN_events.tsv")
    if not (os.path.exists(set_path) and os.path.exists(tsv_path)):
        raise FileNotFoundError(f"missing raw or events file for {sub}")

    raw = mne.io.read_raw_eeglab(set_path, preload=True, verbose=False)
    raw = preprocess(raw)
    raw, n_bad_ica = remove_ocular(raw)

    missing_ref = [ch for ch in REF_CHANNELS if ch not in raw.ch_names]
    if missing_ref:
        raise RuntimeError(f"reference channel(s) absent: {missing_ref}")
    raw.set_eeg_reference(ref_channels=REF_CHANNELS, verbose=False)

    missing_roi = [ch for ch in ROI if ch not in raw.ch_names]
    if missing_roi:
        raise RuntimeError(f"ROI channel(s) absent: {missing_roi}")

    events = read_events(tsv_path, raw.info["sfreq"], raw.n_times)
    epochs = mne.Epochs(
        raw, events, event_id=EVENT_ID, tmin=TMIN, tmax=TMAX,
        baseline=BASELINE, picks=["eeg", "eog"], reject=REJECT,
        preload=True, reject_by_annotation=False, verbose=False,
    )

    n_std = len(epochs["standard"])
    n_dev = len(epochs["deviant"])
    if n_std < MIN_EPOCHS or n_dev < MIN_EPOCHS:
        raise RuntimeError(
            f"too few surviving epochs (standard={n_std}, deviant={n_dev})")

    ev_std = epochs["standard"].average(picks="eeg")
    ev_dev = epochs["deviant"].average(picks="eeg")
    diff = mne.combine_evoked([ev_dev, ev_std], weights=[1, -1])

    return {
        "amplitude": mean_amplitude(diff),
        "n_standard": int(n_std),
        "n_deviant": int(n_dev),
        "n_events_total": int(len(events)),
        "n_ica_excluded": int(len(n_bad_ica)),
    }


def main():
    per_subject, excluded, details = {}, [], {}

    for sub in SUBJECTS:
        try:
            res = run_subject(sub)
        except Exception as exc:
            excluded.append(sub)
            details[sub] = {"error": f"{type(exc).__name__}: {exc}"}
            print(f"{sub}: EXCLUDED ({type(exc).__name__}: {exc})", flush=True)
            continue

        per_subject[sub] = round(res["amplitude"], 3)
        details[sub] = {k: v for k, v in res.items() if k != "amplitude"}
        print(
            f"{sub}: MMN = {per_subject[sub]:+.3f} uV "
            f"(std={res['n_standard']}, dev={res['n_deviant']}, "
            f"ICA rm={res['n_ica_excluded']})",
            flush=True,
        )

    vals = np.array(list(per_subject.values()), dtype=float)
    grand = round(float(np.mean(vals)), 3) if vals.size else None

    out = {
        "per_subject": per_subject,
        "excluded": excluded,
        "n_analyzed": len(per_subject),
        "grand_mean_uV": grand,
        "choices": {
            "notes": (
                "ERP CORE passive auditory oddball. Per subject: EEGLAB .set read at "
                "1024 Hz; FP1/FP2 renamed Fp1/Fp2; HEOG_left/HEOG_right/VEOG_lower set "
                "to EOG type; standard_1020 montage; bipolar VEOG=Fp2-VEOG_lower and "
                "HEOG=HEOG_left-HEOG_right derived (monopolar ocular channels dropped); "
                "zero-phase FIR band-pass 0.1-30 Hz; ocular artifacts CORRECTED by ICA "
                "(FastICA, 20 components, random_state=97, fitted on a 1-30 Hz copy with "
                "decim=8, components with |z|>3 correlation to VEOG or HEOG removed); "
                "re-referenced to the average of P9 and P10 (near-mastoid, the "
                "conventional and ERP CORE reference for auditory MMN); epochs -200 to "
                "800 ms with -200 to 0 ms baseline on value==80 (standard) and value==70 "
                "(deviant); value==180 first-stream tones excluded; residual artifact "
                "rejection at 100 uV peak-to-peak on EEG and 150 uV on VEOG/HEOG; "
                "condition averages then difference wave = deviant - standard; MMN = "
                "mean amplitude over Fz, FCz, Cz across 100-250 ms, in uV. All standards "
                "were kept (standards following a deviant were not discarded). Subjects "
                "with <20 surviving epochs in either condition are excluded. "
                "grand_mean_uV is the unweighted mean of the per-subject values."
            ),
            "filter_hz": [L_FREQ, H_FREQ],
            "reference": "average of P9 and P10",
            "epoch_s": [TMIN, TMAX],
            "baseline_s": list(BASELINE),
            "artifact_correction": (
                f"ICA fastica n_components={N_ICA_COMPONENTS} "
                f"random_state={ICA_RANDOM_STATE} eog_z={ICA_Z_THRESH}"
            ),
            "artifact_rejection_uV_ptp": {"eeg": 100.0, "eog": 150.0},
            "roi": ROI,
            "window_ms": [WIN_START * 1000, WIN_STOP * 1000],
            "min_epochs_per_condition": MIN_EPOCHS,
            "per_subject_details": details,
        },
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(out, f, indent=2)

    print(f"\nAnalyzed {len(per_subject)}/{len(SUBJECTS)} subjects; "
          f"grand mean MMN = {grand} uV -> {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
