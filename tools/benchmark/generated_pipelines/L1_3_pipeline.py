#!/usr/bin/env python3
"""Auditory Mismatch Negativity (MMN) pipeline on the ERP CORE MMN dataset.

Recipe
------
1. Preprocess : 0.1-30 Hz zero-phase FIR, drop dedicated EOG channels *before*
                referencing, average reference over scalp channels, RANSAC bad
                channel detection -> interpolation -> re-reference, resample to
                >= 200 Hz.
2. ICA        : skipped (ERP CORE MMN is clean passive-listening data); a
                +/-100 uV epoch rejection is used instead (documented in the
                "choices" block of the output JSON).
3. Epoch      : -0.2 to 0.5 s, baseline (-0.2, 0), +/-100 uV rejection,
                subjects with < 50 deviants or < 150 standards are excluded.
4. Measure    : deviant - standard difference wave, mean amplitude over
                Fz / FCz / Cz in the 100-250 ms window, in uV.

Run standalone:  python pipeline.py
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import traceback
import warnings
from pathlib import Path

import numpy as np

import mne

mne.set_log_level("ERROR")
warnings.filterwarnings("ignore")


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
DATA_ROOT = Path("/home/hou/mne_data/MNE-erpcoremmn2021-data")
OUT_DIR = Path(
    "/tmp/claude-1137/-home-hou-Research-auto-eeg-analysis/"
    "b4a153ed-22fa-4b6a-ad04-d134656fecf4/scratchpad/gen_scale/L1_3"
)
OUT_JSON = OUT_DIR / "result.json"

SUBJECTS = [f"sub-{i:03d}" for i in range(1, 41)]

# Dedicated EOG channels: the .set file types them as EEG, so drop them by name
# BEFORE the average reference is computed.
EOG_NAMES = ("HEOG_left", "HEOG_right", "VEOG_lower")

# Event codes in {sub}_task-MMN_events.tsv ("value" column).
CODE_STANDARD = 80          # 80 dB standard tone
CODE_DEVIANT = 70           # 70 dB deviant tone
CODE_FIRST_STREAM = 180     # first (familiarisation) stream -> excluded
EVENT_ID = {"standard": 1, "deviant": 2}

# Preprocessing
L_FREQ, H_FREQ = 0.1, 30.0          # zero-phase FIR bandpass
RESAMPLE_SFREQ = 256.0              # >= 200 Hz, integer decimation from 1024 Hz
MONTAGE_NAME = "standard_1020"

# Epoching
TMIN, TMAX = -0.2, 0.5
BASELINE = (-0.2, 0.0)
REJECT = dict(eeg=100e-6)           # peak-to-peak amplitude criterion
MIN_DEVIANTS = 50
MIN_STANDARDS = 150

# Measurement
MEAS_CHANNELS = ("Fz", "FCz", "Cz")
MEAS_TMIN, MEAS_TMAX = 0.100, 0.250

RANDOM_STATE = 42


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def read_events_tsv(path: Path):
    """Read a BIDS-style *_events.tsv; return (onsets [s], codes [int])."""
    onsets, codes = [], []
    with open(path, "r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        fields = reader.fieldnames or []
        if "onset" not in fields:
            raise ValueError(f"'onset' column missing in {path} (columns: {fields})")
        if "value" in fields:
            value_col = "value"
        elif "trial_type" in fields:
            value_col = "trial_type"
        else:
            raise ValueError(f"no 'value'/'trial_type' column in {path} (columns: {fields})")

        for row in reader:
            raw_onset = (row.get("onset") or "").strip()
            raw_value = (row.get(value_col) or "").strip()
            if not raw_onset or not raw_value:
                continue
            if raw_onset.lower() == "n/a" or raw_value.lower() == "n/a":
                continue
            try:
                onset = float(raw_onset)
                code = int(round(float(raw_value)))
            except ValueError:
                continue
            onsets.append(onset)
            codes.append(code)

    return np.asarray(onsets, dtype=float), np.asarray(codes, dtype=int)


def make_annotations(onsets: np.ndarray, codes: np.ndarray, tmax: float):
    """Keep only standards/deviants (drop the first-stream code) as Annotations."""
    keep_onsets, keep_desc = [], []
    n_first_stream = 0
    n_other = 0
    for onset, code in zip(onsets, codes):
        if code == CODE_STANDARD:
            desc = "standard"
        elif code == CODE_DEVIANT:
            desc = "deviant"
        else:
            if code == CODE_FIRST_STREAM:
                n_first_stream += 1
            else:
                n_other += 1
            continue
        # Skip events that fall outside the recording (rare bookkeeping rows).
        if onset < 0 or onset > tmax:
            continue
        keep_onsets.append(onset)
        keep_desc.append(desc)

    annot = mne.Annotations(
        onset=np.asarray(keep_onsets, dtype=float),
        duration=np.zeros(len(keep_onsets), dtype=float),
        description=np.asarray(keep_desc, dtype=object),
    )
    return annot, n_first_stream, n_other


def find_bad_channels_ransac(raw, n_jobs: int = 1):
    """RANSAC bad-channel detection.

    Prefers pyprep's ``NoisyChannels.find_bad_by_ransac`` (the reference RANSAC
    implementation); falls back to ``autoreject.Ransac`` on fixed-length epochs;
    finally degrades gracefully to "no detection" so the pipeline still runs.
    """
    # --- 1) pyprep -------------------------------------------------------- #
    try:
        from pyprep.find_noisy_channels import NoisyChannels  # type: ignore
    except Exception:
        NoisyChannels = None  # type: ignore
    if NoisyChannels is not None:
        try:
            work = raw.copy().pick("eeg")
            try:
                nd = NoisyChannels(work, do_detrend=False, random_state=RANDOM_STATE)
            except TypeError:
                nd = NoisyChannels(work, random_state=RANDOM_STATE)
            try:
                nd.find_bad_by_ransac(channel_wise=True)
            except TypeError:
                nd.find_bad_by_ransac()
            return sorted(set(nd.bad_by_ransac)), "pyprep.NoisyChannels.find_bad_by_ransac"
        except Exception as exc:  # pragma: no cover - environment dependent
            log(f"    [ransac] pyprep failed ({type(exc).__name__}: {exc}); trying autoreject")

    # --- 2) autoreject ---------------------------------------------------- #
    try:
        from autoreject import Ransac  # type: ignore
    except Exception:
        Ransac = None  # type: ignore
    if Ransac is not None:
        try:
            fixed = mne.make_fixed_length_epochs(
                raw.copy().pick("eeg"), duration=2.0, preload=True
            )
            rsc = Ransac(n_jobs=n_jobs, random_state=RANDOM_STATE, verbose=False)
            rsc.fit(fixed)
            return sorted(set(rsc.bad_chs_)), "autoreject.Ransac (2 s fixed-length epochs)"
        except Exception as exc:  # pragma: no cover - environment dependent
            log(f"    [ransac] autoreject failed ({type(exc).__name__}: {exc})")

    return [], "unavailable (no RANSAC backend installed; no channels interpolated)"


# --------------------------------------------------------------------------- #
# Per-subject pipeline
# --------------------------------------------------------------------------- #
def process_subject(sub: str, n_jobs: int = 1) -> dict:
    eeg_dir = DATA_ROOT / sub / "eeg"
    set_path = eeg_dir / f"{sub}_task-MMN_eeg.set"
    tsv_path = eeg_dir / f"{sub}_task-MMN_events.tsv"
    if not set_path.exists():
        raise FileNotFoundError(f"missing EEG file: {set_path}")
    if not tsv_path.exists():
        raise FileNotFoundError(f"missing events file: {tsv_path}")

    # ---- load ------------------------------------------------------------ #
    raw = mne.io.read_raw_eeglab(str(set_path), preload=True)

    # ---- drop dedicated EOG channels BEFORE referencing ------------------- #
    to_drop = {ch for ch in EOG_NAMES if ch in raw.ch_names}
    to_drop |= {
        ch
        for ch, ctype in zip(raw.ch_names, raw.get_channel_types())
        if ctype in ("eog", "misc", "stim")
    }
    if to_drop:
        raw.drop_channels(sorted(to_drop))

    # ---- montage (ERP CORE uses 'FP1'/'FP2' -> match_case=False) ---------- #
    montage = mne.channels.make_standard_montage(MONTAGE_NAME)
    raw.set_montage(montage, match_case=False, on_missing="warn")

    # ---- events from the BIDS TSV ---------------------------------------- #
    onsets, codes = read_events_tsv(tsv_path)
    annot, n_first_stream, n_other = make_annotations(
        onsets, codes, tmax=float(raw.times[-1])
    )
    if len(annot) == 0:
        raise ValueError("no standard/deviant events found in the events.tsv")
    raw.set_annotations(annot)

    # ---- bandpass (zero-phase FIR) --------------------------------------- #
    raw.filter(
        l_freq=L_FREQ,
        h_freq=H_FREQ,
        method="fir",
        phase="zero",
        fir_design="firwin",
        fir_window="hamming",
        n_jobs=n_jobs,
    )

    # ---- resample (>= 200 Hz; 1024 -> 256 Hz) ---------------------------- #
    if raw.info["sfreq"] > RESAMPLE_SFREQ:
        raw.resample(RESAMPLE_SFREQ, npad="auto", n_jobs=n_jobs)

    # ---- average reference, RANSAC -> interpolate -> re-reference --------- #
    raw.set_eeg_reference("average", projection=False)
    bads, ransac_method = find_bad_channels_ransac(raw, n_jobs=n_jobs)
    n_good = len(raw.ch_names) - len(bads)
    if bads and n_good >= 10:
        raw.info["bads"] = list(bads)
        raw.interpolate_bads(reset_bads=True)
        raw.set_eeg_reference("average", projection=False)  # re-reference
    elif bads:
        # Implausible detection (too many bads) -> keep the data as-is.
        log(f"    [ransac] {len(bads)} bads flagged for {sub}; ignoring as implausible")
        bads = []

    # ---- epoch ------------------------------------------------------------ #
    events, _ = mne.events_from_annotations(raw, event_id=EVENT_ID)
    epochs = mne.Epochs(
        raw,
        events,
        event_id=EVENT_ID,
        tmin=TMIN,
        tmax=TMAX,
        baseline=BASELINE,
        reject=REJECT,
        picks="eeg",
        preload=True,
        proj=False,
        on_missing="raise",
    )

    n_std_pre = int(np.sum(events[:, 2] == EVENT_ID["standard"]))
    n_dev_pre = int(np.sum(events[:, 2] == EVENT_ID["deviant"]))
    n_std = len(epochs["standard"])
    n_dev = len(epochs["deviant"])

    info = dict(
        n_standards=n_std,
        n_deviants=n_dev,
        n_standards_before_rejection=n_std_pre,
        n_deviants_before_rejection=n_dev_pre,
        n_first_stream_excluded=int(n_first_stream),
        n_other_codes_excluded=int(n_other),
        interpolated_channels=list(bads),
        ransac_method=ransac_method,
        sfreq=float(raw.info["sfreq"]),
    )

    if n_dev < MIN_DEVIANTS or n_std < MIN_STANDARDS:
        info["amplitude_uV"] = None
        info["reason"] = (
            f"too few trials after rejection: {n_dev} deviants "
            f"(min {MIN_DEVIANTS}), {n_std} standards (min {MIN_STANDARDS})"
        )
        return info

    # ---- measure: deviant - standard difference wave ---------------------- #
    ev_std = epochs["standard"].average()
    ev_dev = epochs["deviant"].average()
    diff = mne.combine_evoked([ev_dev, ev_std], weights=[1, -1])

    present = [ch for ch in MEAS_CHANNELS if ch in diff.ch_names]
    if not present:
        info["amplitude_uV"] = None
        info["reason"] = f"none of {list(MEAS_CHANNELS)} present in the data"
        return info
    if len(present) < len(MEAS_CHANNELS):
        info["measurement_channels_missing"] = [
            ch for ch in MEAS_CHANNELS if ch not in present
        ]

    seg = diff.copy().pick(present).crop(MEAS_TMIN, MEAS_TMAX)
    amp_uV = float(np.mean(seg.data) * 1e6)

    info["amplitude_uV"] = amp_uV
    info["measurement_channels"] = present
    info["n_measurement_samples"] = int(seg.data.shape[1])
    return info


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description="ERP CORE MMN pipeline")
    parser.add_argument("--subjects", nargs="*", default=SUBJECTS,
                        help="subject IDs (default: sub-001 ... sub-040)")
    parser.add_argument("--n-jobs", type=int, default=int(os.environ.get("N_JOBS", "1")),
                        help="n_jobs for filtering / resampling / RANSAC")
    parser.add_argument("--out", type=Path, default=OUT_JSON, help="output JSON path")
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)

    per_subject: dict[str, float] = {}
    excluded: list[str] = []
    exclusion_reasons: dict[str, str] = {}
    trial_counts: dict[str, dict] = {}
    interpolated: dict[str, list] = {}
    ransac_methods: set[str] = set()

    for i, sub in enumerate(args.subjects, start=1):
        log(f"[{i}/{len(args.subjects)}] {sub}")
        try:
            info = process_subject(sub, n_jobs=args.n_jobs)
        except Exception as exc:
            excluded.append(sub)
            exclusion_reasons[sub] = f"{type(exc).__name__}: {exc}"
            log(f"    FAILED: {type(exc).__name__}: {exc}")
            log("    " + traceback.format_exc().replace("\n", "\n    "))
            continue

        ransac_methods.add(info.get("ransac_method", "unknown"))
        trial_counts[sub] = {
            "standards": info["n_standards"],
            "deviants": info["n_deviants"],
            "standards_pre_rejection": info["n_standards_before_rejection"],
            "deviants_pre_rejection": info["n_deviants_before_rejection"],
        }
        if info.get("interpolated_channels"):
            interpolated[sub] = info["interpolated_channels"]

        amp = info.get("amplitude_uV")
        if amp is None:
            excluded.append(sub)
            exclusion_reasons[sub] = info.get("reason", "unknown")
            log(f"    EXCLUDED: {exclusion_reasons[sub]}")
        else:
            per_subject[sub] = round(float(amp), 3)
            log(
                f"    MMN = {amp:+.3f} uV  "
                f"(std={info['n_standards']}, dev={info['n_deviants']}, "
                f"interp={info['interpolated_channels']})"
            )

    values = [v for v in per_subject.values()]
    grand_mean = round(float(np.mean(values)), 3) if values else None

    choices = {
        "notes": (
            "ERP CORE MMN (sub-001..sub-040). Dedicated EOG channels "
            "(HEOG_left/HEOG_right/VEOG_lower) dropped by name before referencing. "
            "Montage standard_1020 with match_case=False. Bandpass 0.1-30 Hz "
            "zero-phase FIR (firwin/hamming), then resampled 1024 -> 256 Hz "
            "(integer factor, >= 200 Hz). Average reference over scalp channels, "
            "RANSAC bad-channel detection, interpolation, then average "
            "re-reference. ICA was NOT used: this is clean passive-listening data, "
            "so a +/-100 uV epoch rejection was used instead, as the recipe allows. "
            "Epochs -0.2 to 0.5 s, baseline (-0.2, 0). Events taken from the BIDS "
            "*_events.tsv 'value' column (80 = standard, 70 = deviant, 180 = "
            "first stream, excluded). Subjects with < 50 deviants or < 150 "
            "standards after rejection are excluded. Measure: deviant - standard "
            "difference wave, mean amplitude over Fz/FCz/Cz, 100-250 ms, in uV."
        ),
        "filter": {
            "l_freq_hz": L_FREQ,
            "h_freq_hz": H_FREQ,
            "method": "fir",
            "phase": "zero",
            "fir_design": "firwin",
            "fir_window": "hamming",
        },
        "resample_hz": RESAMPLE_SFREQ,
        "reference": "average over scalp EEG (EOG dropped first); re-applied after interpolation",
        "bad_channels": {
            "method": sorted(ransac_methods) if ransac_methods else ["n/a"],
            "action": "interpolate (spherical splines) then re-reference",
            "interpolated_per_subject": interpolated,
        },
        "ica": "not applied (clean passive data); +/-100 uV epoch rejection used instead",
        "epoch": {
            "tmin_s": TMIN,
            "tmax_s": TMAX,
            "baseline_s": list(BASELINE),
            "rejection": "peak-to-peak 100 uV on EEG (MNE reject=dict(eeg=100e-6)), "
                         "applied after baseline correction",
        },
        "min_trials": {"deviants": MIN_DEVIANTS, "standards": MIN_STANDARDS},
        "measurement": {
            "contrast": "deviant - standard",
            "channels": list(MEAS_CHANNELS),
            "window_s": [MEAS_TMIN, MEAS_TMAX],
            "statistic": "mean amplitude (uV)",
        },
        "trial_counts": trial_counts,
        "exclusion_reasons": exclusion_reasons,
        "mne_version": mne.__version__,
    }

    result = {
        "per_subject": per_subject,
        "excluded": excluded,
        "n_analyzed": len(per_subject),
        "grand_mean_uV": grand_mean,
        "choices": choices,
    }

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
        fh.write("\n")

    log(
        f"\nDone: {len(per_subject)} analyzed, {len(excluded)} excluded, "
        f"grand mean = {grand_mean} uV -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
