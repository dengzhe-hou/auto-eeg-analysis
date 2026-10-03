#!/usr/bin/env python3
"""
Auditory Mismatch Negativity (MMN) from the ERP CORE MMN dataset.

Per subject:
  MMN = deviant (70) minus standard (80) difference wave,
        mean amplitude over Fz / FCz / Cz in the 100-250 ms window, in microvolts.

Pipeline (standard ERP practice):
  read .set -> rename FP1/FP2 -> type EOG channels -> bipolar HEOG/VEOG
  -> montage -> 0.1-30 Hz zero-phase FIR band-pass -> mastoid-equivalent
  (P9/P10 average) reference -> resample to 256 Hz -> ICA (extended Infomax)
  with automatic EOG-component rejection -> epoch -0.2..0.5 s, baseline
  (-0.2, 0) -> 100 uV peak-to-peak artifact rejection -> average per condition
  -> difference wave -> mean amplitude in the measurement window.

Writes result.json next to this script. Run with no arguments.
"""

import json
import os
import sys
import traceback

import numpy as np
import pandas as pd

import mne

mne.set_log_level("ERROR")

# ----------------------------------------------------------------------------
# Configuration (all analysis choices are collected here)
# ----------------------------------------------------------------------------
DATA_ROOT = "/home/hou/mne_data/MNE-erpcoremmn2021-data"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(OUT_DIR, "result.json")

SUBJECTS = [f"sub-{i:03d}" for i in range(1, 41)]

EOG_RAW_CHANNELS = ["HEOG_left", "HEOG_right", "VEOG_lower"]
RENAME = {"FP1": "Fp1", "FP2": "Fp2"}

L_FREQ = 0.1              # high-pass (Hz), removes slow drift, keeps ERP shape
H_FREQ = 30.0             # low-pass (Hz), typical for auditory ERP components
RESAMPLE_SFREQ = 256.0    # Hz, ample for a <=30 Hz signal, speeds up ICA
REFERENCE = ["P9", "P10"] # mastoid-equivalent average reference (MMN standard)

TMIN, TMAX = -0.2, 0.5    # epoch limits (s)
BASELINE = (-0.2, 0.0)    # pre-stimulus baseline (s)
REJECT_PTP_EEG = 100e-6   # peak-to-peak epoch rejection threshold (V)

ICA_HP = 1.0              # high-pass for the ICA fitting copy (Hz)
ICA_N_COMPONENTS = 0.99   # keep components explaining 99% of variance
ICA_RANDOM_STATE = 97
ICA_MAX_ITER = 500
EOG_Z_THRESHOLDS = (3.0, 2.5, 2.0)  # progressively relaxed detection thresholds

MEAS_WIN = (0.100, 0.250)     # MMN measurement window (s)
ROI = ["Fz", "FCz", "Cz"]     # fronto-central ROI

EVENT_ID = {"standard": 80, "deviant": 70}   # 180 = first stream, excluded
MIN_EPOCHS_PER_CONDITION = 20  # subject-level exclusion criterion


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def load_raw(subject):
    """Load one subject's continuous EEG with channel types/montage set."""
    set_path = os.path.join(
        DATA_ROOT, subject, "eeg", f"{subject}_task-MMN_eeg.set"
    )
    raw = mne.io.read_raw_eeglab(set_path, preload=True)

    # Harmonise channel names with the 10-05 montage conventions.
    raw.rename_channels({k: v for k, v in RENAME.items() if k in raw.ch_names})

    # The three ocular channels are stored as EEG in the file.
    present_eog = [ch for ch in EOG_RAW_CHANNELS if ch in raw.ch_names]
    raw.set_channel_types({ch: "eog" for ch in present_eog})

    # Bipolar ocular derivations (ERP CORE convention):
    #   HEOG = HEOG_left - HEOG_right ; VEOG = VEOG_lower - Fp2
    # These give cleaner templates for automatic ICA component detection.
    try:
        if {"HEOG_left", "HEOG_right"}.issubset(set(raw.ch_names)):
            raw = mne.set_bipolar_reference(
                raw, anode="HEOG_left", cathode="HEOG_right",
                ch_name="HEOG", drop_refs=True, copy=False,
            )
        if {"VEOG_lower", "Fp2"}.issubset(set(raw.ch_names)):
            raw = mne.set_bipolar_reference(
                raw, anode="VEOG_lower", cathode="Fp2",
                ch_name="VEOG", drop_refs=False, copy=False,
            )
            raw.drop_channels(["VEOG_lower"])
        raw.set_channel_types(
            {ch: "eog" for ch in ("HEOG", "VEOG") if ch in raw.ch_names}
        )
    except Exception:
        # Fall back to the monopolar ocular channels if anything is missing.
        pass

    montage = mne.channels.make_standard_montage("standard_1005")
    raw.set_montage(montage, on_missing="ignore", match_case=False)
    return raw


def read_events(subject, sfreq, n_times):
    """Build an MNE events array from the BIDS *_events.tsv file."""
    tsv = os.path.join(
        DATA_ROOT, subject, "eeg", f"{subject}_task-MMN_events.tsv"
    )
    df = pd.read_csv(tsv, sep="\t")
    value = pd.to_numeric(df["value"], errors="coerce")
    onset = pd.to_numeric(df["onset"], errors="coerce")

    keep = value.isin(list(EVENT_ID.values())) & onset.notna()
    if "trial_type" in df.columns:
        keep &= df["trial_type"].astype(str).str.strip().eq("stimulus")

    onset = onset[keep].to_numpy(float)
    value = value[keep].to_numpy(int)

    samples = np.round(onset * sfreq).astype(int)

    # Keep only events with a full epoch inside the recording.
    lo = int(np.ceil(abs(TMIN) * sfreq)) + 1
    hi = n_times - int(np.ceil(TMAX * sfreq)) - 1
    ok = (samples >= lo) & (samples <= hi)
    samples, value = samples[ok], value[ok]

    events = np.column_stack(
        [samples, np.zeros_like(samples), value]
    ).astype(int)
    # Guard against duplicate sample indices (would break MNE).
    _, uniq = np.unique(events[:, 0], return_index=True)
    return events[np.sort(uniq)]


def run_ica(raw):
    """Fit ICA on a 1 Hz high-passed copy and remove ocular components."""
    raw_hp = raw.copy().filter(
        l_freq=ICA_HP, h_freq=None, picks="all", method="fir",
        phase="zero", fir_design="firwin",
    )
    ica = mne.preprocessing.ICA(
        n_components=ICA_N_COMPONENTS,
        method="infomax",
        fit_params=dict(extended=True),
        max_iter=ICA_MAX_ITER,
        random_state=ICA_RANDOM_STATE,
    )
    ica.fit(raw_hp, picks="eeg", decim=3)

    bads = []
    for thr in EOG_Z_THRESHOLDS:
        try:
            bads, _ = ica.find_bads_eog(raw_hp, threshold=thr)
        except Exception:
            bads = []
        if bads:
            break

    ica.exclude = sorted(set(bads))
    n_removed = len(ica.exclude)
    if n_removed:
        ica.apply(raw)
    del raw_hp
    return n_removed


def measure_mmn(evoked_diff):
    """Mean amplitude (uV) over the ROI within the measurement window."""
    picks = [evoked_diff.ch_names.index(ch) for ch in ROI]
    times = evoked_diff.times
    tol = 1e-9
    mask = (times >= MEAS_WIN[0] - tol) & (times <= MEAS_WIN[1] + tol)
    if not mask.any():
        raise RuntimeError("empty measurement window")
    return float(evoked_diff.data[picks][:, mask].mean() * 1e6)


# ----------------------------------------------------------------------------
# Per-subject analysis
# ----------------------------------------------------------------------------
def process_subject(subject):
    raw = load_raw(subject)

    missing = [ch for ch in ROI + REFERENCE if ch not in raw.ch_names]
    if missing:
        raise RuntimeError(f"missing channels: {missing}")

    sfreq_orig = raw.info["sfreq"]
    events = read_events(subject, sfreq_orig, raw.n_times)

    # Band-pass filter (zero-phase FIR) before referencing/epoching.
    raw.filter(
        l_freq=L_FREQ, h_freq=H_FREQ, picks="all", method="fir",
        phase="zero", fir_design="firwin",
    )

    # Mastoid-equivalent reference (average of P9 and P10).
    raw.set_eeg_reference(ref_channels=REFERENCE)

    # Downsample raw and events together (keeps event timing consistent).
    if RESAMPLE_SFREQ and RESAMPLE_SFREQ < raw.info["sfreq"]:
        raw, events = raw.resample(RESAMPLE_SFREQ, events=events)

    n_ica_removed = 0
    try:
        n_ica_removed = run_ica(raw)
    except Exception:
        n_ica_removed = -1  # ICA failed; rely on threshold rejection only

    epochs = mne.Epochs(
        raw, events, event_id=EVENT_ID, tmin=TMIN, tmax=TMAX,
        baseline=BASELINE, picks="eeg", reject=dict(eeg=REJECT_PTP_EEG),
        preload=True, proj=False, on_missing="raise",
    )

    n_std = len(epochs["standard"])
    n_dev = len(epochs["deviant"])
    if n_std < MIN_EPOCHS_PER_CONDITION or n_dev < MIN_EPOCHS_PER_CONDITION:
        raise RuntimeError(
            f"too few clean epochs (standard={n_std}, deviant={n_dev})"
        )

    ev_std = epochs["standard"].average()
    ev_dev = epochs["deviant"].average()
    diff = mne.combine_evoked([ev_dev, ev_std], weights=[1, -1])

    value = measure_mmn(diff)
    info = dict(
        n_standard=n_std, n_deviant=n_dev,
        n_ica_components_removed=n_ica_removed,
    )
    del raw, epochs
    return round(value, 3), info


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    per_subject = {}
    excluded = []
    reasons = {}
    trial_counts = {}

    for subject in SUBJECTS:
        try:
            value, info = process_subject(subject)
            per_subject[subject] = value
            trial_counts[subject] = info
            print(f"{subject}: MMN = {value:+.3f} uV  {info}", file=sys.stderr)
        except Exception as exc:
            excluded.append(subject)
            reasons[subject] = f"{type(exc).__name__}: {exc}"
            print(f"{subject}: EXCLUDED -- {reasons[subject]}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

    values = list(per_subject.values())
    grand_mean = round(float(np.mean(values)), 3) if values else None

    result = {
        "per_subject": per_subject,
        "excluded": excluded,
        "n_analyzed": len(per_subject),
        "grand_mean_uV": grand_mean,
        "choices": {
            "notes": (
                "MMN = deviant(70) minus standard(80) difference wave; mean "
                "amplitude across Fz/FCz/Cz over 100-250 ms. Preprocessing: "
                "0.1-30 Hz zero-phase FIR band-pass, mastoid-equivalent "
                "reference (average of P9/P10), resample to 256 Hz, extended "
                "Infomax ICA with automatic EOG-component removal (bipolar "
                "HEOG = HEOG_left-HEOG_right, VEOG = VEOG_lower-Fp2), epochs "
                "-200 to 500 ms baseline-corrected to -200..0 ms, 100 uV "
                "peak-to-peak artifact rejection on the 30 scalp channels. "
                "All standards (excluding the 180 first-stream trials) and "
                "all deviants are averaged; conditions are not trial-matched. "
                "Subjects with fewer than 20 clean epochs in either condition "
                "are excluded. Values in microvolts, rounded to 3 decimals; "
                "negative = expected mismatch negativity."
            ),
            "filter_hz": [L_FREQ, H_FREQ],
            "reference": REFERENCE,
            "resample_hz": RESAMPLE_SFREQ,
            "epoch_s": [TMIN, TMAX],
            "baseline_s": list(BASELINE),
            "reject_ptp_uV": REJECT_PTP_EEG * 1e6,
            "ica": {
                "method": "infomax (extended)",
                "n_components": ICA_N_COMPONENTS,
                "fit_highpass_hz": ICA_HP,
                "random_state": ICA_RANDOM_STATE,
                "eog_thresholds": list(EOG_Z_THRESHOLDS),
            },
            "measurement_window_s": list(MEAS_WIN),
            "roi": ROI,
            "min_epochs_per_condition": MIN_EPOCHS_PER_CONDITION,
            "exclusion_reasons": reasons,
            "trial_counts": trial_counts,
        },
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w") as fh:
        json.dump(result, fh, indent=2)
    print(
        f"\nWrote {OUT_JSON}: n={len(per_subject)}, "
        f"grand mean = {grand_mean} uV",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
