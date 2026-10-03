#!/usr/bin/env python3
"""
Auditory Mismatch Negativity (MMN) pipeline -- ERP CORE MMN (40 subjects).

Implements the recipe:
  1. Preprocess : 0.1-30 Hz zero-phase FIR bandpass, drop dedicated EOG channels,
                  resample to 256 Hz, RANSAC bad-channel detection -> interpolate ->
                  average reference over scalp channels.
  2. ICA        : NOT used. ERP CORE MMN is passive/clean, so the recipe's sanctioned
                  alternative (a plain +/-100 uV epoch reject) is used instead.
  3. Epoch      : -0.2 to 0.5 s, baseline (-0.2, 0), reject 100 uV, and require
                  >= 50 deviants and >= 150 standards after rejection.
  4. Measure    : per-subject deviant - standard difference wave, mean amplitude over
                  Fz/FCz/Cz in the 100-250 ms window, in microvolts.

Standalone: `python pipeline.py`. Writes result.json next to this file.
"""

import csv
import json
import os
import traceback
from pathlib import Path

import numpy as np
import mne

mne.set_log_level("ERROR")

# --------------------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------------------
DATA_ROOT = Path("/home/hou/mne_data/MNE-erpcoremmn2021-data")
OUT_DIR = Path(
    "/tmp/claude-1137/-home-hou-Research-auto-eeg-analysis/"
    "b4a153ed-22fa-4b6a-ad04-d134656fecf4/scratchpad/gen_scale/L1_8"
)
OUT_JSON = OUT_DIR / "result.json"

SUBJECTS = [f"sub-{i:03d}" for i in range(1, 41)]

# Dedicated EOG channels: typed as EEG in the .set file, so drop them by name.
EOG_NAMES = ["HEOG_left", "HEOG_right", "VEOG_lower"]

L_FREQ, H_FREQ = 0.1, 30.0          # zero-phase FIR bandpass
SFREQ_TARGET = 256.0                # >= 200 Hz; 1024 / 4 -> exact integer decimation
TMIN, TMAX = -0.2, 0.5
BASELINE = (-0.2, 0.0)
REJECT = dict(eeg=100e-6)           # peak-to-peak amplitude criterion
MEAS_CHANS = ["Fz", "FCz", "Cz"]
MEAS_WIN = (0.100, 0.250)
MIN_DEVIANTS, MIN_STANDARDS = 50, 150

CODE_STANDARD, CODE_DEVIANT, CODE_FIRST_STREAM = 80, 70, 180
EVENT_ID = {"standard": 1, "deviant": 2}

RANDOM_STATE = 42
MAX_BAD_FRACTION = 0.30             # sanity cap on RANSAC output before interpolation


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------
def read_events_tsv(path):
    """Return (onsets_sec, codes) for standard/deviant events only (180 excluded)."""
    onsets, codes = [], []
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            raw_onset = row.get("onset")
            raw_value = row.get("value")
            if raw_onset is None or raw_value is None:
                continue
            try:
                onset = float(raw_onset)
                code = int(round(float(raw_value)))
            except (TypeError, ValueError):
                continue  # 'n/a' or malformed rows
            if code == CODE_FIRST_STREAM:
                continue  # first stimulus of each stream -- excluded by the recipe
            if code in (CODE_STANDARD, CODE_DEVIANT):
                onsets.append(onset)
                codes.append(code)
    return np.asarray(onsets, dtype=float), np.asarray(codes, dtype=int)


def build_events(onsets_sec, codes, sfreq, n_times):
    """Convert TSV onsets (seconds) to an MNE events array at the given sampling rate."""
    samples = np.round(np.asarray(onsets_sec) * sfreq).astype(int)
    ids = np.where(np.asarray(codes) == CODE_DEVIANT,
                   EVENT_ID["deviant"], EVENT_ID["standard"])

    # Keep only events whose full epoch fits inside the recording.
    lo = int(np.ceil(abs(TMIN) * sfreq))
    hi = n_times - int(np.ceil(TMAX * sfreq)) - 1
    keep = (samples >= lo) & (samples <= hi)
    samples, ids = samples[keep], ids[keep]

    events = np.column_stack([samples, np.zeros_like(samples), ids]).astype(int)
    order = np.argsort(events[:, 0], kind="stable")
    events = events[order]

    # Drop exact-duplicate sample indices (MNE refuses them).
    if events.shape[0] > 1:
        uniq = np.concatenate([[True], np.diff(events[:, 0]) > 0])
        events = events[uniq]
    return events


def detect_bads_ransac(raw):
    """RANSAC bad-channel detection. pyprep preferred, autoreject as fallback."""
    try:
        from pyprep.find_noisy_channels import NoisyChannels

        nd = NoisyChannels(raw.copy(), do_detrend=True, random_state=RANDOM_STATE)
        nd.find_bad_by_ransac()
        return sorted(set(nd.bad_by_ransac)), "pyprep.NoisyChannels.find_bad_by_ransac"
    except Exception:
        pass

    try:
        from autoreject import Ransac

        tmp = mne.make_fixed_length_epochs(raw.copy(), duration=1.0, preload=True)
        rsc = Ransac(n_resample=50, min_channels=0.25, min_corr=0.75,
                     unbroken_time=0.4, random_state=RANDOM_STATE, n_jobs=1,
                     verbose=False)
        rsc.fit(tmp)
        return sorted(set(rsc.bad_chs_)), "autoreject.Ransac"
    except Exception:
        return [], "none (no RANSAC implementation available)"


def measure_mmn(evoked_diff):
    """Mean amplitude (uV) of the difference wave over MEAS_CHANS in MEAS_WIN."""
    picked = evoked_diff.copy().pick(MEAS_CHANS)
    picked.crop(tmin=MEAS_WIN[0], tmax=MEAS_WIN[1], include_tmax=True)
    return float(picked.data.mean() * 1e6)


# --------------------------------------------------------------------------------------
# Per-subject pipeline
# --------------------------------------------------------------------------------------
def process_subject(sub):
    """Return (value_uV, info_dict). value_uV is None when the subject is excluded."""
    info = {}
    set_path = DATA_ROOT / sub / "eeg" / f"{sub}_task-MMN_eeg.set"
    tsv_path = DATA_ROOT / sub / "eeg" / f"{sub}_task-MMN_events.tsv"
    if not set_path.exists():
        return None, {"reason": f"missing file: {set_path}"}
    if not tsv_path.exists():
        return None, {"reason": f"missing file: {tsv_path}"}

    # ---- load -------------------------------------------------------------------------
    raw = mne.io.read_raw_eeglab(str(set_path), preload=True)

    # ---- drop dedicated EOG channels BEFORE referencing --------------------------------
    to_drop = [ch for ch in EOG_NAMES if ch in raw.ch_names]
    if to_drop:
        raw.drop_channels(to_drop)
    info["dropped_eog"] = to_drop
    raw.pick("eeg")
    info["n_scalp_channels"] = len(raw.ch_names)

    # ---- montage ----------------------------------------------------------------------
    montage = mne.channels.make_standard_montage("standard_1020")
    raw.set_montage(montage, match_case=False, on_missing="warn")

    missing = [ch for ch in MEAS_CHANS if ch not in raw.ch_names]
    if missing:
        return None, {"reason": f"measurement channels absent: {missing}"}

    # ---- bandpass (zero-phase FIR) -----------------------------------------------------
    raw.filter(l_freq=L_FREQ, h_freq=H_FREQ, method="fir", phase="zero",
               fir_design="firwin", fir_window="hamming", n_jobs=1)

    # ---- resample ----------------------------------------------------------------------
    sfreq_orig = float(raw.info["sfreq"])
    if abs(sfreq_orig - SFREQ_TARGET) > 1e-6:
        raw.resample(SFREQ_TARGET, npad="auto")
    info["sfreq_orig"] = sfreq_orig
    info["sfreq_final"] = float(raw.info["sfreq"])

    # ---- RANSAC -> interpolate ---------------------------------------------------------
    bads, ransac_backend = detect_bads_ransac(raw)
    info["ransac_backend"] = ransac_backend
    max_bads = int(np.floor(MAX_BAD_FRACTION * len(raw.ch_names)))
    if len(bads) > max_bads:  # implausible detection -- do not interpolate everything
        info["ransac_bads_detected"] = bads
        info["ransac_bads_capped"] = True
        bads = []
    raw.info["bads"] = list(bads)
    info["bads"] = list(bads)
    if bads:
        raw.interpolate_bads(reset_bads=True, mode="accurate")

    # ---- average reference over scalp channels -----------------------------------------
    raw.set_eeg_reference("average", projection=False)

    # ---- events -------------------------------------------------------------------------
    onsets, codes = read_events_tsv(tsv_path)
    if onsets.size == 0:
        return None, {"reason": "no standard/deviant events in events.tsv"}
    events = build_events(onsets, codes, raw.info["sfreq"], raw.n_times)
    info["n_events_standard_raw"] = int(np.sum(events[:, 2] == EVENT_ID["standard"]))
    info["n_events_deviant_raw"] = int(np.sum(events[:, 2] == EVENT_ID["deviant"]))

    # ---- epoch + artifact rejection -----------------------------------------------------
    epochs = mne.Epochs(
        raw, events, event_id=EVENT_ID, tmin=TMIN, tmax=TMAX, baseline=BASELINE,
        reject=REJECT, flat=None, picks="eeg", preload=True, detrend=None,
        reject_by_annotation=False, on_missing="warn", verbose=False,
    )

    n_std = len(epochs["standard"])
    n_dev = len(epochs["deviant"])
    info["n_standard_kept"] = int(n_std)
    info["n_deviant_kept"] = int(n_dev)

    if n_dev < MIN_DEVIANTS or n_std < MIN_STANDARDS:
        info["reason"] = (f"too few trials after rejection "
                          f"(deviant={n_dev} < {MIN_DEVIANTS}? / "
                          f"standard={n_std} < {MIN_STANDARDS}?)")
        return None, info

    # ---- measure -------------------------------------------------------------------------
    ev_std = epochs["standard"].average()
    ev_dev = epochs["deviant"].average()
    diff = mne.combine_evoked([ev_dev, ev_std], weights=[1, -1])  # deviant - standard
    value = measure_mmn(diff)
    return value, info


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------
def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    per_subject = {}
    excluded = []
    details = {}

    for sub in SUBJECTS:
        try:
            value, info = process_subject(sub)
        except Exception as exc:  # keep the batch alive; record why the subject died
            value, info = None, {"reason": f"{type(exc).__name__}: {exc}",
                                 "traceback": traceback.format_exc(limit=3)}
        details[sub] = info
        if value is None or not np.isfinite(value):
            excluded.append(sub)
            print(f"[{sub}] EXCLUDED -- {info.get('reason', 'unknown')}", flush=True)
        else:
            per_subject[sub] = round(float(value), 3)
            print(f"[{sub}] MMN = {value:+.3f} uV "
                  f"(std={info.get('n_standard_kept')}, dev={info.get('n_deviant_kept')}, "
                  f"bads={info.get('bads')})", flush=True)

    values = np.asarray(list(per_subject.values()), dtype=float)
    grand_mean = round(float(values.mean()), 3) if values.size else None

    result = {
        "per_subject": per_subject,
        "excluded": excluded,
        "n_analyzed": len(per_subject),
        "grand_mean_uV": grand_mean,
        "choices": {
            "notes": (
                "Open choices resolved as follows. (a) ICA was NOT run: ERP CORE MMN is a "
                "clean passive paradigm, so the recipe's sanctioned alternative -- a plain "
                "100 uV epoch reject -- was used instead. (b) The 100 uV criterion is "
                "implemented as MNE's peak-to-peak rejection threshold, reject=dict(eeg=100e-6). "
                "(c) Resampling target is 256 Hz (exact 4x decimation from the native 1024 Hz, "
                "satisfying the >= 200 Hz floor). (d) Processing order follows the recipe "
                "literally: drop EOG -> montage -> 0.1-30 Hz zero-phase FIR (firwin/hamming, "
                "applied at the native 1024 Hz so the long 0.1 Hz highpass is not distorted by "
                "resampling) -> resample -> RANSAC -> interpolate -> average reference. "
                "(e) RANSAC via pyprep.NoisyChannels.find_bad_by_ransac with a fixed "
                "random_state=42; autoreject.Ransac is the fallback if pyprep is unavailable. "
                "A safety cap ignores RANSAC output flagging >30% of channels. "
                "(f) Difference wave = deviant - standard via mne.combine_evoked(weights=[1,-1]); "
                "amplitude = mean over Fz/FCz/Cz and over all samples in 100-250 ms inclusive. "
                "(g) Events with value 180 (first stimulus of a stream) are dropped; events whose "
                "epoch would extend past the recording edges are dropped. (h) Subjects that error "
                "out or fall below the >= 50 deviant / >= 150 standard floor are excluded, and the "
                "grand mean is the unweighted mean of the retained per-subject values."
            ),
            "filter": {"l_freq": L_FREQ, "h_freq": H_FREQ, "method": "fir",
                       "phase": "zero", "fir_design": "firwin", "fir_window": "hamming"},
            "resample_hz": SFREQ_TARGET,
            "reference": "average of scalp EEG channels (EOG dropped first)",
            "ica": "not used (100 uV epoch reject instead)",
            "reject_peak_to_peak_uV": 100.0,
            "epoch_window_s": [TMIN, TMAX],
            "baseline_s": list(BASELINE),
            "measure_channels": MEAS_CHANS,
            "measure_window_s": list(MEAS_WIN),
            "min_trials": {"deviant": MIN_DEVIANTS, "standard": MIN_STANDARDS},
            "montage": "standard_1020 (match_case=False)",
            "random_state": RANDOM_STATE,
            "mne_version": mne.__version__,
            "per_subject_details": details,
        },
    }

    with open(OUT_JSON, "w") as fh:
        json.dump(result, fh, indent=2)

    print(f"\nAnalyzed {len(per_subject)}/{len(SUBJECTS)} subjects; "
          f"grand mean = {grand_mean} uV; excluded = {excluded}")
    print(f"Wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
