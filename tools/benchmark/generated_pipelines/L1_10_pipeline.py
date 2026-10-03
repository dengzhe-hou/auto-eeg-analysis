#!/usr/bin/env python3
"""
Auditory Mismatch Negativity (MMN) pipeline -- ERP CORE MMN (sub-001 .. sub-040).

Implements the recipe:
  1. Preprocess : 0.1-30 Hz zero-phase FIR, drop EOG, RANSAC bad channels ->
                  interpolate -> average reference of scalp channels, resample to 256 Hz.
  2. ICA        : not used (clean passive paradigm) -- a +/-100 uV epoch reject is used
                  instead, as the recipe explicitly permits for ERP CORE MMN.
  3. Epoch      : -0.2 to 0.5 s, baseline (-0.2, 0), reject 100 uV, require
                  >= 50 deviants and >= 150 standards after rejection.
  4. Measure    : deviant - standard difference wave, mean amplitude over
                  Fz/FCz/Cz in 100-250 ms, in uV.

Writes result.json next to this script. Standalone: python pipeline.py
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

# ----------------------------------------------------------------------------- config
DATA_ROOT = "/home/hou/mne_data/MNE-erpcoremmn2021-data"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(OUT_DIR, "result.json")

SUBJECTS = [f"sub-{i:03d}" for i in range(1, 41)]

EOG_NAMES = ["HEOG_left", "HEOG_right", "VEOG_lower"]

L_FREQ, H_FREQ = 0.1, 30.0
RESAMPLE_SFREQ = 256.0                 # 1024 / 4, exact decimation, >= 200 Hz
TMIN, TMAX = -0.2, 0.5
BASELINE = (-0.2, 0.0)
REJECT = dict(eeg=100e-6)              # MNE peak-to-peak criterion, 100 uV
EVENT_ID = {"standard": 80, "deviant": 70}
MIN_DEVIANTS, MIN_STANDARDS = 50, 150
ROI = ["Fz", "FCz", "Cz"]
WIN = (0.100, 0.250)
RANDOM_STATE = 42


# ----------------------------------------------------------------------------- helpers
def read_events_tsv(path, sfreq, first_samp=0):
    """Read the BIDS events.tsv and build an MNE events array.

    `onset` is in seconds; `value` is 80 (standard) / 70 (deviant) / 180 (first
    stimulus of a stream -- excluded).
    """
    keep = set(EVENT_ID.values())
    rows = []
    with open(path, "r", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            raw_val = row.get("value", row.get("trial_type", ""))
            raw_onset = row.get("onset", "")
            if raw_val is None or raw_onset is None:
                continue
            raw_val = str(raw_val).strip()
            raw_onset = str(raw_onset).strip()
            if raw_val in ("", "n/a") or raw_onset in ("", "n/a"):
                continue
            try:
                code = int(round(float(raw_val)))
                onset = float(raw_onset)
            except ValueError:
                continue
            if code not in keep:
                continue
            samp = int(round(onset * sfreq)) + int(first_samp)
            rows.append((samp, 0, code))

    rows.sort(key=lambda r: r[0])
    # guard against duplicated sample indices after resampling
    deduped, seen = [], set()
    for samp, prev, code in rows:
        if samp in seen:
            continue
        seen.add(samp)
        deduped.append((samp, prev, code))

    if not deduped:
        return np.empty((0, 3), dtype=int)
    return np.array(deduped, dtype=int)


def detect_bad_channels(raw):
    """RANSAC bad-channel detection.

    Preference order: pyprep's NoisyChannels.find_bad_by_ransac (operates on the
    continuous data), then autoreject's Ransac (operates on fixed-length epochs).
    Returns (bads, backend_name).
    """
    # -- pyprep
    try:
        from pyprep.find_noisy_channels import NoisyChannels

        nc = NoisyChannels(raw.copy(), do_detrend=False, random_state=RANDOM_STATE)
        nc.find_bad_by_ransac(channel_wise=False)
        return sorted(set(nc.bad_by_ransac)), "pyprep.NoisyChannels.find_bad_by_ransac"
    except Exception:
        pass

    # -- autoreject
    try:
        from autoreject import Ransac

        tmp = mne.make_fixed_length_epochs(raw.copy(), duration=1.0, preload=True)
        rsc = Ransac(n_jobs=1, random_state=RANDOM_STATE, verbose=False)
        rsc.fit(tmp)
        return sorted(set(rsc.bad_chs_)), "autoreject.Ransac (1 s fixed-length epochs)"
    except Exception:
        pass

    return [], "unavailable (no RANSAC backend installed; no channels interpolated)"


def resolve_roi(ch_names):
    """Case-insensitive resolution of the Fz/FCz/Cz ROI."""
    lut = {c.lower(): c for c in ch_names}
    return [lut[name.lower()] for name in ROI if name.lower() in lut]


# ----------------------------------------------------------------------------- subject
def process_subject(sub):
    """Return (value_uV, info_dict). Raises RuntimeError if the subject must be excluded."""
    set_path = os.path.join(DATA_ROOT, sub, "eeg", f"{sub}_task-MMN_eeg.set")
    tsv_path = os.path.join(DATA_ROOT, sub, "eeg", f"{sub}_task-MMN_events.tsv")
    if not os.path.exists(set_path):
        raise RuntimeError(f"missing raw file: {set_path}")
    if not os.path.exists(tsv_path):
        raise RuntimeError(f"missing events file: {tsv_path}")

    raw = mne.io.read_raw_eeglab(set_path, preload=True)

    # 1a. drop the dedicated EOG channels *before* referencing so they never enter
    #     the average reference (they are typed as EEG in the .set file)
    drop = [ch for ch in EOG_NAMES if ch in raw.ch_names]
    if drop:
        raw.drop_channels(drop)
    raw.pick("eeg")

    # 1b. montage (ERP CORE uses 'FP1'/'FP2' -> match_case=False)
    raw.set_montage("standard_1020", match_case=False, on_missing="warn")

    # 1c. bandpass 0.1-30 Hz, zero-phase FIR (filter before resampling)
    raw.filter(
        l_freq=L_FREQ,
        h_freq=H_FREQ,
        method="fir",
        phase="zero",
        fir_design="firwin",
        fir_window="hamming",
        n_jobs=1,
    )

    # 1d. resample to 256 Hz (>= 200 Hz). Events are rebuilt from the TSV onsets
    #     (in seconds) afterwards, so no event jitter is introduced.
    if raw.info["sfreq"] > RESAMPLE_SFREQ:
        raw.resample(RESAMPLE_SFREQ, npad="auto")

    # 1e. RANSAC -> interpolate -> re-reference
    bads, ransac_backend = detect_bad_channels(raw)
    raw.info["bads"] = bads
    n_interp = len(bads)
    if bads:
        raw.interpolate_bads(reset_bads=True, mode="accurate")

    raw.set_eeg_reference("average", projection=False)

    # 3. epoching
    events = read_events_tsv(tsv_path, raw.info["sfreq"], raw.first_samp)
    if events.shape[0] == 0:
        raise RuntimeError("no standard/deviant events found")

    epochs = mne.Epochs(
        raw,
        events,
        event_id=EVENT_ID,
        tmin=TMIN,
        tmax=TMAX,
        baseline=BASELINE,
        reject=REJECT,
        proj=False,
        preload=True,
        on_missing="ignore",
        reject_by_annotation=True,
    )
    epochs.drop_bad()

    n_std = len(epochs["standard"])
    n_dev = len(epochs["deviant"])
    if n_dev < MIN_DEVIANTS or n_std < MIN_STANDARDS:
        raise RuntimeError(
            f"too few surviving trials (deviants={n_dev} < {MIN_DEVIANTS} "
            f"or standards={n_std} < {MIN_STANDARDS})"
        )

    # 4. deviant - standard difference wave, mean amplitude over Fz/FCz/Cz, 100-250 ms
    ev_std = epochs["standard"].average()
    ev_dev = epochs["deviant"].average()
    diff = mne.combine_evoked([ev_dev, ev_std], weights=[1, -1])

    picks = resolve_roi(diff.ch_names)
    if not picks:
        raise RuntimeError(f"ROI channels {ROI} not found in {diff.ch_names}")

    seg = diff.copy().pick(picks).crop(tmin=WIN[0], tmax=WIN[1])
    value_uV = float(seg.data.mean() * 1e6)

    info = dict(
        n_standards=int(n_std),
        n_deviants=int(n_dev),
        n_interpolated=int(n_interp),
        bads=list(bads),
        roi=picks,
        ransac_backend=ransac_backend,
        sfreq=float(raw.info["sfreq"]),
    )
    return value_uV, info


# ----------------------------------------------------------------------------- main
def main():
    per_subject = {}
    excluded = []
    reasons = {}
    details = {}
    backends = set()

    for sub in SUBJECTS:
        try:
            value_uV, info = process_subject(sub)
        except Exception as exc:  # excluded subject (missing data, too few trials, error)
            excluded.append(sub)
            reasons[sub] = f"{type(exc).__name__}: {exc}"
            print(f"[{sub}] EXCLUDED -- {reasons[sub]}", file=sys.stderr)
            if not isinstance(exc, RuntimeError):
                traceback.print_exc(file=sys.stderr)
            continue

        per_subject[sub] = round(value_uV, 3)
        details[sub] = info
        backends.add(info["ransac_backend"])
        print(
            f"[{sub}] {value_uV:+.3f} uV  "
            f"(std={info['n_standards']}, dev={info['n_deviants']}, "
            f"interp={info['n_interpolated']})",
            file=sys.stderr,
        )

    values = list(per_subject.values())
    grand_mean = round(float(np.mean(values)), 3) if values else None

    notes = (
        "ERP CORE MMN. Order: read .set -> drop HEOG_left/HEOG_right/VEOG_lower by name "
        "(before any referencing) -> standard_1020 montage (match_case=False) -> "
        "0.1-30 Hz zero-phase FIR (firwin/hamming, phase='zero') -> resample 1024->256 Hz "
        "(exact 4x decimation, >=200 Hz) -> RANSAC bad-channel detection -> "
        "interpolate (spherical splines) -> average reference over the 30 scalp EEG "
        "channels. No ICA: the recipe permits a plain +/-100 uV epoch reject for this "
        "clean passive paradigm, so that is what is used. Epochs -0.2..0.5 s, baseline "
        "(-0.2, 0), rejection via MNE's peak-to-peak criterion reject=dict(eeg=100e-6). "
        "Events come from the events.tsv 'value' column (80=standard, 70=deviant; "
        "180=first-stream excluded), with onsets in seconds converted to samples at the "
        "post-resampling rate, so resampling introduces no event jitter. Subjects with "
        "<50 deviants or <150 standards surviving rejection (or with unreadable data) "
        "are excluded. Measure: deviant-minus-standard evoked difference "
        "(mne.combine_evoked weights [1, -1]), mean amplitude over Fz/FCz/Cz across "
        "100-250 ms inclusive, in uV, rounded to 3 dp."
    )

    result = {
        "per_subject": per_subject,
        "excluded": excluded,
        "n_analyzed": len(per_subject),
        "grand_mean_uV": grand_mean,
        "choices": {
            "notes": notes,
            "filter": "0.1-30 Hz FIR, firwin design, hamming window, phase='zero' (zero-phase)",
            "resample_hz": RESAMPLE_SFREQ,
            "filter_then_resample": True,
            "reference": "average of the 30 scalp EEG channels, applied after interpolation",
            "eog_handling": "HEOG_left/HEOG_right/VEOG_lower dropped by name before referencing",
            "ica": "none (clean passive data); +/-100 uV epoch rejection used instead",
            "rejection": "MNE peak-to-peak reject=dict(eeg=100e-6)",
            "ransac_backend": sorted(backends) if backends else ["n/a"],
            "ransac_random_state": RANDOM_STATE,
            "roi": ROI,
            "window_s": list(WIN),
            "epoch_s": [TMIN, TMAX],
            "baseline_s": list(BASELINE),
            "min_trials": {"deviants": MIN_DEVIANTS, "standards": MIN_STANDARDS},
            "exclusion_reasons": reasons,
            "per_subject_detail": details,
            "mne_version": mne.__version__,
        },
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w") as fh:
        json.dump(result, fh, indent=2)

    print(
        f"\nn_analyzed={len(per_subject)}  excluded={len(excluded)}  "
        f"grand_mean_uV={grand_mean}\nwrote {OUT_JSON}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
