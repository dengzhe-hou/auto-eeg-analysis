#!/usr/bin/env python3
"""Auditory Mismatch Negativity (MMN) pipeline -- ERP CORE MMN (sub-001 ... sub-040).

Recipe
------
1. Preprocess : 0.1-30 Hz zero-phase FIR, drop dedicated EOG channels, RANSAC bad
   channel detection -> interpolate -> average reference of the scalp channels,
   resample to 256 Hz (>= 200 Hz).
2. ICA        : skipped (ERP CORE MMN is passive/clean); a +/-100 uV epoch reject is
   used instead, as explicitly permitted by the recipe.
3. Epoch      : -0.2 .. 0.5 s, baseline (-0.2, 0), reject 100 uV peak-to-peak,
   subject kept only with >= 50 deviants and >= 150 standards after rejection.
4. Measure    : per-subject (deviant - standard) difference wave, mean amplitude over
   Fz/FCz/Cz in the 100-250 ms window, reported in microvolts.

Event codes in `*_task-MMN_events.tsv`: 80 = standard, 70 = deviant,
180 = first-stream trials (excluded).

Standalone: `python pipeline.py`. Writes result.json next to this file.
"""

from __future__ import annotations

import json
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

import mne

mne.set_log_level("ERROR")

# --------------------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------------------
DATA_ROOT = Path("/home/hou/mne_data/MNE-erpcoremmn2021-data")
OUT_DIR = Path(
    "/tmp/claude-1137/-home-hou-Research-auto-eeg-analysis/"
    "b4a153ed-22fa-4b6a-ad04-d134656fecf4/scratchpad/gen_scale/L1_5"
)
OUT_JSON = OUT_DIR / "result.json"

SUBJECTS = [f"sub-{i:03d}" for i in range(1, 41)]

EOG_NAMES = ["HEOG_left", "HEOG_right", "VEOG_lower"]

L_FREQ, H_FREQ = 0.1, 30.0
RESAMPLE_SFREQ = 256.0          # integer decimation of 1024 Hz, comfortably >= 200 Hz

TMIN, TMAX = -0.2, 0.5
BASELINE = (-0.2, 0.0)
REJECT = dict(eeg=100e-6)       # 100 uV peak-to-peak on any scalp channel

CODE_STANDARD, CODE_DEVIANT, CODE_FIRST_STREAM = 80, 70, 180
EVENT_ID = {"standard": CODE_STANDARD, "deviant": CODE_DEVIANT}

MIN_DEVIANTS, MIN_STANDARDS = 50, 150

MEAS_CHANNELS = ["Fz", "FCz", "Cz"]
WIN_TMIN, WIN_TMAX = 0.100, 0.250

RANDOM_STATE = 97


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------
def read_events_tsv(path: Path, sfreq: float) -> np.ndarray:
    """Build an MNE events array from the BIDS *_events.tsv file.

    `onset` is in seconds relative to the start of the recording; EEGLAB raws have
    ``first_samp == 0`` so the sample index is simply round(onset * sfreq).
    Only the standard (80) and deviant (70) codes are kept; the first-stream code
    (180) is dropped.
    """
    df = pd.read_csv(path, sep="\t")
    if "onset" not in df.columns or "value" not in df.columns:
        raise RuntimeError(f"{path.name}: missing 'onset'/'value' columns")

    onset = pd.to_numeric(df["onset"], errors="coerce")
    value = pd.to_numeric(df["value"], errors="coerce")
    keep = onset.notna() & value.isin([CODE_STANDARD, CODE_DEVIANT])

    samples = np.round(onset[keep].to_numpy(dtype=float) * sfreq).astype(int)
    codes = value[keep].to_numpy(dtype=int)

    events = np.column_stack([samples, np.zeros_like(samples), codes])
    # keep chronological order and drop accidental duplicate sample indices
    events = events[np.argsort(events[:, 0], kind="stable")]
    _, uniq = np.unique(events[:, 0], return_index=True)
    return events[np.sort(uniq)]


def detect_bads_ransac(raw: mne.io.BaseRaw) -> tuple[list[str], str]:
    """RANSAC-based bad-channel detection.

    Prefers pyprep's `NoisyChannels.find_bad_by_ransac` (operates on continuous data);
    falls back to autoreject's `Ransac` on fixed-length epochs if pyprep is missing.
    """
    try:
        try:
            from pyprep import NoisyChannels  # type: ignore
        except ImportError:
            from pyprep.find_noisy_channels import NoisyChannels  # type: ignore

        nd = NoisyChannels(raw.copy(), random_state=RANDOM_STATE, do_detrend=False)
        nd.find_bad_by_ransac(channel_wise=False)
        return sorted(set(nd.bad_by_ransac)), "pyprep.NoisyChannels.find_bad_by_ransac"
    except ImportError:
        pass

    try:
        from autoreject import Ransac  # type: ignore

        tmp = mne.make_fixed_length_epochs(raw.copy(), duration=1.0, preload=True)
        rsc = Ransac(n_jobs=1, random_state=RANDOM_STATE, verbose=False)
        rsc.fit(tmp)
        return sorted(set(rsc.bad_chs_)), "autoreject.Ransac (1 s fixed-length epochs)"
    except ImportError:
        return [], "unavailable (neither pyprep nor autoreject installed)"


def mean_amplitude_uV(evoked: mne.Evoked) -> float:
    """Mean amplitude (uV) over MEAS_CHANNELS within [WIN_TMIN, WIN_TMAX]."""
    picked = evoked.copy().pick(MEAS_CHANNELS)
    times = picked.times
    mask = (times >= WIN_TMIN - 1e-9) & (times <= WIN_TMAX + 1e-9)
    if not mask.any():
        raise RuntimeError("measurement window contains no samples")
    return float(picked.data[:, mask].mean() * 1e6)


# --------------------------------------------------------------------------------------
# Per-subject processing
# --------------------------------------------------------------------------------------
def process_subject(sub: str) -> dict:
    """Return a diagnostics dict; ``value`` is None when the subject is excluded."""
    eeg_dir = DATA_ROOT / sub / "eeg"
    set_path = eeg_dir / f"{sub}_task-MMN_eeg.set"
    tsv_path = eeg_dir / f"{sub}_task-MMN_events.tsv"

    if not set_path.exists():
        return {"value": None, "reason": f"missing file {set_path.name}"}
    if not tsv_path.exists():
        return {"value": None, "reason": f"missing file {tsv_path.name}"}

    raw = mne.io.read_raw_eeglab(set_path, preload=True)

    # --- drop the dedicated EOG channels (typed as EEG in the .set) before anything
    # that mixes channels together (interpolation / average reference).
    to_drop = [ch for ch in EOG_NAMES if ch in raw.ch_names]
    if to_drop:
        raw.drop_channels(to_drop)
    raw.pick("eeg")

    # --- montage (ERP CORE uses 'FP1'/'FP2', hence match_case=False)
    raw.set_montage("standard_1020", match_case=False, on_missing="raise")

    # --- bandpass 0.1-30 Hz, zero-phase FIR
    raw.filter(
        l_freq=L_FREQ,
        h_freq=H_FREQ,
        method="fir",
        phase="zero",
        fir_design="firwin",
        fir_window="hamming",
        n_jobs=1,
    )

    # --- downsample (1024 -> 256 Hz). Events are rebuilt from the TSV onsets in
    # seconds afterwards, so no event-jitter from resampling.
    orig_sfreq = float(raw.info["sfreq"])
    if orig_sfreq > RESAMPLE_SFREQ:
        raw.resample(RESAMPLE_SFREQ, npad="auto")
    sfreq = float(raw.info["sfreq"])

    # --- RANSAC -> interpolate -> average reference
    bads, ransac_backend = detect_bads_ransac(raw)
    raw.info["bads"] = bads
    if bads:
        raw.interpolate_bads(reset_bads=True)
    raw.set_eeg_reference("average", projection=False)

    # --- events
    events = read_events_tsv(tsv_path, sfreq=sfreq)
    n_std_raw = int((events[:, 2] == CODE_STANDARD).sum())
    n_dev_raw = int((events[:, 2] == CODE_DEVIANT).sum())
    if n_std_raw == 0 or n_dev_raw == 0:
        return {
            "value": None,
            "reason": f"no usable events (standards={n_std_raw}, deviants={n_dev_raw})",
        }

    # --- epoch + artifact rejection
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
        reject_by_annotation=False,
        on_missing="warn",
    )

    n_std = len(epochs["standard"])
    n_dev = len(epochs["deviant"])
    if n_dev < MIN_DEVIANTS or n_std < MIN_STANDARDS:
        return {
            "value": None,
            "reason": (
                f"too few trials after rejection (deviants={n_dev} < {MIN_DEVIANTS}"
                if n_dev < MIN_DEVIANTS
                else f"too few trials after rejection (standards={n_std} < {MIN_STANDARDS}"
            )
            + f"; kept {n_std}/{n_std_raw} standards, {n_dev}/{n_dev_raw} deviants)",
            "n_standards": n_std,
            "n_deviants": n_dev,
        }

    # --- deviant - standard difference wave
    ev_std = epochs["standard"].average()
    ev_dev = epochs["deviant"].average()
    diff = mne.combine_evoked([ev_dev, ev_std], weights=[1.0, -1.0])

    value = mean_amplitude_uV(diff)

    return {
        "value": value,
        "reason": None,
        "n_standards": n_std,
        "n_deviants": n_dev,
        "n_standards_available": n_std_raw,
        "n_deviants_available": n_dev_raw,
        "bads_ransac": bads,
        "ransac_backend": ransac_backend,
        "sfreq_hz": sfreq,
    }


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------
def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    per_subject: dict[str, float] = {}
    excluded: list[str] = []
    reasons: dict[str, str] = {}
    diagnostics: dict[str, dict] = {}
    ransac_backends: set[str] = set()

    for sub in SUBJECTS:
        try:
            info = process_subject(sub)
        except Exception as exc:  # noqa: BLE001 - one bad subject must not kill the run
            print(f"[{sub}] FAILED: {exc}", flush=True)
            traceback.print_exc()
            excluded.append(sub)
            reasons[sub] = f"processing error: {type(exc).__name__}: {exc}"
            continue

        if info.get("ransac_backend"):
            ransac_backends.add(info["ransac_backend"])

        diagnostics[sub] = {
            k: v for k, v in info.items() if k not in ("value", "reason")
        }

        if info["value"] is None:
            excluded.append(sub)
            reasons[sub] = info["reason"]
            print(f"[{sub}] excluded: {info['reason']}", flush=True)
        else:
            per_subject[sub] = round(float(info["value"]), 3)
            print(
                f"[{sub}] MMN = {per_subject[sub]:+.3f} uV "
                f"(std={info['n_standards']}, dev={info['n_deviants']}, "
                f"bads={info['bads_ransac']})",
                flush=True,
            )

    n_analyzed = len(per_subject)
    grand_mean = (
        round(float(np.mean(list(per_subject.values()))), 3) if n_analyzed else None
    )

    result = {
        "per_subject": per_subject,
        "excluded": excluded,
        "n_analyzed": n_analyzed,
        "grand_mean_uV": grand_mean,
        "choices": {
            "notes": (
                "ERP CORE MMN, sub-001..sub-040. Per subject: read .set with "
                "read_raw_eeglab; the 3 dedicated EOG channels (HEOG_left, HEOG_right, "
                "VEOG_lower) are dropped by name BEFORE any interpolation/referencing so "
                "they never enter the average reference; montage standard_1020 with "
                "match_case=False; 0.1-30 Hz zero-phase FIR (firwin/hamming, MNE 'auto' "
                "transition bands); resample 1024 -> 256 Hz (integer factor, >= 200 Hz); "
                "RANSAC bad-channel detection -> spherical-spline interpolation -> "
                "average reference over the 30 scalp channels; NO ICA (recipe allows the "
                "simple route for this clean passive dataset), artifact control is the "
                "epoch-level peak-to-peak reject; epochs -0.2..0.5 s, baseline "
                "(-0.2, 0) s, reject=dict(eeg=100e-6); subjects with < 50 deviants or "
                "< 150 standards surviving rejection are excluded; deviant (70) minus "
                "standard (80) difference wave via mne.combine_evoked(weights=[1, -1]); "
                "reported value is the mean amplitude over Fz/FCz/Cz in 100-250 ms, in "
                "uV, rounded to 3 decimals. Events come from the BIDS *_events.tsv "
                "('onset' seconds -> sample index at the post-resample sfreq, "
                "first_samp = 0 for EEGLAB), code 180 (first stream) excluded."
            ),
            "filter": {
                "l_freq_hz": L_FREQ,
                "h_freq_hz": H_FREQ,
                "method": "fir",
                "phase": "zero",
                "fir_design": "firwin",
                "fir_window": "hamming",
            },
            "resample_sfreq_hz": RESAMPLE_SFREQ,
            "eog_channels_dropped": EOG_NAMES,
            "reference": "average of the 30 scalp EEG channels (after interpolation)",
            "bad_channels": {
                "method": "RANSAC",
                "backend": sorted(ransac_backends) if ransac_backends else ["n/a"],
                "random_state": RANDOM_STATE,
                "handling": "interpolate_bads(reset_bads=True), then re-reference",
            },
            "ica": "not applied (clean passive paradigm); +/-100 uV epoch reject used instead",
            "epoching": {
                "tmin_s": TMIN,
                "tmax_s": TMAX,
                "baseline_s": list(BASELINE),
                "reject_uV_peak_to_peak": 100.0,
                "reject_interpretation": (
                    "'+/-100 uV' implemented as MNE reject=dict(eeg=100e-6), i.e. a "
                    "100 uV peak-to-peak limit per epoch on any scalp channel"
                ),
            },
            "min_trials": {"deviants": MIN_DEVIANTS, "standards": MIN_STANDARDS},
            "measurement": {
                "channels": MEAS_CHANNELS,
                "window_s": [WIN_TMIN, WIN_TMAX],
                "contrast": "deviant (70) - standard (80)",
                "statistic": "mean amplitude across the 3 channels and the window, uV",
            },
            "exclusion_reasons": reasons,
            "per_subject_diagnostics": diagnostics,
            "software": {
                "mne": mne.__version__,
                "numpy": np.__version__,
                "pandas": pd.__version__,
            },
        },
    }

    with open(OUT_JSON, "w") as fh:
        json.dump(result, fh, indent=2)

    print(
        f"\nAnalyzed {n_analyzed}/{len(SUBJECTS)} subjects; "
        f"excluded {len(excluded)} ({', '.join(excluded) if excluded else 'none'}); "
        f"grand mean = {grand_mean} uV",
        flush=True,
    )
    print(f"Wrote {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
