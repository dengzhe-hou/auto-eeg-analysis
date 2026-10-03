#!/usr/bin/env python3
"""
Auditory Mismatch Negativity (MMN) pipeline -- ERP CORE MMN (sub-001 ... sub-040).

Implements the recipe:
  1. Preprocess : 0.1-30 Hz zero-phase FIR, drop EOG, resample >= 200 Hz,
                  RANSAC bad-channel detection -> interpolate -> average reference.
  2. ICA        : skipped (ERP CORE MMN is passive/clean); a +-100 uV epoch reject
                  is used instead, as the recipe permits.
  3. Epoch      : -0.2 .. 0.5 s, baseline (-0.2, 0), reject +-100 uV,
                  require >= 50 deviants and >= 150 standards after rejection.
  4. Measure    : per-subject deviant - standard difference wave, mean amplitude
                  over Fz/FCz/Cz in the 100-250 ms window, in microvolts.

Writes result.json next to this script. Standalone: `python pipeline.py`.
"""

from __future__ import annotations

import json
import sys
import traceback
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

import mne

mne.set_log_level("ERROR")
warnings.filterwarnings("ignore")

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
DATA_ROOT = Path("/home/hou/mne_data/MNE-erpcoremmn2021-data")
OUT_DIR = Path(
    "/tmp/claude-1137/-home-hou-Research-auto-eeg-analysis/"
    "b4a153ed-22fa-4b6a-ad04-d134656fecf4/scratchpad/gen_scale/L1_9"
)
OUT_JSON = OUT_DIR / "result.json"

SUBJECTS = [f"sub-{i:03d}" for i in range(1, 41)]

# EOG channels are typed as EEG in the .set file -> drop them by name so they
# never enter the average reference.
EOG_NAMES = ["HEOG_left", "HEOG_right", "VEOG_lower"]

L_FREQ, H_FREQ = 0.1, 30.0          # zero-phase FIR bandpass
SFREQ_TARGET = 256.0                # >= 200 Hz; 1024 / 4 -> exact integer decimation
MONTAGE_NAME = "standard_1020"

TMIN, TMAX = -0.2, 0.5
BASELINE = (-0.2, 0.0)
REJECT = dict(eeg=100e-6)           # peak-to-peak, 100 uV
MIN_DEVIANTS, MIN_STANDARDS = 50, 150

CODE_STANDARD, CODE_DEVIANT = 80, 70
CODE_FIRST_STREAM = 180             # excluded
EVENT_ID = {"standard": CODE_STANDARD, "deviant": CODE_DEVIANT}

ROI = ["Fz", "FCz", "Cz"]
WIN = (0.100, 0.250)                # seconds

RANDOM_STATE = 97


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def log(msg: str) -> None:
    print(msg, flush=True)


def subject_paths(sub: str) -> tuple[Path, Path]:
    eeg_dir = DATA_ROOT / sub / "eeg"
    return (
        eeg_dir / f"{sub}_task-MMN_eeg.set",
        eeg_dir / f"{sub}_task-MMN_events.tsv",
    )


def load_raw(set_path: Path) -> mne.io.BaseRaw:
    """Read the EEGLAB file, drop EOG channels, attach the montage."""
    raw = mne.io.read_raw_eeglab(str(set_path), preload=True)

    drop = [ch for ch in EOG_NAMES if ch in raw.ch_names]
    if drop:
        raw.drop_channels(drop)

    # Everything left is scalp EEG.
    raw.set_channel_types({ch: "eeg" for ch in raw.ch_names})

    montage = mne.channels.make_standard_montage(MONTAGE_NAME)
    raw.set_montage(montage, match_case=False, on_missing="warn")
    return raw


def read_events(events_tsv: Path, sfreq: float, first_samp: int) -> np.ndarray:
    """Build an MNE events array from the BIDS events.tsv (onsets in seconds)."""
    df = pd.read_csv(events_tsv, sep="\t")
    if "onset" not in df.columns or "value" not in df.columns:
        raise RuntimeError(f"events.tsv missing 'onset'/'value': {events_tsv}")

    onset = pd.to_numeric(df["onset"], errors="coerce")
    value = pd.to_numeric(df["value"], errors="coerce")

    keep = onset.notna() & value.isin([CODE_STANDARD, CODE_DEVIANT])  # drops 180
    onset = onset[keep].to_numpy(dtype=float)
    value = value[keep].to_numpy(dtype=int)

    samples = np.round(onset * sfreq).astype(int) + int(first_samp)
    events = np.column_stack(
        [samples, np.zeros_like(samples), value]
    ).astype(int)

    # MNE wants ascending, unique sample indices.
    events = events[np.argsort(events[:, 0], kind="stable")]
    _, uniq = np.unique(events[:, 0], return_index=True)
    events = events[np.sort(uniq)]
    return events


def detect_bads_ransac(raw: mne.io.BaseRaw) -> tuple[list[str], str]:
    """RANSAC bad-channel detection (pyprep preferred, autoreject fallback)."""
    # --- pyprep on continuous data -----------------------------------------
    try:
        from pyprep.find_noisy_channels import NoisyChannels

        nd = NoisyChannels(raw.copy(), random_state=RANDOM_STATE, do_detrend=False)
        nd.find_bad_by_ransac(channel_wise=False)
        return sorted(set(nd.bad_by_ransac)), "pyprep.NoisyChannels.find_bad_by_ransac"
    except Exception:
        pass

    # --- autoreject RANSAC on fixed-length epochs --------------------------
    try:
        from autoreject import Ransac

        tmp = mne.make_fixed_length_epochs(raw.copy(), duration=1.0, preload=True)
        rsc = Ransac(random_state=RANDOM_STATE, n_jobs=1, verbose=False)
        rsc.fit(tmp)
        return sorted(set(rsc.bad_chs_)), "autoreject.Ransac (1 s fixed-length epochs)"
    except Exception:
        pass

    return [], "unavailable (no pyprep/autoreject) -- no channels marked bad"


def mmn_amplitude(evoked_dev: mne.Evoked, evoked_std: mne.Evoked) -> float:
    """Mean amplitude (uV) of the deviant - standard wave over ROI x window."""
    diff = mne.combine_evoked([evoked_dev, evoked_std], weights=[1.0, -1.0])
    picks = [ch for ch in ROI if ch in diff.ch_names]
    if not picks:
        raise RuntimeError(f"none of the ROI channels {ROI} are present")
    seg = diff.copy().pick(picks).crop(tmin=WIN[0], tmax=WIN[1])
    return float(seg.get_data().mean() * 1e6)


# --------------------------------------------------------------------------- #
# Per-subject processing
# --------------------------------------------------------------------------- #
def process_subject(sub: str) -> dict:
    set_path, ev_path = subject_paths(sub)
    if not set_path.exists():
        return {"status": "excluded", "reason": f"missing file {set_path.name}"}
    if not ev_path.exists():
        return {"status": "excluded", "reason": f"missing file {ev_path.name}"}

    raw = load_raw(set_path)

    # 1. Bandpass (zero-phase FIR, default firwin design, both directions).
    raw.filter(
        l_freq=L_FREQ,
        h_freq=H_FREQ,
        method="fir",
        phase="zero",
        fir_design="firwin",
        fir_window="hamming",
        n_jobs=1,
    )

    # Downsample (1024 -> 256 Hz, >= 200 Hz as required).
    if raw.info["sfreq"] > SFREQ_TARGET:
        raw.resample(SFREQ_TARGET, npad="auto")

    # 2. RANSAC -> interpolate -> average reference (scalp channels only).
    bads, ransac_backend = detect_bads_ransac(raw)
    raw.info["bads"] = sorted(set(raw.info["bads"]) | set(bads))
    n_bads = len(raw.info["bads"])
    if raw.info["bads"]:
        raw.interpolate_bads(reset_bads=True, mode="accurate")
    raw.set_eeg_reference("average", projection=False)

    # 3. Epoch.
    events = read_events(ev_path, raw.info["sfreq"], raw.first_samp)
    if events.size == 0:
        return {"status": "excluded", "reason": "no standard/deviant events"}

    epochs = mne.Epochs(
        raw,
        events=events,
        event_id=EVENT_ID,
        tmin=TMIN,
        tmax=TMAX,
        baseline=BASELINE,
        reject=REJECT,
        preload=True,
        proj=False,
        reject_by_annotation=False,
        on_missing="warn",
    )

    n_std = len(epochs["standard"]) if "standard" in epochs.event_id else 0
    n_dev = len(epochs["deviant"]) if "deviant" in epochs.event_id else 0

    if n_dev < MIN_DEVIANTS or n_std < MIN_STANDARDS:
        return {
            "status": "excluded",
            "reason": (
                f"too few trials after rejection "
                f"(deviants {n_dev} < {MIN_DEVIANTS}"
                if n_dev < MIN_DEVIANTS
                else f"too few trials after rejection (standards {n_std} < {MIN_STANDARDS}"
            )
            + f"; kept {n_std} standards / {n_dev} deviants)",
            "n_standards": n_std,
            "n_deviants": n_dev,
            "n_bads": n_bads,
        }

    # 4. Measure.
    amp = mmn_amplitude(epochs["deviant"].average(), epochs["standard"].average())

    return {
        "status": "ok",
        "amplitude_uV": amp,
        "n_standards": n_std,
        "n_deviants": n_dev,
        "n_bads": n_bads,
        "bads": bads,
        "ransac_backend": ransac_backend,
        "sfreq": float(raw.info["sfreq"]),
    }


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    per_subject: dict[str, float] = {}
    excluded: list[str] = []
    details: dict[str, dict] = {}
    ransac_backends: set[str] = set()

    for sub in SUBJECTS:
        try:
            res = process_subject(sub)
        except Exception as exc:  # keep the batch alive on any single failure
            res = {"status": "excluded", "reason": f"{type(exc).__name__}: {exc}"}
            traceback.print_exc(file=sys.stderr)

        if res.get("ransac_backend"):
            ransac_backends.add(res["ransac_backend"])

        if res["status"] == "ok":
            per_subject[sub] = round(res["amplitude_uV"], 3)
            details[sub] = {
                "n_standards": res["n_standards"],
                "n_deviants": res["n_deviants"],
                "n_interpolated": res["n_bads"],
            }
            log(
                f"{sub}: MMN = {per_subject[sub]:+.3f} uV  "
                f"(std {res['n_standards']}, dev {res['n_deviants']}, "
                f"interp {res['n_bads']})"
            )
        else:
            excluded.append(sub)
            details[sub] = {"excluded_reason": res.get("reason", "unknown")}
            log(f"{sub}: EXCLUDED -- {res.get('reason', 'unknown')}")

    values = np.array(list(per_subject.values()), dtype=float)
    grand_mean = round(float(values.mean()), 3) if values.size else None

    notes = (
        "ICA skipped (recipe-permitted for clean passive ERP CORE MMN data); artifact "
        "control is the +-100 uV epoch reject, applied as MNE peak-to-peak "
        "reject=dict(eeg=100e-6). Preprocessing order: read .set -> drop the 3 EOG "
        "channels by name (HEOG_left/HEOG_right/VEOG_lower, which are typed EEG in the "
        "file) -> standard_1020 montage with match_case=False -> 0.1-30 Hz zero-phase "
        "FIR (firwin/hamming, MNE default transition bands) at the native 1024 Hz -> "
        "resample to 256 Hz (>= 200 Hz, exact /4 decimation) -> RANSAC bad-channel "
        "detection -> spherical-spline interpolation (reset_bads=True) -> average "
        "reference over scalp channels only. Events come from the BIDS events.tsv "
        "(tab-separated, onset in seconds x sfreq); value 80 = standard, 70 = deviant, "
        "180 (first stream) dropped; no additional post-deviant standard exclusion. "
        "Epochs -0.2 to 0.5 s, baseline (-0.2, 0). Subjects with < 50 deviants or "
        "< 150 standards surviving rejection are excluded. Measure: per-subject "
        "deviant-minus-standard difference wave (mne.combine_evoked weights [1, -1]), "
        "mean amplitude across Fz/FCz/Cz over 100-250 ms, converted to uV; grand mean "
        "is the unweighted mean of the per-subject values. All values rounded to 3 dp."
    )

    result = {
        "per_subject": per_subject,
        "excluded": excluded,
        "n_analyzed": len(per_subject),
        "grand_mean_uV": grand_mean,
        "choices": {
            "filter": "0.1-30 Hz zero-phase FIR (firwin, hamming), applied at 1024 Hz",
            "resample_hz": SFREQ_TARGET,
            "reference": "average of scalp EEG channels (EOG dropped beforehand)",
            "bad_channels": "RANSAC -> interpolate -> re-reference",
            "ransac_backend": sorted(ransac_backends) or ["not run"],
            "ica": "not used (clean passive data); +-100 uV epoch reject instead",
            "epoch_reject": "peak-to-peak 100 uV on EEG",
            "epoch_window_s": [TMIN, TMAX],
            "baseline_s": list(BASELINE),
            "min_trials": {"deviants": MIN_DEVIANTS, "standards": MIN_STANDARDS},
            "roi": ROI,
            "measure_window_s": list(WIN),
            "per_subject_details": details,
            "notes": notes,
        },
    }

    with open(OUT_JSON, "w") as fh:
        json.dump(result, fh, indent=2)

    log(
        f"\nAnalyzed {len(per_subject)}/{len(SUBJECTS)} subjects; "
        f"excluded {len(excluded)}; grand mean = {grand_mean} uV"
    )
    log(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
