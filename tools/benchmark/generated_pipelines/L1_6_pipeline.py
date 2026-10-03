#!/usr/bin/env python3
"""
Auditory Mismatch Negativity (MMN) pipeline -- ERP CORE MMN (sub-001 ... sub-040).

Recipe
------
1. Preprocess : 0.1-30 Hz zero-phase FIR, drop dedicated EOG channels, RANSAC bad
                channel detection -> interpolate -> average reference, resample to
                256 Hz (>= 200 Hz).
2. ICA        : not used.  ERP CORE MMN is passive/clean, so the recipe's allowed
                fallback (a plain +/-100 uV epoch rejection) is used instead.
3. Epoch      : -0.2 .. 0.5 s, baseline (-0.2, 0), reject at 100 uV peak-to-peak,
                require >= 50 deviants and >= 150 standards after rejection.
4. Measure    : per-subject deviant - standard difference wave, mean amplitude over
                Fz/FCz/Cz in the 100-250 ms window, in uV.

Output
------
JSON with per-subject values, exclusions and the grand mean.

Standalone: `python pipeline.py [--jobs N] [--out PATH]`
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

import mne

mne.set_log_level("ERROR")

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

DATA_ROOT = "/home/hou/mne_data/MNE-erpcoremmn2021-data"
SUBJECTS = [f"sub-{i:03d}" for i in range(1, 41)]

OUT_DIR = (
    "/tmp/claude-1137/-home-hou-Research-auto-eeg-analysis/"
    "b4a153ed-22fa-4b6a-ad04-d134656fecf4/scratchpad/gen_scale/L1_6"
)
OUT_JSON = os.path.join(OUT_DIR, "result.json")

EOG_NAMES = ["HEOG_left", "HEOG_right", "VEOG_lower"]  # typed as EEG in the .set

L_FREQ = 0.1
H_FREQ = 30.0
RESAMPLE_HZ = 256.0  # 1024 / 4, >= 200 Hz

TMIN, TMAX = -0.2, 0.5
BASELINE = (-0.2, 0.0)
REJECT_PTP_V = 100e-6  # +/-100 uV, implemented as MNE peak-to-peak threshold

EVENT_ID = {"standard": 80, "deviant": 70}  # 180 = first stream -> excluded
MIN_DEVIANTS = 50
MIN_STANDARDS = 150

ROI = ["Fz", "FCz", "Cz"]
WIN = (0.100, 0.250)

RANDOM_STATE = 42


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _paths(sub: str):
    d = os.path.join(DATA_ROOT, sub, "eeg")
    return (
        os.path.join(d, f"{sub}_task-MMN_eeg.set"),
        os.path.join(d, f"{sub}_task-MMN_events.tsv"),
    )


def read_events_tsv(path: str):
    """Return list of (onset_seconds, integer_value) for value in {70, 80}."""
    out = []
    with open(path, "r", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            raw_onset = (row.get("onset") or "").strip()
            raw_value = (row.get("value") or "").strip()
            if raw_onset in ("", "n/a") or raw_value in ("", "n/a"):
                continue
            try:
                onset = float(raw_onset)
                value = int(round(float(raw_value)))
            except ValueError:
                continue
            if value in EVENT_ID.values():
                out.append((onset, value))
    return out


def resolve_names(ch_names, wanted):
    """Case-insensitive channel-name resolution ('FP1' vs 'Fp1', 'FCZ' vs 'FCz')."""
    lut = {c.lower(): c for c in ch_names}
    missing = [w for w in wanted if w.lower() not in lut]
    if missing:
        raise RuntimeError(f"missing channels: {missing}")
    return [lut[w.lower()] for w in wanted]


def detect_bads_ransac(raw):
    """RANSAC bad-channel detection.  pyprep preferred, autoreject as fallback."""
    try:
        from pyprep.find_noisy_channels import NoisyChannels

        nc = NoisyChannels(raw.copy(), do_detrend=False, random_state=RANDOM_STATE)
        try:
            nc.find_bad_by_ransac(channel_wise=False)
        except TypeError:
            nc.find_bad_by_ransac()
        return sorted(set(nc.bad_by_ransac)), "pyprep.NoisyChannels.find_bad_by_ransac"
    except Exception:
        pass

    try:
        from autoreject import Ransac

        epo = mne.make_fixed_length_epochs(raw, duration=2.0, preload=True)
        rsc = Ransac(n_jobs=1, random_state=RANDOM_STATE, verbose=False)
        rsc.fit(epo)
        return sorted(set(rsc.bad_chs_)), "autoreject.Ransac (2 s fixed-length epochs)"
    except Exception:
        return [], "unavailable (no bad-channel interpolation performed)"


# --------------------------------------------------------------------------- #
# Per-subject pipeline
# --------------------------------------------------------------------------- #

def process_subject(sub: str) -> dict:
    res = {"subject": sub, "ok": False, "value_uV": None, "reason": None}

    set_path, tsv_path = _paths(sub)
    if not os.path.exists(set_path):
        res["reason"] = "missing EEG file"
        return res
    if not os.path.exists(tsv_path):
        res["reason"] = "missing events.tsv"
        return res

    # ---- load -------------------------------------------------------------- #
    raw = mne.io.read_raw_eeglab(set_path, preload=True)

    # ---- drop dedicated EOG channels BEFORE referencing --------------------- #
    drop = [c for c in EOG_NAMES if c in raw.ch_names]
    if drop:
        raw.drop_channels(drop)
    res["dropped_eog"] = drop

    # everything that survives is scalp EEG
    raw.set_channel_types({c: "eeg" for c in raw.ch_names})

    # ---- montage ------------------------------------------------------------ #
    montage = mne.channels.make_standard_montage("standard_1020")
    raw.set_montage(montage, match_case=False, on_missing="warn")

    # ---- bandpass (zero-phase FIR) ------------------------------------------ #
    raw.filter(
        l_freq=L_FREQ,
        h_freq=H_FREQ,
        method="fir",
        phase="zero",
        fir_design="firwin",
        fir_window="hamming",
        n_jobs=1,
    )

    # ---- downsample --------------------------------------------------------- #
    if raw.info["sfreq"] > RESAMPLE_HZ:
        raw.resample(RESAMPLE_HZ, npad="auto")
    sfreq = float(raw.info["sfreq"])
    res["sfreq"] = sfreq

    # ---- RANSAC -> interpolate ---------------------------------------------- #
    bads, ransac_backend = detect_bads_ransac(raw)
    res["ransac_backend"] = ransac_backend
    res["bad_channels"] = bads
    if bads:
        raw.info["bads"] = bads
        raw.interpolate_bads(reset_bads=True, mode="accurate")

    # ---- average reference over scalp channels ------------------------------ #
    raw.set_eeg_reference("average", projection=False)

    # ---- events ------------------------------------------------------------- #
    ev = read_events_tsv(tsv_path)
    if not ev:
        res["reason"] = "no usable events (values 70/80) in events.tsv"
        return res

    rows, seen = [], set()
    for onset, value in ev:
        samp = int(round(onset * sfreq)) + int(raw.first_samp)
        if samp in seen:
            continue
        seen.add(samp)
        rows.append([samp, 0, value])
    events = np.asarray(sorted(rows, key=lambda r: r[0]), dtype=int)

    n_raw_dev = int(np.sum(events[:, 2] == EVENT_ID["deviant"]))
    n_raw_std = int(np.sum(events[:, 2] == EVENT_ID["standard"]))
    res["n_events"] = {"standard": n_raw_std, "deviant": n_raw_dev}

    # ---- epoch -------------------------------------------------------------- #
    epochs = mne.Epochs(
        raw,
        events,
        event_id=EVENT_ID,
        tmin=TMIN,
        tmax=TMAX,
        baseline=BASELINE,
        picks="eeg",
        reject=dict(eeg=REJECT_PTP_V),
        flat=None,
        proj=False,
        detrend=None,
        preload=True,
        reject_by_annotation=False,
        on_missing="warn",
    )

    n_std = len(epochs["standard"])
    n_dev = len(epochs["deviant"])
    res["n_kept"] = {"standard": int(n_std), "deviant": int(n_dev)}
    res["pct_kept"] = {
        "standard": round(100.0 * n_std / n_raw_std, 1) if n_raw_std else 0.0,
        "deviant": round(100.0 * n_dev / n_raw_dev, 1) if n_raw_dev else 0.0,
    }

    if n_dev < MIN_DEVIANTS or n_std < MIN_STANDARDS:
        res["reason"] = (
            f"too few trials after rejection "
            f"(deviants {n_dev} < {MIN_DEVIANTS}"
            if n_dev < MIN_DEVIANTS
            else f"too few trials after rejection (standards {n_std} < {MIN_STANDARDS}"
        )
        res["reason"] = (
            f"too few trials after rejection: {n_dev} deviants (need >= {MIN_DEVIANTS}), "
            f"{n_std} standards (need >= {MIN_STANDARDS})"
        )
        return res

    # ---- difference wave ---------------------------------------------------- #
    ev_std = epochs["standard"].average()
    ev_dev = epochs["deviant"].average()
    diff = mne.combine_evoked([ev_dev, ev_std], weights=[1, -1])

    roi = resolve_names(diff.ch_names, ROI)
    res["roi"] = roi

    d = diff.copy().pick(roi)
    mask = (d.times >= WIN[0] - 1e-9) & (d.times <= WIN[1] + 1e-9)
    if not mask.any():
        res["reason"] = "measurement window empty"
        return res

    value_uV = float(d.data[:, mask].mean() * 1e6)

    res["ok"] = True
    res["value_uV"] = round(value_uV, 3)
    return res


def _worker(sub: str) -> dict:
    try:
        return process_subject(sub)
    except Exception as exc:  # keep one bad subject from killing the batch
        return {
            "subject": sub,
            "ok": False,
            "value_uV": None,
            "reason": f"error: {type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(limit=5),
        }


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser(description="ERP CORE MMN pipeline")
    ap.add_argument(
        "--jobs",
        type=int,
        default=int(os.environ.get("AEA_JOBS", min(4, os.cpu_count() or 1))),
        help="parallel subject workers (default: 4)",
    )
    ap.add_argument("--out", default=OUT_JSON, help="output JSON path")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)

    results = {}
    if args.jobs > 1:
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            futs = {pool.submit(_worker, s): s for s in SUBJECTS}
            for fut in as_completed(futs):
                r = fut.result()
                results[r["subject"]] = r
                print(
                    f"[{r['subject']}] "
                    + (f"{r['value_uV']:+.3f} uV" if r["ok"] else f"EXCLUDED ({r['reason']})"),
                    flush=True,
                )
    else:
        for s in SUBJECTS:
            r = _worker(s)
            results[s] = r
            print(
                f"[{s}] "
                + (f"{r['value_uV']:+.3f} uV" if r["ok"] else f"EXCLUDED ({r['reason']})"),
                flush=True,
            )

    per_subject, excluded, reasons, detail = {}, [], {}, {}
    for sub in SUBJECTS:
        r = results.get(sub, {"ok": False, "reason": "not processed"})
        detail[sub] = {
            k: r.get(k)
            for k in ("n_events", "n_kept", "pct_kept", "bad_channels", "sfreq")
            if r.get(k) is not None
        }
        if r.get("ok"):
            per_subject[sub] = r["value_uV"]
        else:
            excluded.append(sub)
            reasons[sub] = r.get("reason", "unknown")

    vals = list(per_subject.values())
    grand = round(float(np.mean(vals)), 3) if vals else None

    backends = sorted(
        {r.get("ransac_backend") for r in results.values() if r.get("ransac_backend")}
    )

    out = {
        "per_subject": per_subject,
        "excluded": excluded,
        "n_analyzed": len(per_subject),
        "grand_mean_uV": grand,
        "choices": {
            "notes": (
                "ERP CORE MMN, sub-001..sub-040. Per subject: read .set with "
                "read_raw_eeglab; the 3 dedicated EOG channels (HEOG_left, HEOG_right, "
                "VEOG_lower, typed EEG in the .set) are dropped by name BEFORE "
                "referencing so they never enter the average reference; standard_1020 "
                "montage with match_case=False; 0.1-30 Hz zero-phase FIR (firwin, "
                "hamming, MNE auto transition bands); resampled 1024 -> 256 Hz "
                "(clean factor-of-4 decimation, >= 200 Hz); RANSAC bad-channel "
                "detection -> spherical-spline interpolation -> average reference "
                "(recipe order). No ICA: ERP CORE MMN is clean passive data, so the "
                "recipe's permitted alternative (a plain +/-100 uV epoch rejection) is "
                "used. Epochs -0.2..0.5 s, baseline (-0.2, 0), rejection threshold "
                "implemented as MNE's peak-to-peak criterion reject=dict(eeg=100e-6). "
                "Events taken from the BIDS events.tsv 'onset' (seconds) x 'value' "
                "column: 80 = standard, 70 = deviant, 180 (first stream) excluded; "
                "duplicate onsets de-duplicated. Subjects with < 50 deviants or "
                "< 150 standards surviving rejection are excluded. Measure: "
                "deviant - standard difference wave (combine_evoked weights [1, -1]), "
                "mean amplitude across Fz/FCz/Cz over 100-250 ms, converted to uV. "
                "grand_mean_uV is the unweighted mean of the per-subject values. "
                "All values rounded to 3 decimals."
            ),
            "filter": "0.1-30 Hz FIR, phase='zero', fir_design='firwin', hamming window",
            "reference": "average of the 30 scalp EEG channels (EOG dropped first)",
            "resample_hz": RESAMPLE_HZ,
            "ica": "none; +/-100 uV epoch rejection used instead (clean passive data)",
            "artifact_rejection": "peak-to-peak 100 uV on all EEG channels",
            "ransac_backend": backends,
            "bad_channel_handling": "RANSAC -> interpolate_bads(mode='accurate') -> average reference",
            "epoch_window_s": [TMIN, TMAX],
            "baseline_s": list(BASELINE),
            "measurement_window_ms": [int(WIN[0] * 1000), int(WIN[1] * 1000)],
            "roi_channels": ROI,
            "min_trials": {"deviant": MIN_DEVIANTS, "standard": MIN_STANDARDS},
            "random_state": RANDOM_STATE,
            "exclusion_reasons": reasons,
            "per_subject_detail": detail,
        },
    }

    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=2)

    print(
        f"\nAnalyzed {len(per_subject)}/{len(SUBJECTS)} subjects; "
        f"grand mean = {grand} uV; excluded = {excluded}"
    )
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
