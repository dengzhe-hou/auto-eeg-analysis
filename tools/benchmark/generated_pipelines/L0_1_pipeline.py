#!/usr/bin/env python
"""
Auditory Mismatch Negativity (MMN) from the ERP CORE MMN dataset.

For every subject sub-001 ... sub-040 the deviant-minus-standard difference
wave is computed and the MMN is quantified as the mean amplitude over
channels Fz, FCz, Cz in the 100-250 ms post-stimulus window (microvolts).

Pipeline (standard ERP practice, ERP CORE conventions where applicable):
  1. read EEGLAB .set
  2. type HEOG_left / HEOG_right / VEOG_lower as EOG, build bipolar
     HEOG (left-right) and VEOG (lower-Fp2) for ocular artifact detection
  3. rename FP1/FP2 -> Fp1/Fp2, attach standard_1005 montage
  4. zero-phase FIR band-pass 0.1-30 Hz
  5. re-reference EEG to the average of P9 / P10 (ERP CORE MMN reference)
  6. events from the BIDS *_events.tsv (value 80 = standard, 70 = deviant;
     value 180 = first-stream standards, excluded)
  7. epochs -200 to +500 ms, baseline -200 to 0 ms
  8. peak-to-peak artifact rejection: 100 uV on EEG, 150 uV on bipolar EOG
  9. average per condition, difference wave = deviant - standard
 10. mean amplitude over Fz/FCz/Cz x 100-250 ms

Run standalone:  python pipeline.py
"""

import csv
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
DATA_ROOT = "/home/hou/mne_data/MNE-erpcoremmn2021-data"
OUT_DIR = ("/tmp/claude-1137/-home-hou-Research-auto-eeg-analysis/"
           "b4a153ed-22fa-4b6a-ad04-d134656fecf4/scratchpad/gen_scale/L0_1")
OUT_JSON = os.path.join(OUT_DIR, "result.json")

SUBJECTS = [f"sub-{i:03d}" for i in range(1, 41)]

STANDARD_CODE = 80        # repeated ("standard") tone
DEVIANT_CODE = 70         # deviant tone
EXCLUDED_CODE = 180       # first stream of standards -> not analysed

L_FREQ, H_FREQ = 0.1, 30.0
REF_CHANNELS = ["P9", "P10"]      # mastoid-equivalent, ERP CORE MMN reference
TMIN, TMAX = -0.2, 0.5
BASELINE = (-0.2, 0.0)
REJECT = dict(eeg=100e-6, eog=150e-6)   # peak-to-peak

MEAS_CHANNELS = ["Fz", "FCz", "Cz"]
MEAS_TMIN, MEAS_TMAX = 0.100, 0.250

MIN_EPOCHS_PER_COND = 20          # subject-level inclusion criterion


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def read_events_tsv(path, sfreq, first_samp=0):
    """Return an MNE events array built from a BIDS *_events.tsv file.

    Only the two analysed trigger codes (standard / deviant) are kept.
    """
    events = []
    with open(path, "r", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            raw_value = (row.get("value") or "").strip()
            raw_onset = (row.get("onset") or "").strip()
            if raw_value in ("", "n/a") or raw_onset in ("", "n/a"):
                continue
            try:
                code = int(round(float(raw_value)))
                onset = float(raw_onset)
            except ValueError:
                continue
            if code not in (STANDARD_CODE, DEVIANT_CODE):
                # 180 = first-stream standards, 1 = STATUS/boundary, ...
                continue
            sample = int(round(onset * sfreq)) + int(first_samp)
            events.append([sample, 0, code])

    events = np.asarray(events, dtype=int)
    if events.size == 0:
        return events.reshape(0, 3)
    # chronological order + drop accidental duplicate samples (MNE requires it)
    events = events[np.argsort(events[:, 0])]
    keep = np.ones(len(events), dtype=bool)
    keep[1:] = np.diff(events[:, 0]) > 0
    return events[keep]


def preprocess_raw(set_path):
    """Load and preprocess one subject's continuous recording."""
    raw = mne.io.read_raw_eeglab(set_path, preload=True, verbose="ERROR")

    # --- EOG channels: the .set file types them as EEG ---------------------- #
    eog_map = {ch: "eog" for ch in ("HEOG_left", "HEOG_right", "VEOG_lower")
               if ch in raw.ch_names}
    if eog_map:
        raw.set_channel_types(eog_map)

    # --- bipolar ocular derivations (ERP CORE convention) ------------------- #
    anodes, cathodes, names = [], [], []
    if {"HEOG_left", "HEOG_right"}.issubset(raw.ch_names):
        anodes.append("HEOG_left")
        cathodes.append("HEOG_right")
        names.append("HEOG")
    if {"VEOG_lower", "FP2"}.issubset(raw.ch_names):
        anodes.append("VEOG_lower")
        cathodes.append("FP2")
        names.append("VEOG")
    if anodes:
        try:
            raw = mne.set_bipolar_reference(
                raw, anode=anodes, cathode=cathodes, ch_name=names,
                drop_refs=False, copy=False, verbose="ERROR")
            raw.set_channel_types({n: "eog" for n in names})
            # keep only the bipolar ocular channels
            drop = [c for c in ("HEOG_left", "HEOG_right", "VEOG_lower")
                    if c in raw.ch_names]
            if drop:
                raw.drop_channels(drop)
        except Exception:
            pass  # fall back to the monopolar EOG channels

    # --- montage ------------------------------------------------------------ #
    rename = {old: new for old, new in (("FP1", "Fp1"), ("FP2", "Fp2"))
              if old in raw.ch_names}
    if rename:
        raw.rename_channels(rename)
    try:
        raw.set_montage("standard_1005", match_case=False, on_missing="warn",
                        verbose="ERROR")
    except Exception:
        pass  # positions are not required for this analysis

    # --- filter ------------------------------------------------------------- #
    raw.filter(L_FREQ, H_FREQ, picks=["eeg", "eog"], method="fir",
               phase="zero", fir_design="firwin", verbose="ERROR")

    # --- reference ---------------------------------------------------------- #
    ref = [c for c in REF_CHANNELS if c in raw.ch_names]
    if len(ref) == len(REF_CHANNELS):
        raw.set_eeg_reference(ref, verbose="ERROR")
    else:                              # safety net: average reference
        raw.set_eeg_reference("average", verbose="ERROR")

    return raw


def mmn_for_subject(subject):
    """Return (mmn_uV, info_dict) for one subject."""
    eeg_dir = os.path.join(DATA_ROOT, subject, "eeg")
    set_path = os.path.join(eeg_dir, f"{subject}_task-MMN_eeg.set")
    tsv_path = os.path.join(eeg_dir, f"{subject}_task-MMN_events.tsv")
    if not (os.path.exists(set_path) and os.path.exists(tsv_path)):
        raise FileNotFoundError(f"missing data files for {subject}")

    raw = preprocess_raw(set_path)
    sfreq = raw.info["sfreq"]
    events = read_events_tsv(tsv_path, sfreq, raw.first_samp)
    if events.shape[0] == 0:
        raise RuntimeError("no usable events")

    event_id = {"standard": STANDARD_CODE, "deviant": DEVIANT_CODE}
    epochs = mne.Epochs(raw, events, event_id=event_id, tmin=TMIN, tmax=TMAX,
                        baseline=BASELINE, reject=REJECT, preload=True,
                        reject_by_annotation=False, on_missing="raise",
                        verbose="ERROR")

    n_std = len(epochs["standard"])
    n_dev = len(epochs["deviant"])
    if n_std < MIN_EPOCHS_PER_COND or n_dev < MIN_EPOCHS_PER_COND:
        raise RuntimeError(
            f"too few surviving epochs (standard={n_std}, deviant={n_dev})")

    ev_std = epochs["standard"].average()
    ev_dev = epochs["deviant"].average()
    diff = mne.combine_evoked([ev_dev, ev_std], weights=[1, -1])

    picks = [ch for ch in MEAS_CHANNELS if ch in diff.ch_names]
    if len(picks) != len(MEAS_CHANNELS):
        raise RuntimeError(f"missing measurement channels: "
                           f"{set(MEAS_CHANNELS) - set(picks)}")

    diff_picked = diff.copy().pick(picks)
    tmask = (diff_picked.times >= MEAS_TMIN) & (diff_picked.times <= MEAS_TMAX)
    mmn_uV = float(diff_picked.data[:, tmask].mean() * 1e6)

    info = dict(n_standard=int(n_std), n_deviant=int(n_dev),
                n_events=int(events.shape[0]))
    return mmn_uV, info


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    per_subject = {}
    excluded = []
    diagnostics = {}

    for subject in SUBJECTS:
        try:
            value, info = mmn_for_subject(subject)
            per_subject[subject] = round(value, 3)
            diagnostics[subject] = info
            print(f"{subject}: MMN = {value:+.3f} uV "
                  f"(std={info['n_standard']}, dev={info['n_deviant']})",
                  file=sys.stderr, flush=True)
        except Exception as exc:  # noqa: BLE001 - keep the batch running
            excluded.append(subject)
            diagnostics[subject] = {"error": f"{type(exc).__name__}: {exc}"}
            print(f"{subject}: EXCLUDED ({type(exc).__name__}: {exc})",
                  file=sys.stderr, flush=True)
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
                "ERP CORE MMN, EEGLAB .set read with mne.io.read_raw_eeglab. "
                "HEOG_left/HEOG_right/VEOG_lower re-typed as EOG and turned "
                "into bipolar HEOG (left-right) and VEOG (lower-Fp2) channels "
                "used only for artifact detection. FP1/FP2 renamed to "
                "Fp1/Fp2 and standard_1005 montage attached. Zero-phase FIR "
                "band-pass 0.1-30 Hz (firwin). EEG re-referenced to the "
                "average of P9 and P10, the mastoid-equivalent reference used "
                "by ERP CORE for MMN (average reference would shrink the "
                "frontocentral MMN because of its mastoid polarity "
                "inversion). Events taken from the BIDS *_events.tsv with "
                "sample = round(onset * 1024) + first_samp; value 80 = "
                "standard and 70 = deviant were analysed, value 180 "
                "(first-stream standards) and all other codes were dropped. "
                "All 80-coded standards were used (no post-deviant standard "
                "exclusion), matching the ERP CORE convention. Epochs -200 to "
                "+500 ms (shorter than the ~600 ms SOA, so no overlap with "
                "the next tone), baseline-corrected on -200 to 0 ms. "
                "Artifact handling by peak-to-peak rejection rather than ICA: "
                "100 uV on EEG and 150 uV on the bipolar EOG channels; no "
                "bad-channel interpolation, no resampling (1024 Hz kept). "
                "Difference wave = deviant-average minus standard-average "
                "(mne.combine_evoked weights [1, -1], i.e. an unweighted "
                "difference of the two condition ERPs). MMN = mean of the "
                "difference wave over Fz, FCz, Cz and over all samples with "
                "100 ms <= t <= 250 ms, converted from V to uV. A subject is "
                "excluded only if fewer than 20 artifact-free epochs remain "
                "in either condition or if the files cannot be processed."
            ),
            "filter_hz": [L_FREQ, H_FREQ],
            "reference": REF_CHANNELS,
            "epoch_s": [TMIN, TMAX],
            "baseline_s": list(BASELINE),
            "reject_peak_to_peak_V": {k: v for k, v in REJECT.items()},
            "measurement_channels": MEAS_CHANNELS,
            "measurement_window_s": [MEAS_TMIN, MEAS_TMAX],
            "standard_code": STANDARD_CODE,
            "deviant_code": DEVIANT_CODE,
            "dropped_codes": [EXCLUDED_CODE],
            "min_epochs_per_condition": MIN_EPOCHS_PER_COND,
            "per_subject_diagnostics": diagnostics,
        },
    }

    with open(OUT_JSON, "w") as fh:
        json.dump(result, fh, indent=2)

    print(f"\nWrote {OUT_JSON}", file=sys.stderr)
    print(f"n_analyzed = {result['n_analyzed']}, "
          f"grand_mean_uV = {result['grand_mean_uV']}", file=sys.stderr)


if __name__ == "__main__":
    main()
