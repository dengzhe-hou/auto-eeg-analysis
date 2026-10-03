#!/usr/bin/env python3
"""
Auditory Mismatch Negativity (MMN) pipeline -- ERP CORE MMN (ERP CORE, Kappenman et al. 2021).

Implements the RECIPE:
  1. Preprocess : 0.1-30 Hz zero-phase FIR, drop dedicated EOG channels, RANSAC bad-channel
                  detection -> interpolate -> average reference of the scalp channels,
                  resample to 256 Hz (>= 200 Hz).
  2. ICA        : NOT used. ERP CORE MMN is passive/clean; a simple +-100 uV epoch reject is
                  used instead (explicitly permitted and documented by the recipe).
  3. Epoch      : -0.2 to 0.5 s, baseline (-0.2, 0), reject +-100 uV,
                  require >= 50 deviants and >= 150 standards after rejection.
  4. Measure    : per subject deviant - standard difference wave; mean amplitude over
                  Fz/FCz/Cz in the 100-250 ms window, reported in microvolts.

Output: JSON next to this script (result.json).

Standalone: python pipeline.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
import traceback
from typing import Dict, List, Optional, Tuple

import numpy as np

import mne

mne.set_log_level("ERROR")

# --------------------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------------------

DATA_ROOT = "/home/hou/mne_data/MNE-erpcoremmn2021-data"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(OUT_DIR, "result.json")

SUBJECTS = [f"sub-{i:03d}" for i in range(1, 41)]

TASK = "MMN"

# Event coding in {sub}_task-MMN_events.tsv  ("value" column)
CODE_STANDARD = 80
CODE_DEVIANT = 70
CODE_FIRST_STREAM = 180  # excluded

EVENT_ID = {"standard": CODE_STANDARD, "deviant": CODE_DEVIANT}

# Dedicated EOG channels (typed EEG inside the .set file -> must be dropped by name so that
# they are never averaged into the reference).
EOG_NAMES = ["HEOG_left", "HEOG_right", "VEOG_lower"]

# Filtering
L_FREQ = 0.1
H_FREQ = 30.0

# Resampling: 1024 Hz / 4 = 256 Hz  (exact integer decimation, >= 200 Hz as required)
SFREQ_TARGET = 256.0

# Epoching
TMIN, TMAX = -0.2, 0.5
BASELINE = (-0.2, 0.0)
REJECT_PTP_V = 100e-6  # peak-to-peak, volts ("+-100 uV")

MIN_DEVIANTS = 50
MIN_STANDARDS = 150

# Measurement
ROI = ["Fz", "FCz", "Cz"]
WIN_TMIN, WIN_TMAX = 0.100, 0.250

# RANSAC
RANSAC_EPOCH_LEN = 1.0     # s, fixed-length epochs used only for bad-channel detection
RANSAC_MAX_EPOCHS = 300    # deterministic evenly-spaced subsample, bounds runtime
RANSAC_SEED = 42
RANSAC_MAX_BADS_FRAC = 0.20  # sanity guard: never interpolate more than 20% of channels

ROUND_DP = 3
N_JOBS = 1


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------

def subject_paths(sub: str) -> Tuple[str, str]:
    eeg_dir = os.path.join(DATA_ROOT, sub, "eeg")
    set_path = os.path.join(eeg_dir, f"{sub}_task-{TASK}_eeg.set")
    ev_path = os.path.join(eeg_dir, f"{sub}_task-{TASK}_events.tsv")
    return set_path, ev_path


def read_events_tsv(path: str) -> List[Tuple[float, int]]:
    """Return [(onset_seconds, value), ...] keeping only standards (80) and deviants (70).

    The 180 code marks the first (unanalysed) stimulus stream and is excluded, as are any
    non-stimulus status codes.
    """
    keep = []
    with open(path, "r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            raw_val = (row.get("value") or "").strip()
            raw_onset = (row.get("onset") or "").strip()
            if raw_val in ("", "n/a", "N/A") or raw_onset in ("", "n/a", "N/A"):
                continue
            try:
                val = int(round(float(raw_val)))
                onset = float(raw_onset)
            except ValueError:
                continue
            if val in (CODE_STANDARD, CODE_DEVIANT):
                keep.append((onset, val))
            # CODE_FIRST_STREAM (180) and anything else is dropped on purpose.
    return keep


def events_to_array(onsets_values: List[Tuple[float, int]], raw: mne.io.BaseRaw) -> np.ndarray:
    """Build an MNE events array from BIDS onsets (seconds, relative to recording start)."""
    sfreq = raw.info["sfreq"]
    n_times = raw.n_times
    rows = []
    for onset, val in onsets_values:
        samp = int(round(onset * sfreq))
        if 0 <= samp < n_times:
            rows.append((samp + raw.first_samp, 0, val))
    if not rows:
        return np.empty((0, 3), dtype=int)
    ev = np.array(sorted(rows, key=lambda r: r[0]), dtype=int)
    # Guard against duplicate sample indices introduced by rounding.
    _, uniq_idx = np.unique(ev[:, 0], return_index=True)
    return ev[np.sort(uniq_idx)]


def detect_bads_ransac(raw: mne.io.BaseRaw) -> Tuple[List[str], str]:
    """RANSAC bad-channel detection on fixed-length epochs. Returns (bads, note)."""
    try:
        from autoreject import Ransac  # noqa: WPS433 (optional dependency)
    except Exception:
        return [], "autoreject.Ransac unavailable -> no RANSAC bad-channel detection"

    try:
        epochs = mne.make_fixed_length_epochs(
            raw, duration=RANSAC_EPOCH_LEN, preload=True, verbose=False
        )
        if len(epochs) < 10:
            return [], f"only {len(epochs)} RANSAC epochs -> skipped"
        if len(epochs) > RANSAC_MAX_EPOCHS:
            sel = np.linspace(0, len(epochs) - 1, RANSAC_MAX_EPOCHS).round().astype(int)
            epochs = epochs[np.unique(sel)]

        picks = mne.pick_types(epochs.info, eeg=True, exclude=[])
        rsc = Ransac(picks=picks, n_jobs=N_JOBS, random_state=RANSAC_SEED, verbose=False)
        rsc.fit(epochs)
        bads = sorted(set(rsc.bad_chs_))

        n_eeg = len(picks)
        max_bads = max(1, int(np.floor(RANSAC_MAX_BADS_FRAC * n_eeg)))
        note = ""
        if len(bads) > max_bads:
            note = (
                f"RANSAC flagged {len(bads)} channels (> {RANSAC_MAX_BADS_FRAC:.0%} of "
                f"{n_eeg}); kept none to avoid over-interpolation"
            )
            bads = []
        return bads, note
    except Exception as exc:  # pragma: no cover - defensive
        return [], f"RANSAC failed ({type(exc).__name__}: {exc}) -> no bads flagged"


# --------------------------------------------------------------------------------------
# Per-subject pipeline
# --------------------------------------------------------------------------------------

def process_subject(sub: str) -> Dict:
    """Run the full recipe for one subject.

    Returns a dict with keys: ok (bool), value (float|None), reason (str), info (dict).
    """
    out = {"ok": False, "value": None, "reason": "", "info": {}}

    set_path, ev_path = subject_paths(sub)
    if not os.path.exists(set_path):
        out["reason"] = "missing EEG file"
        return out
    if not os.path.exists(ev_path):
        out["reason"] = "missing events.tsv"
        return out

    # ---- 1. Load -----------------------------------------------------------------
    raw = mne.io.read_raw_eeglab(set_path, preload=True, verbose=False)

    # ---- 1a. Drop dedicated EOG channels BEFORE any referencing --------------------
    to_drop = [ch for ch in EOG_NAMES if ch in raw.ch_names]
    # also drop anything MNE already typed as EOG/misc, to be safe
    extra = [
        ch
        for ch, kind in zip(raw.ch_names, raw.get_channel_types())
        if kind in ("eog", "misc", "stim") and ch not in to_drop
    ]
    raw.drop_channels(to_drop + extra)
    out["info"]["dropped_channels"] = to_drop + extra

    # ---- 1b. Montage ---------------------------------------------------------------
    montage = mne.channels.make_standard_montage("standard_1020")
    raw.set_montage(montage, match_case=False, on_missing="warn", verbose=False)
    no_pos = [
        ch
        for ch, loc in zip(raw.ch_names, [c["loc"][:3] for c in raw.info["chs"]])
        if not np.isfinite(loc).all() or np.allclose(loc, 0)
    ]
    if no_pos:
        out["info"]["channels_without_position"] = no_pos

    raw.set_channel_types({ch: "eeg" for ch in raw.ch_names})

    # ---- 1c. Bandpass 0.1-30 Hz, zero-phase FIR ------------------------------------
    raw.filter(
        l_freq=L_FREQ,
        h_freq=H_FREQ,
        method="fir",
        phase="zero",
        fir_design="firwin",
        fir_window="hamming",
        l_trans_bandwidth="auto",
        h_trans_bandwidth="auto",
        n_jobs=N_JOBS,
        verbose=False,
    )

    # ---- 1d. Resample (1024 -> 256 Hz) ---------------------------------------------
    if abs(raw.info["sfreq"] - SFREQ_TARGET) > 1e-6:
        raw.resample(SFREQ_TARGET, npad="auto", n_jobs=N_JOBS, verbose=False)
    out["info"]["sfreq"] = float(raw.info["sfreq"])

    # ---- 1e. RANSAC -> interpolate -> average reference ----------------------------
    bads, ransac_note = detect_bads_ransac(raw)
    raw.info["bads"] = bads
    out["info"]["bad_channels"] = bads
    if ransac_note:
        out["info"]["ransac_note"] = ransac_note
    if bads:
        raw.interpolate_bads(reset_bads=True, mode="accurate", verbose=False)

    raw.set_eeg_reference("average", projection=False, ch_type="eeg", verbose=False)

    # ---- 3. Epoch ------------------------------------------------------------------
    ev_list = read_events_tsv(ev_path)
    events = events_to_array(ev_list, raw)
    if events.shape[0] == 0:
        out["reason"] = "no usable events"
        return out

    epochs = mne.Epochs(
        raw,
        events=events,
        event_id=EVENT_ID,
        tmin=TMIN,
        tmax=TMAX,
        baseline=BASELINE,
        reject=dict(eeg=REJECT_PTP_V),
        preload=True,
        proj=False,
        reject_by_annotation=True,
        verbose=False,
    )

    n_std = len(epochs["standard"])
    n_dev = len(epochs["deviant"])
    out["info"]["n_standard_kept"] = int(n_std)
    out["info"]["n_deviant_kept"] = int(n_dev)
    out["info"]["n_standard_presented"] = int(np.sum(events[:, 2] == CODE_STANDARD))
    out["info"]["n_deviant_presented"] = int(np.sum(events[:, 2] == CODE_DEVIANT))

    if n_dev < MIN_DEVIANTS or n_std < MIN_STANDARDS:
        out["reason"] = (
            f"too few trials after rejection (deviants={n_dev}<{MIN_DEVIANTS} or "
            f"standards={n_std}<{MIN_STANDARDS})"
        )
        return out

    # ---- 4. Measure ----------------------------------------------------------------
    ev_std = epochs["standard"].average()
    ev_dev = epochs["deviant"].average()
    diff = mne.combine_evoked([ev_dev, ev_std], weights=[1.0, -1.0])

    missing_roi = [ch for ch in ROI if ch not in diff.ch_names]
    if missing_roi:
        out["reason"] = f"missing ROI channels {missing_roi}"
        return out

    data = diff.get_data(picks=ROI, tmin=WIN_TMIN, tmax=WIN_TMAX)  # (n_ch, n_times), volts
    value_uv = float(np.mean(data) * 1e6)

    out["ok"] = True
    out["value"] = value_uv
    return out


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------

def main() -> int:
    per_subject: Dict[str, float] = {}
    excluded: List[str] = []
    exclusion_reasons: Dict[str, str] = {}
    diagnostics: Dict[str, Dict] = {}

    for sub in SUBJECTS:
        try:
            res = process_subject(sub)
        except Exception as exc:  # pragma: no cover - defensive
            res = {
                "ok": False,
                "value": None,
                "reason": f"error: {type(exc).__name__}: {exc}",
                "info": {"traceback": traceback.format_exc(limit=3)},
            }

        diagnostics[sub] = res["info"]
        if res["ok"]:
            per_subject[sub] = round(float(res["value"]), ROUND_DP)
            print(f"[{sub}] MMN (dev-std, Fz/FCz/Cz, 100-250 ms) = "
                  f"{per_subject[sub]:+.3f} uV", file=sys.stderr)
        else:
            excluded.append(sub)
            exclusion_reasons[sub] = res["reason"]
            print(f"[{sub}] EXCLUDED: {res['reason']}", file=sys.stderr)

    values = list(per_subject.values())
    grand_mean = round(float(np.mean(values)), ROUND_DP) if values else None

    result = {
        "per_subject": per_subject,
        "excluded": excluded,
        "n_analyzed": len(per_subject),
        "grand_mean_uV": grand_mean,
        "choices": {
            "notes": (
                "ERP CORE MMN, sub-001..sub-040. Pipeline: read_raw_eeglab -> drop the 3 "
                "dedicated EOG channels (HEOG_left/HEOG_right/VEOG_lower) by name BEFORE "
                "referencing so they never enter the average reference -> standard_1020 "
                "montage (match_case=False for FP1/FP2) -> zero-phase FIR bandpass "
                "0.1-30 Hz (firwin/hamming, 'auto' transition bands) -> resample 1024->256 Hz "
                "(exact /4 decimation, >=200 Hz) -> RANSAC bad-channel detection "
                "(autoreject.Ransac on 1-s fixed-length epochs) -> spherical-spline "
                "interpolation -> average reference over the 30 scalp channels -> epochs "
                "-0.2..0.5 s, baseline (-0.2, 0), peak-to-peak reject 100 uV. NO ICA was run: "
                "the recipe explicitly allows the simple +-100 uV reject for the clean passive "
                "ERP CORE MMN data, so that route was taken. Subjects with <50 deviants or "
                "<150 standards surviving rejection are excluded. Measure: per-subject "
                "deviant(70) - standard(80) difference wave, mean amplitude across Fz, FCz, Cz "
                "over 100-250 ms, in uV. Values rounded to 3 dp."
            ),
            "open_choices_resolved": {
                "ica": "not used (+-100 uV peak-to-peak epoch reject only), per recipe option B",
                "resample_rate_hz": SFREQ_TARGET,
                "resample_stage": "after filtering, before epoching (exact 1024/4 decimation)",
                "filter": {
                    "l_freq": L_FREQ,
                    "h_freq": H_FREQ,
                    "method": "fir",
                    "phase": "zero",
                    "fir_design": "firwin",
                    "fir_window": "hamming",
                    "trans_bandwidth": "auto",
                },
                "reject_interpretation": (
                    "MNE `reject=dict(eeg=100e-6)`, i.e. a 100 uV peak-to-peak criterion "
                    "within the -0.2..0.5 s epoch on the average-referenced scalp channels"
                ),
                "ransac": {
                    "implementation": "autoreject.Ransac",
                    "epoch_len_s": RANSAC_EPOCH_LEN,
                    "max_epochs_used": RANSAC_MAX_EPOCHS,
                    "random_state": RANSAC_SEED,
                    "max_bads_fraction": RANSAC_MAX_BADS_FRAC,
                    "order": "RANSAC on unreferenced data -> interpolate -> average reference",
                },
                "event_source": (
                    "BIDS events.tsv `onset` (seconds) x sfreq; value 80=standard, 70=deviant; "
                    "180 (first stream) and all non-stimulus codes excluded"
                ),
                "measurement_window": [WIN_TMIN, WIN_TMAX],
                "roi": ROI,
                "sign_convention": "deviant minus standard (MMN expected negative)",
            },
            "exclusion_reasons": exclusion_reasons,
            "diagnostics": diagnostics,
            "software": {
                "mne": mne.__version__,
                "python": sys.version.split()[0],
                "numpy": np.__version__,
            },
        },
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)

    print(
        f"\nAnalyzed {len(per_subject)}/{len(SUBJECTS)} subjects; "
        f"grand mean = {grand_mean} uV -> {OUT_JSON}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
