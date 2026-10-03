#!/usr/bin/env python3
"""
P3b (P300) from the ERP CORE P3 visual oddball dataset (sub-001 ... sub-020).

Measure
-------
Per subject: target-minus-standard difference wave, mean amplitude in the
300-500 ms window, averaged over Fz, Cz, Pz, CPz, reported in microvolts.

Processing choices (standard ERP-CORE-style practice; see CHOICES below)
------------------------------------------------------------------------
* channels    : FP1/FP2 renamed to Fp1/Fp2, HEOG_left/HEOG_right/VEOG_lower
                re-typed as EOG, standard_1005 montage attached.
* reference   : average of the P9/P10 mastoid-adjacent electrodes (the data are
                recorded against the Biosemi CMS reference, so an offline
                re-reference is mandatory). P9/P10 is the ERP CORE reference for
                the P3 component and keeps the midline P3b ROI maximal.
* filter      : zero-phase FIR band-pass 0.1 - 30 Hz (firwin) on EEG + EOG.
* epochs      : -200 to 800 ms, baseline corrected on the -200 to 0 ms window.
* conditions  : stimulus codes 11..55; TARGET iff tens == units, otherwise
                STANDARD. Response codes (201/202) ignored.
* artifacts   : peak-to-peak rejection of 100 uV on the 30 scalp EEG channels
                (no ICA, so blink-contaminated epochs are dropped outright,
                which matters because Fz sits in the ROI). Epochs overlapping
                BAD_ annotations are dropped as well.
* exclusion   : a subject is dropped if data are unreadable, a required channel
                is missing, or fewer than 10 clean epochs survive in either
                condition.

Run: python pipeline.py     (writes result.json next to this file)
"""

import json
import os
import sys
import traceback

import numpy as np
import mne

mne.set_log_level("ERROR")

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
DATA_ROOT = "/home/hou/mne_data/erpcore-P3"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(OUT_DIR, "result.json")

SUBJECTS = [f"sub-{i:03d}" for i in range(1, 21)]

ROI = ["Fz", "Cz", "Pz", "CPz"]
REF_CHANNELS = ["P9", "P10"]
EOG_CHANNELS = ["HEOG_left", "HEOG_right", "VEOG_lower"]
RENAME = {"FP1": "Fp1", "FP2": "Fp2"}

L_FREQ, H_FREQ = 0.1, 30.0
TMIN, TMAX = -0.2, 0.8
BASELINE = (-0.2, 0.0)
MEAS_WIN = (0.30, 0.50)          # P3b measurement window, seconds
REJECT = dict(eeg=100e-6)        # peak-to-peak, volts
MIN_EPOCHS = 10                  # per condition

EVENT_ID = {"standard": 1, "target": 2}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def read_events_tsv(path, sfreq, first_samp=0):
    """Parse a BIDS events.tsv into an MNE events array.

    `onset` is in seconds; `value` is a 2-digit code 11..55 whose TENS digit is
    the block's target letter and whose UNITS digit is the letter shown on this
    trial -> TARGET iff tens == units. Codes 201/202 are button presses and are
    ignored, as is anything that is not a 2-digit 1..5 / 1..5 combination.
    """
    with open(path, "r") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        i_onset, i_value = header.index("onset"), header.index("value")
        rows = []
        for line in fh:
            if not line.strip():
                continue
            fields = line.rstrip("\n").split("\t")
            try:
                onset = float(fields[i_onset])
                value = int(float(fields[i_value]))
            except (ValueError, IndexError):
                continue
            if not (11 <= value <= 55):
                continue
            tens, units = divmod(value, 10)
            if not (1 <= tens <= 5 and 1 <= units <= 5):
                continue
            code = EVENT_ID["target"] if tens == units else EVENT_ID["standard"]
            sample = int(round(onset * sfreq)) + int(first_samp)
            rows.append([sample, 0, code])

    if not rows:
        return np.empty((0, 3), dtype=int)
    events = np.array(rows, dtype=int)
    return events[np.argsort(events[:, 0])]


def prepare_raw(set_path):
    """Load, retype/rename channels, re-reference and band-pass filter."""
    raw = mne.io.read_raw_eeglab(set_path, preload=True)

    present = {old: new for old, new in RENAME.items() if old in raw.ch_names}
    if present:
        raw.rename_channels(present)

    eog_map = {ch: "eog" for ch in EOG_CHANNELS if ch in raw.ch_names}
    if eog_map:
        raw.set_channel_types(eog_map)

    try:
        raw.set_montage("standard_1005", match_case=False, on_missing="ignore")
    except Exception:
        pass  # montage is cosmetic here; the measure does not depend on it

    missing_ref = [ch for ch in REF_CHANNELS if ch not in raw.ch_names]
    if missing_ref:
        raise RuntimeError(f"missing reference channel(s): {missing_ref}")
    raw.set_eeg_reference(ref_channels=REF_CHANNELS)

    raw.filter(
        l_freq=L_FREQ,
        h_freq=H_FREQ,
        picks=["eeg", "eog"],
        method="fir",
        phase="zero",
        fir_design="firwin",
    )
    return raw


def mean_amplitude(evoked, roi, window):
    """Mean amplitude (uV) over `roi` channels within `window` (seconds)."""
    ev = evoked.copy().pick(roi)
    tmask = (ev.times >= window[0]) & (ev.times <= window[1])
    if not tmask.any():
        raise RuntimeError("measurement window falls outside the epoch")
    return float(ev.data[:, tmask].mean() * 1e6)


def process_subject(sub):
    """Return (amplitude_uV, diagnostics dict) for one subject."""
    eeg_dir = os.path.join(DATA_ROOT, sub, "eeg")
    set_path = os.path.join(eeg_dir, f"{sub}_task-P3_eeg.set")
    tsv_path = os.path.join(eeg_dir, f"{sub}_task-P3_events.tsv")
    for p in (set_path, tsv_path):
        if not os.path.exists(p):
            raise RuntimeError(f"file not found: {p}")

    raw = prepare_raw(set_path)

    missing_roi = [ch for ch in ROI if ch not in raw.ch_names]
    if missing_roi:
        raise RuntimeError(f"missing ROI channel(s): {missing_roi}")

    events = read_events_tsv(tsv_path, raw.info["sfreq"], raw.first_samp)
    if events.shape[0] == 0:
        raise RuntimeError("no stimulus events parsed from events.tsv")

    epochs = mne.Epochs(
        raw,
        events=events,
        event_id=EVENT_ID,
        tmin=TMIN,
        tmax=TMAX,
        baseline=BASELINE,
        picks=["eeg", "eog"],
        reject=REJECT,
        reject_by_annotation=True,
        preload=True,
        verbose=False,
    )

    n_target = len(epochs["target"])
    n_standard = len(epochs["standard"])
    n_presented = int(np.sum(events[:, 2] == EVENT_ID["target"])), int(
        np.sum(events[:, 2] == EVENT_ID["standard"])
    )
    if n_target < MIN_EPOCHS or n_standard < MIN_EPOCHS:
        raise RuntimeError(
            f"too few clean epochs (target={n_target}, standard={n_standard}, "
            f"minimum={MIN_EPOCHS})"
        )

    ev_target = epochs["target"].average()
    ev_standard = epochs["standard"].average()
    diff = mne.combine_evoked([ev_target, ev_standard], weights=[1, -1])

    amp = mean_amplitude(diff, ROI, MEAS_WIN)
    diag = {
        "n_target_kept": n_target,
        "n_standard_kept": n_standard,
        "n_target_presented": n_presented[0],
        "n_standard_presented": n_presented[1],
        "pct_epochs_rejected": round(
            100.0
            * (1.0 - (n_target + n_standard) / float(sum(n_presented))),
            2,
        ),
        "target_uV": round(mean_amplitude(ev_target, ROI, MEAS_WIN), 3),
        "standard_uV": round(mean_amplitude(ev_standard, ROI, MEAS_WIN), 3),
    }
    return amp, diag


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    per_subject = {}
    excluded = []
    diagnostics = {}

    for sub in SUBJECTS:
        try:
            amp, diag = process_subject(sub)
        except Exception as exc:
            print(f"[EXCLUDE] {sub}: {exc}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            excluded.append(sub)
            diagnostics[sub] = {"excluded_reason": str(exc)}
            continue
        per_subject[sub] = round(amp, 3)
        diagnostics[sub] = diag
        print(
            f"[OK] {sub}: P3b = {amp:8.3f} uV  "
            f"(target n={diag['n_target_kept']}, standard n={diag['n_standard_kept']}, "
            f"{diag['pct_epochs_rejected']}% rejected)"
        )

    values = list(per_subject.values())
    grand_mean = round(float(np.mean(values)), 3) if values else None

    choices = {
        "notes": (
            "ERP CORE P3 visual oddball. Per subject: target-minus-standard "
            "difference wave, mean amplitude 300-500 ms averaged over Fz, Cz, "
            "Pz, CPz, in uV. Reference: offline average of P9 and P10 (the "
            "recording reference is Biosemi CMS, so re-referencing is "
            "required; P9/P10 is the ERP CORE choice for the P3 and preserves "
            "the midline P3b). Band-pass 0.1-30 Hz zero-phase FIR (firwin) "
            "applied to EEG and EOG; FP1/FP2 renamed to Fp1/Fp2; "
            "HEOG_left/HEOG_right/VEOG_lower re-typed as EOG and excluded from "
            "the ERP; standard_1005 montage. Epochs -200 to 800 ms with "
            "-200 to 0 ms baseline correction. Trials taken from events.tsv "
            "onsets (seconds x 1024 Hz): codes 11-55, TARGET iff tens digit == "
            "units digit, otherwise STANDARD; response codes 201/202 ignored. "
            "No ICA: artifact control is peak-to-peak rejection at 100 uV on "
            "the 30 scalp EEG channels (drops blink-contaminated epochs, which "
            "matters because Fz is in the ROI), plus MNE's BAD_ annotation "
            "rejection. All trials are used regardless of behavioural accuracy. "
            "A subject is excluded only if the data are unreadable, a required "
            "channel is missing, or fewer than 10 clean epochs survive in "
            "either condition. Grand mean is the unweighted average across "
            "analysed subjects. Values rounded to 3 decimals."
        ),
        "reference": "average of P9 and P10",
        "filter_hz": [L_FREQ, H_FREQ],
        "filter_design": "zero-phase FIR, firwin",
        "epoch_s": [TMIN, TMAX],
        "baseline_s": list(BASELINE),
        "measurement_window_s": list(MEAS_WIN),
        "roi": ROI,
        "artifact_rejection": "peak-to-peak 100 uV on EEG channels, no ICA",
        "min_epochs_per_condition": MIN_EPOCHS,
        "condition_rule": "target iff tens digit == units digit of code 11-55",
        "sampling_rate_hz": 1024,
        "software": f"mne {mne.__version__}",
        "per_subject_diagnostics": diagnostics,
    }

    result = {
        "per_subject": per_subject,
        "excluded": excluded,
        "n_analyzed": len(per_subject),
        "grand_mean_uV": grand_mean,
        "choices": choices,
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w") as fh:
        json.dump(result, fh, indent=2)

    print(f"\nAnalysed {len(per_subject)}/{len(SUBJECTS)} subjects; "
          f"grand mean P3b = {grand_mean} uV")
    print(f"Wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
