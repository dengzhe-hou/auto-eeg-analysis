#!/usr/bin/env python3
"""
Auditory Mismatch Negativity (MMN) from the ERP CORE MMN dataset.

Per subject:
  * epoch the standard (value 80) and deviant (value 70) tones
  * average each condition, form the difference wave (deviant - standard)
  * report the mean amplitude of the difference wave over the fronto-central
    ROI (Fz, FCz, Cz) in the 100-250 ms window, in microvolts.

Standalone: `python pipeline.py`.  Writes result.json next to this file.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import traceback

import numpy as np
import mne

mne.set_log_level("ERROR")

# --------------------------------------------------------------------------- #
# Configuration (analysis choices)
# --------------------------------------------------------------------------- #
DATA_ROOT = "/home/hou/mne_data/MNE-erpcoremmn2021-data"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(OUT_DIR, "result.json")

SUBJECTS = [f"sub-{i:03d}" for i in range(1, 41)]

# Event codes in the *_events.tsv "value" column
CODE_STANDARD = 80
CODE_DEVIANT = 70
CODE_FIRST_STREAM = 180  # first tone of a stream -- not analysed

EOG_CHANNELS = ["HEOG_left", "HEOG_right", "VEOG_lower"]

# Pre-processing
L_FREQ = 0.1          # Hz, high-pass (ERP-standard for MMN)
H_FREQ = 30.0         # Hz, low-pass
REREF = "average"     # average reference over scalp EEG
DECIM = 4             # 1024 Hz -> 256 Hz (safe: data already low-passed at 30 Hz)

# Epoching
TMIN, TMAX = -0.2, 0.5
BASELINE = (-0.2, 0.0)

# Artifact rejection (peak-to-peak, Volts)
REJECT = dict(eeg=100e-6, eog=250e-6)
FLAT = dict(eeg=0.1e-6)

# Subject-level QC
MIN_EPOCHS_PER_COND = 20      # need at least this many clean trials per condition
MAX_REJECT_FRACTION = 0.50    # exclude if more than half of all trials are dropped

# Measurement
ROI = ["Fz", "FCz", "Cz"]
WIN = (0.100, 0.250)  # seconds

ROUND = 3


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def read_events_tsv(path):
    """Return list of (onset_seconds, value_int) from a BIDS *_events.tsv."""
    out = []
    with open(path, "r", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            onset = row.get("onset", "")
            value = row.get("value", "")
            if onset is None or value is None:
                continue
            onset = str(onset).strip()
            value = str(value).strip()
            if onset in ("", "n/a") or value in ("", "n/a"):
                continue
            try:
                out.append((float(onset), int(round(float(value)))))
            except ValueError:
                continue
    return out


def build_events_array(tsv_rows, sfreq, n_times, first_samp=0):
    """Convert (onset_s, value) rows into an MNE events array, keeping only the
    standard / deviant codes and dropping out-of-range or duplicated samples."""
    keep = {CODE_STANDARD, CODE_DEVIANT}
    rows, seen = [], set()
    for onset, value in tsv_rows:
        if value not in keep:
            continue  # e.g. CODE_FIRST_STREAM
        samp = int(round(onset * sfreq))
        if samp < 0 or samp >= n_times:
            continue
        if samp in seen:
            continue
        seen.add(samp)
        rows.append([samp + first_samp, 0, value])
    if not rows:
        return np.empty((0, 3), dtype=int)
    ev = np.array(rows, dtype=int)
    return ev[np.argsort(ev[:, 0])]


def prepare_raw(set_path):
    """Load, type, montage, filter and re-reference one subject's recording."""
    raw = mne.io.read_raw_eeglab(set_path, preload=True)

    # EOG channels are stored as EEG in the .set file -> retype them so they are
    # excluded from the average reference and from the scalp ROI/rejection.
    types = {ch: "eog" for ch in EOG_CHANNELS if ch in raw.ch_names}
    if types:
        raw.set_channel_types(types)

    # ERP CORE uses 'FP1'/'FP2'; the standard montages use 'Fp1'/'Fp2'.
    ren = {}
    for old, new in (("FP1", "Fp1"), ("FP2", "Fp2")):
        if old in raw.ch_names and new not in raw.ch_names:
            ren[old] = new
    if ren:
        raw.rename_channels(ren)

    try:
        raw.set_montage("standard_1005", match_case=False, on_missing="warn")
    except Exception:
        pass

    raw.filter(L_FREQ, H_FREQ, fir_design="firwin", phase="zero",
               picks=["eeg", "eog"])
    raw.set_eeg_reference(REREF, projection=False)
    return raw


def measure_mmn(evoked_diff):
    """Mean amplitude (uV) of the difference wave over ROI x time window."""
    picks = [ch for ch in ROI if ch in evoked_diff.ch_names]
    if not picks:
        raise RuntimeError(f"none of the ROI channels {ROI} are present")
    ev = evoked_diff.copy().pick(picks).crop(tmin=WIN[0], tmax=WIN[1])
    return float(ev.data.mean() * 1e6), picks


def process_subject(sub):
    """Return (value_uV, info_dict).  Raises on unrecoverable problems."""
    eeg_dir = os.path.join(DATA_ROOT, sub, "eeg")
    set_path = os.path.join(eeg_dir, f"{sub}_task-MMN_eeg.set")
    tsv_path = os.path.join(eeg_dir, f"{sub}_task-MMN_events.tsv")
    if not os.path.exists(set_path):
        raise FileNotFoundError(set_path)
    if not os.path.exists(tsv_path):
        raise FileNotFoundError(tsv_path)

    raw = prepare_raw(set_path)
    sfreq = raw.info["sfreq"]

    rows = read_events_tsv(tsv_path)
    events = build_events_array(rows, sfreq, raw.n_times, raw.first_samp)
    n_total = len(events)
    if n_total == 0:
        raise RuntimeError("no standard/deviant events found")

    event_id = {"standard": CODE_STANDARD, "deviant": CODE_DEVIANT}
    event_id = {k: v for k, v in event_id.items() if (events[:, 2] == v).any()}
    if len(event_id) < 2:
        raise RuntimeError("one of the two conditions is missing")

    epochs = mne.Epochs(
        raw, events, event_id=event_id,
        tmin=TMIN, tmax=TMAX, baseline=BASELINE,
        picks=["eeg", "eog"], reject=REJECT, flat=FLAT,
        decim=DECIM, preload=True, reject_by_annotation=True,
        proj=False, on_missing="ignore",
    )
    del raw

    n_std = len(epochs["standard"])
    n_dev = len(epochs["deviant"])
    n_kept = n_std + n_dev
    rej_frac = 1.0 - (n_kept / float(n_total)) if n_total else 1.0

    if n_std < MIN_EPOCHS_PER_COND or n_dev < MIN_EPOCHS_PER_COND:
        raise RuntimeError(
            f"too few clean epochs (standard={n_std}, deviant={n_dev}, "
            f"min={MIN_EPOCHS_PER_COND})"
        )
    if rej_frac > MAX_REJECT_FRACTION:
        raise RuntimeError(f"rejection rate {rej_frac:.2f} > {MAX_REJECT_FRACTION}")

    ev_std = epochs["standard"].average(picks="eeg")
    ev_dev = epochs["deviant"].average(picks="eeg")
    diff = mne.combine_evoked([ev_dev, ev_std], weights=[1, -1])

    value, picks = measure_mmn(diff)
    info = dict(n_standard=n_std, n_deviant=n_dev,
                n_events=n_total, reject_fraction=round(rej_frac, 4),
                roi_used=picks)
    return value, info


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    per_subject, excluded, details = {}, [], {}

    for sub in SUBJECTS:
        try:
            value, info = process_subject(sub)
            if not np.isfinite(value):
                raise RuntimeError("non-finite MMN amplitude")
            per_subject[sub] = round(value, ROUND)
            details[sub] = info
            print(f"[ok]   {sub}: {per_subject[sub]:+.3f} uV  "
                  f"(std={info['n_standard']}, dev={info['n_deviant']}, "
                  f"rej={info['reject_fraction']:.2%})", flush=True)
        except Exception as exc:  # noqa: BLE001
            excluded.append(sub)
            details[sub] = dict(error=f"{type(exc).__name__}: {exc}")
            print(f"[skip] {sub}: {type(exc).__name__}: {exc}", flush=True)
            traceback.print_exc(file=sys.stderr)

    vals = list(per_subject.values())
    grand = round(float(np.mean(vals)), ROUND) if vals else None

    result = {
        "per_subject": per_subject,
        "excluded": excluded,
        "n_analyzed": len(per_subject),
        "grand_mean_uV": grand,
        "choices": {
            "reference": "average reference over the 30 scalp EEG channels "
                         "(EOG channels retyped to 'eog' and excluded)",
            "filter": f"FIR band-pass {L_FREQ}-{H_FREQ} Hz, zero-phase, firwin",
            "resample": f"decim={DECIM} (1024 -> {1024 // DECIM} Hz) after low-pass",
            "montage": "standard_1005 (FP1/FP2 renamed to Fp1/Fp2)",
            "epoch": f"{TMIN} to {TMAX} s, baseline {BASELINE} s",
            "conditions": f"standard = value {CODE_STANDARD}, deviant = value "
                          f"{CODE_DEVIANT}; value {CODE_FIRST_STREAM} "
                          "(first tone of a stream) discarded; all standards used",
            "artifact_rejection": f"peak-to-peak reject EEG>{REJECT['eeg'] * 1e6:.0f} uV, "
                                  f"EOG>{REJECT['eog'] * 1e6:.0f} uV; "
                                  f"flat<{FLAT['eeg'] * 1e6:.1f} uV; "
                                  "no ICA / ocular correction",
            "difference_wave": "evoked(deviant) - evoked(standard), per subject",
            "measure": f"mean amplitude over {ROI} in "
                       f"{int(WIN[0] * 1000)}-{int(WIN[1] * 1000)} ms, in uV",
            "exclusion_rule": f"subject dropped if <{MIN_EPOCHS_PER_COND} clean "
                              f"epochs in either condition, if >{MAX_REJECT_FRACTION:.0%} "
                              "of trials are rejected, or if the recording cannot be read",
            "grand_mean": "unweighted mean of the per-subject MMN amplitudes",
            "notes": "Standard ERP-CORE-style MMN pipeline: 0.1-30 Hz band-pass, "
                     "average reference, -200..500 ms epochs baseline-corrected to "
                     "the 200 ms pre-stimulus interval, 100 uV peak-to-peak artifact "
                     "rejection, deviant-minus-standard difference wave, mean "
                     "amplitude across Fz/FCz/Cz in the 100-250 ms MMN window. "
                     "All values in microvolts, rounded to 3 decimals.",
        },
        "per_subject_details": details,
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w") as fh:
        json.dump(result, fh, indent=2)

    print(f"\nAnalyzed {len(per_subject)}/{len(SUBJECTS)} subjects; "
          f"grand mean = {grand} uV -> {OUT_JSON}")


if __name__ == "__main__":
    main()
