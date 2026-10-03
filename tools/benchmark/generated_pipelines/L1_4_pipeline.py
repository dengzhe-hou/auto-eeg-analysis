#!/usr/bin/env python3
"""Auditory Mismatch Negativity (MMN) pipeline on the ERP CORE MMN dataset.

Recipe
------
1. Preprocess : 0.1-30 Hz zero-phase FIR bandpass, EOG channels dropped before
   referencing, average reference over scalp channels, RANSAC bad-channel
   detection -> interpolation -> re-reference, resample to 256 Hz (>= 200 Hz).
2. ICA        : skipped.  ERP CORE MMN is passive/clean, so the recipe's
   alternative (simple +/-100 uV epoch rejection) is used instead.
3. Epoch      : -0.2 to 0.5 s, baseline (-0.2, 0), +/-100 uV rejection,
   subjects with < 50 deviants or < 150 standards after rejection excluded.
4. Measure    : per-subject deviant - standard difference wave, mean amplitude
   over Fz/FCz/Cz in the 100-250 ms window, reported in uV.

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
from autoreject import Ransac

mne.set_log_level("ERROR")

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

DATA_ROOT = "/home/hou/mne_data/MNE-erpcoremmn2021-data"
OUT_DIR = (
    "/tmp/claude-1137/-home-hou-Research-auto-eeg-analysis/"
    "b4a153ed-22fa-4b6a-ad04-d134656fecf4/scratchpad/gen_scale/L1_4"
)
OUT_JSON = os.path.join(OUT_DIR, "result.json")

SUBJECTS = [f"sub-{i:03d}" for i in range(1, 41)]

# The .set file types the three EOG electrodes as EEG -> drop them by name so
# they never enter the average reference.
EOG_NAMES = ["HEOG_left", "HEOG_right", "VEOG_lower"]

# events.tsv `value` codes
CODE_STANDARD = 80
CODE_DEVIANT = 70
CODE_FIRST_STREAM = 180  # excluded

EVENT_ID = {"standard": 1, "deviant": 2}
CODE_TO_ID = {CODE_STANDARD: EVENT_ID["standard"], CODE_DEVIANT: EVENT_ID["deviant"]}

L_FREQ, H_FREQ = 0.1, 30.0
RESAMPLE_SFREQ = 256.0  # 1024 / 4, integer decimation, >= 200 Hz
TMIN, TMAX = -0.2, 0.5
BASELINE = (-0.2, 0.0)
REJECT = dict(eeg=100e-6)  # peak-to-peak, MNE convention

MIN_DEVIANTS = 50
MIN_STANDARDS = 150

ROI = ["Fz", "FCz", "Cz"]
WIN_TMIN, WIN_TMAX = 0.100, 0.250

RANSAC_RANDOM_STATE = 42
RANSAC_N_RESAMPLE = 50
RANSAC_MIN_CORR = 0.75

NOTES = (
    "ICA skipped (recipe allows it for clean passive data): artifact control is "
    "the +/-100 uV epoch rejection only. Rejection threshold applied as MNE's "
    "peak-to-peak criterion reject=dict(eeg=100e-6). Bandpass 0.1-30 Hz "
    "zero-phase FIR (firwin, 'auto' transition bands) applied at the native "
    "1024 Hz, then resampled to 256 Hz (integer decimation, >= 200 Hz). EOG "
    "channels (HEOG_left/HEOG_right/VEOG_lower) dropped before any referencing. "
    "Order: filter -> resample -> average reference -> RANSAC (autoreject, "
    "n_resample=50, min_corr=0.75, random_state=42) on unrejected task epochs "
    "-> interpolate flagged channels on the continuous data -> re-apply average "
    "reference -> final epoching. Epochs -0.2 to 0.5 s, baseline (-0.2, 0). "
    "Difference wave = deviant - standard via mne.combine_evoked(weights=[1,-1]); "
    "measure = mean amplitude across Fz/FCz/Cz over 100-250 ms (window edges "
    "snapped to the nearest samples, inclusive), converted to uV. Subjects with "
    "< 50 deviants or < 150 standards surviving rejection are excluded, as are "
    "subjects whose data fail to load/process. grand_mean_uV is the unweighted "
    "mean of the retained per-subject values. All values rounded to 3 decimals."
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def read_events_tsv(path):
    """Read a BIDS *_events.tsv and return an (n, 2) array of (onset_s, code).

    Only stimulus rows carrying value 80 (standard) or 70 (deviant) are kept;
    value 180 (first-stream) and non-stimulus rows (e.g. STATUS) are dropped.
    """
    onsets, codes = [], []
    with open(path, "r", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            raw_value = (row.get("value") or "").strip()
            try:
                value = int(float(raw_value))
            except (TypeError, ValueError):
                continue
            if value not in CODE_TO_ID:
                continue  # 180 first-stream, or anything else
            raw_onset = (row.get("onset") or "").strip()
            try:
                onset = float(raw_onset)
            except (TypeError, ValueError):
                continue
            onsets.append(onset)
            codes.append(value)
    if not onsets:
        raise RuntimeError(f"no standard/deviant events found in {path}")
    order = np.argsort(np.asarray(onsets, dtype=float), kind="stable")
    return np.asarray(onsets, dtype=float)[order], np.asarray(codes, dtype=int)[order]


def build_events_array(onsets_s, codes, sfreq, first_samp):
    """Convert onsets in seconds to an MNE events array at `sfreq`."""
    samples = np.round(np.asarray(onsets_s) * sfreq).astype(int) + int(first_samp)
    ids = np.array([CODE_TO_ID[c] for c in codes], dtype=int)
    events = np.column_stack([samples, np.zeros_like(samples), ids]).astype(int)
    return events


def load_raw(subject):
    """Read the .set file, drop EOG channels, attach the standard_1020 montage."""
    eeg_dir = os.path.join(DATA_ROOT, subject, "eeg")
    set_path = os.path.join(eeg_dir, f"{subject}_task-MMN_eeg.set")
    events_path = os.path.join(eeg_dir, f"{subject}_task-MMN_events.tsv")
    for p in (set_path, events_path):
        if not os.path.isfile(p):
            raise FileNotFoundError(p)

    raw = mne.io.read_raw_eeglab(set_path, preload=True)

    # The dataset types the EOG electrodes as EEG; remove them by name so they
    # are excluded from the average reference and from RANSAC.
    to_drop = [ch for ch in EOG_NAMES if ch in raw.ch_names]
    if to_drop:
        raw.drop_channels(to_drop)

    # Any residual non-EEG channels are not wanted either.
    raw.pick("eeg")

    montage = mne.channels.make_standard_montage("standard_1020")
    raw.set_montage(montage, match_case=False, on_missing="raise")

    onsets_s, codes = read_events_tsv(events_path)
    return raw, onsets_s, codes


def window_mean_uv(evoked, ch_names, tmin, tmax):
    """Mean amplitude (uV) across `ch_names` over [tmin, tmax] (inclusive)."""
    ev = evoked.copy().pick(ch_names)
    # Re-order defensively so the ROI is exactly the requested set.
    ev.reorder_channels(list(ch_names))
    times = ev.times
    i0 = int(np.argmin(np.abs(times - tmin)))
    i1 = int(np.argmin(np.abs(times - tmax)))
    if i1 < i0:
        i0, i1 = i1, i0
    data = ev.data[:, i0 : i1 + 1]  # volts
    return float(np.mean(data) * 1e6)


# --------------------------------------------------------------------------- #
# Per-subject pipeline
# --------------------------------------------------------------------------- #


def process_subject(subject):
    """Run the full recipe for one subject.

    Returns
    -------
    dict with keys: ok (bool), value (float|None), reason (str),
    n_standard, n_deviant, bads (list of interpolated channel names).
    """
    raw, onsets_s, codes = load_raw(subject)

    # --- 1. bandpass 0.1-30 Hz, zero-phase FIR -----------------------------
    raw.filter(
        l_freq=L_FREQ,
        h_freq=H_FREQ,
        method="fir",
        phase="zero",
        fir_design="firwin",
        fir_window="hamming",
        l_trans_bandwidth="auto",
        h_trans_bandwidth="auto",
        n_jobs=1,
    )

    # --- resample (>= 200 Hz), carrying the events along -------------------
    events = build_events_array(onsets_s, codes, raw.info["sfreq"], raw.first_samp)
    if abs(raw.info["sfreq"] - RESAMPLE_SFREQ) > 1e-6:
        raw, events = raw.resample(RESAMPLE_SFREQ, events=events, n_jobs=1)

    # --- 2. average reference over scalp channels --------------------------
    raw.set_eeg_reference("average", projection=False)

    # --- 3. RANSAC bad-channel detection -> interpolate -> re-reference -----
    #  RANSAC operates on epochs, so build a provisional (unrejected) epoching.
    epochs_for_ransac = mne.Epochs(
        raw,
        events,
        event_id=EVENT_ID,
        tmin=TMIN,
        tmax=TMAX,
        baseline=BASELINE,
        reject=None,
        preload=True,
        proj=False,
        on_missing="warn",
    )

    bads = []
    if len(epochs_for_ransac) > 0:
        try:
            ransac = Ransac(
                n_resample=RANSAC_N_RESAMPLE,
                min_corr=RANSAC_MIN_CORR,
                random_state=RANSAC_RANDOM_STATE,
                n_jobs=1,
                verbose=False,
            )
            ransac.fit(epochs_for_ransac)
            bads = sorted(set(ransac.bad_chs_))
        except Exception:  # RANSAC is a convenience step, never fatal
            sys.stderr.write(
                f"[{subject}] RANSAC failed, continuing with no bad channels:\n"
                + traceback.format_exc()
            )
            bads = []
    del epochs_for_ransac

    if bads:
        raw.info["bads"] = list(bads)
        raw.interpolate_bads(reset_bads=True, mode="accurate")
        # re-reference after interpolation
        raw.set_eeg_reference("average", projection=False)

    # --- 4. final epoching with +/-100 uV rejection ------------------------
    epochs = mne.Epochs(
        raw,
        events,
        event_id=EVENT_ID,
        tmin=TMIN,
        tmax=TMAX,
        baseline=BASELINE,
        reject=REJECT,
        preload=True,
        proj=False,
        on_missing="warn",
    )

    n_standard = len(epochs["standard"])
    n_deviant = len(epochs["deviant"])

    if n_deviant < MIN_DEVIANTS or n_standard < MIN_STANDARDS:
        failures = []
        if n_deviant < MIN_DEVIANTS:
            failures.append(f"deviants={n_deviant} < {MIN_DEVIANTS}")
        if n_standard < MIN_STANDARDS:
            failures.append(f"standards={n_standard} < {MIN_STANDARDS}")
        return dict(
            ok=False,
            value=None,
            reason="too few trials after rejection (" + "; ".join(failures) + ")",
            n_standard=n_standard,
            n_deviant=n_deviant,
            bads=bads,
        )

    missing_roi = [ch for ch in ROI if ch not in epochs.ch_names]
    if missing_roi:
        return dict(
            ok=False,
            value=None,
            reason=f"missing ROI channel(s): {missing_roi}",
            n_standard=n_standard,
            n_deviant=n_deviant,
            bads=bads,
        )

    # --- 5. deviant - standard difference wave, mean amplitude -------------
    ev_std = epochs["standard"].average()
    ev_dev = epochs["deviant"].average()
    diff = mne.combine_evoked([ev_dev, ev_std], weights=[1, -1])

    value = window_mean_uv(diff, ROI, WIN_TMIN, WIN_TMAX)

    return dict(
        ok=True,
        value=value,
        reason="",
        n_standard=n_standard,
        n_deviant=n_deviant,
        bads=bads,
    )


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    per_subject = {}
    excluded = []
    reasons = {}
    trial_counts = {}
    interpolated = {}

    for subject in SUBJECTS:
        try:
            res = process_subject(subject)
        except Exception as exc:
            sys.stderr.write(f"[{subject}] FAILED: {exc!r}\n")
            sys.stderr.write(traceback.format_exc())
            excluded.append(subject)
            reasons[subject] = f"processing error: {type(exc).__name__}: {exc}"
            continue

        trial_counts[subject] = dict(
            standard=int(res["n_standard"]), deviant=int(res["n_deviant"])
        )
        if res["bads"]:
            interpolated[subject] = res["bads"]

        if res["ok"]:
            per_subject[subject] = round(float(res["value"]), 3)
            print(
                f"[{subject}] MMN = {per_subject[subject]:+.3f} uV  "
                f"(std={res['n_standard']}, dev={res['n_deviant']}, "
                f"interp={res['bads']})",
                flush=True,
            )
        else:
            excluded.append(subject)
            reasons[subject] = res["reason"]
            print(f"[{subject}] EXCLUDED: {res['reason']}", flush=True)

    values = np.array(list(per_subject.values()), dtype=float)
    grand_mean = round(float(values.mean()), 3) if values.size else None

    out = {
        "per_subject": per_subject,
        "excluded": excluded,
        "n_analyzed": len(per_subject),
        "grand_mean_uV": grand_mean,
        "choices": {
            "notes": NOTES,
            "bandpass_hz": [L_FREQ, H_FREQ],
            "filter": "zero-phase FIR (firwin, hamming, 'auto' transition bands)",
            "resample_hz": RESAMPLE_SFREQ,
            "reference": "average over 30 scalp EEG channels (EOG dropped first)",
            "eog_channels_dropped": EOG_NAMES,
            "montage": "standard_1020 (match_case=False)",
            "ica": "not used",
            "bad_channels": (
                "autoreject RANSAC on task epochs, interpolated then "
                "re-referenced"
            ),
            "ransac": {
                "n_resample": RANSAC_N_RESAMPLE,
                "min_corr": RANSAC_MIN_CORR,
                "random_state": RANSAC_RANDOM_STATE,
            },
            "epoch_s": [TMIN, TMAX],
            "baseline_s": list(BASELINE),
            "rejection": "peak-to-peak 100 uV on EEG (reject=dict(eeg=100e-6))",
            "min_trials": {"deviant": MIN_DEVIANTS, "standard": MIN_STANDARDS},
            "roi": ROI,
            "measure_window_s": [WIN_TMIN, WIN_TMAX],
            "measure": "mean amplitude of (deviant - standard) difference wave, uV",
            "exclusion_reasons": reasons,
            "trial_counts": trial_counts,
            "interpolated_channels": interpolated,
        },
    }

    with open(OUT_JSON, "w") as fh:
        json.dump(out, fh, indent=2)

    print(
        f"\nAnalyzed {out['n_analyzed']}/{len(SUBJECTS)} subjects; "
        f"grand mean = {grand_mean} uV; excluded = {excluded}",
        flush=True,
    )
    print(f"Wrote {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
