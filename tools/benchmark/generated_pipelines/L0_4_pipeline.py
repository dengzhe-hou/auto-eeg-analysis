#!/usr/bin/env python
"""
Auditory Mismatch Negativity (MMN) from the ERP CORE passive auditory oddball task.

For every subject the deviant-minus-standard difference wave is computed and the
mean amplitude over Fz / FCz / Cz in the 100-250 ms post-stimulus window is
reported in microvolts.

Run standalone:  python pipeline.py
"""

import json
import os
import warnings

import numpy as np
import pandas as pd

import mne

mne.set_log_level("ERROR")
warnings.filterwarnings("ignore")

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
DATA_ROOT = "/home/hou/mne_data/MNE-erpcoremmn2021-data"
OUT_DIR = (
    "/tmp/claude-1137/-home-hou-Research-auto-eeg-analysis/"
    "b4a153ed-22fa-4b6a-ad04-d134656fecf4/scratchpad/gen_scale/L0_4"
)
OUT_JSON = os.path.join(OUT_DIR, "result.json")

SUBJECTS = [f"sub-{i:03d}" for i in range(1, 41)]

# Event codes in the BIDS *_events.tsv "value" column
CODE_STANDARD = 80
CODE_DEVIANT = 70
CODE_FIRST_STREAM = 180  # first-stream standards -> not analysed

# EOG channels are typed as EEG inside the .set file; retype them.
EOG_CHANNELS = ["HEOG_left", "HEOG_right", "VEOG_lower"]

# Filtering (non-causal FIR, zero phase)
L_FREQ = 0.1   # Hz  high-pass
H_FREQ = 30.0  # Hz  low-pass

# Epoching
TMIN, TMAX = -0.2, 0.5            # s
BASELINE = (-0.2, 0.0)            # s, pre-stimulus baseline correction

# Artifact rejection: peak-to-peak amplitude on scalp EEG channels
REJECT = dict(eeg=100e-6)         # 100 uV

# Reference: average of P9 / P10 (mastoid-equivalent), the canonical
# reference for the auditory MMN in this electrode montage.
REF_CHANNELS = ["P9", "P10"]

# Measurement
ROI = ["Fz", "FCz", "Cz"]
WIN = (0.100, 0.250)              # s

MIN_TRIALS = 10                   # per condition, after artifact rejection


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def load_events(events_tsv, sfreq, n_times):
    """Build an MNE events array from the BIDS events.tsv onsets (seconds)."""
    df = pd.read_csv(events_tsv, sep="\t")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["onset"] = pd.to_numeric(df["onset"], errors="coerce")
    df = df[df["value"].isin([CODE_STANDARD, CODE_DEVIANT])].dropna(
        subset=["onset", "value"]
    )

    samples = np.round(df["onset"].to_numpy(float) * sfreq).astype(int)
    codes = df["value"].to_numpy(float).astype(int)

    # keep only events for which a full epoch fits inside the recording
    lo = int(np.ceil(-TMIN * sfreq)) + 1
    hi = n_times - int(np.ceil(TMAX * sfreq)) - 1
    keep = (samples >= lo) & (samples <= hi)
    samples, codes = samples[keep], codes[keep]

    events = np.column_stack(
        [samples, np.zeros_like(samples), codes]
    ).astype(int)
    # events must be ordered by sample for MNE
    events = events[np.argsort(events[:, 0])]
    return events


def prepare_raw(set_path):
    """Read, retype, montage, filter and re-reference one subject's raw file."""
    raw = mne.io.read_raw_eeglab(set_path, preload=True)

    # 1) The .set file labels the three EOG channels as EEG -> retype them so
    #    they are excluded from the reference, the ROI and the EEG rejection.
    present_eog = [ch for ch in EOG_CHANNELS if ch in raw.ch_names]
    if present_eog:
        raw.set_channel_types({ch: "eog" for ch in present_eog})

    # 2) Harmonise naming with the standard 10-05 montage (FP1 -> Fp1).
    rename = {ch: ch.capitalize() for ch in ("FP1", "FP2") if ch in raw.ch_names}
    if rename:
        raw.rename_channels(rename)
    try:
        raw.set_montage("standard_1005", match_case=False, on_missing="ignore")
    except Exception:
        pass  # montage is cosmetic here; not required for the measurement

    # 3) Band-pass filter (zero-phase FIR) before epoching.
    raw.filter(L_FREQ, H_FREQ, picks=["eeg", "eog"], fir_design="firwin",
               phase="zero", verbose="ERROR")

    # 4) Re-reference the scalp EEG to the average of P9 / P10.
    ref = [ch for ch in REF_CHANNELS if ch in raw.ch_names]
    if len(ref) == len(REF_CHANNELS):
        raw.set_eeg_reference(ref_channels=ref, projection=False)
    else:  # fall back to a common average reference if P9/P10 are unavailable
        raw.set_eeg_reference("average", projection=False)

    return raw


def subject_mmn(subject):
    """Return (mmn_uV, info_dict) for one subject, or (None, info_dict)."""
    eeg_dir = os.path.join(DATA_ROOT, subject, "eeg")
    set_path = os.path.join(eeg_dir, f"{subject}_task-MMN_eeg.set")
    tsv_path = os.path.join(eeg_dir, f"{subject}_task-MMN_events.tsv")
    info = {}

    if not (os.path.exists(set_path) and os.path.exists(tsv_path)):
        info["reason"] = "missing file"
        return None, info

    raw = prepare_raw(set_path)
    sfreq = raw.info["sfreq"]

    events = load_events(tsv_path, sfreq, raw.n_times)
    if events.shape[0] == 0:
        info["reason"] = "no usable events"
        return None, info

    event_id = {"standard": CODE_STANDARD, "deviant": CODE_DEVIANT}
    epochs = mne.Epochs(
        raw,
        events,
        event_id=event_id,
        tmin=TMIN,
        tmax=TMAX,
        baseline=BASELINE,
        picks=["eeg", "eog"],
        reject=REJECT,
        reject_by_annotation=False,
        preload=True,
        verbose="ERROR",
    )
    del raw

    n_std = len(epochs["standard"])
    n_dev = len(epochs["deviant"])
    info["n_standard"] = int(n_std)
    info["n_deviant"] = int(n_dev)

    if n_std < MIN_TRIALS or n_dev < MIN_TRIALS:
        info["reason"] = f"too few clean trials (std={n_std}, dev={n_dev})"
        return None, info

    roi = [ch for ch in ROI if ch in epochs.ch_names]
    if not roi:
        info["reason"] = "ROI channels absent"
        return None, info
    info["roi"] = roi

    ev_std = epochs["standard"].average(picks=roi)
    ev_dev = epochs["deviant"].average(picks=roi)
    diff = mne.combine_evoked([ev_dev, ev_std], weights=[1, -1])  # deviant - standard

    tmask = (diff.times >= WIN[0]) & (diff.times <= WIN[1])
    # mean over the window, then over the ROI channels; V -> uV
    mmn_uV = float(diff.data[:, tmask].mean() * 1e6)

    del epochs
    return mmn_uV, info


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    per_subject = {}
    excluded = []
    details = {}

    for subject in SUBJECTS:
        try:
            value, info = subject_mmn(subject)
        except Exception as exc:  # keep the batch alive on a single bad file
            value, info = None, {"reason": f"{type(exc).__name__}: {exc}"}

        details[subject] = info
        if value is None or not np.isfinite(value):
            excluded.append(subject)
            print(f"{subject}: EXCLUDED ({info.get('reason', 'unknown')})")
        else:
            per_subject[subject] = round(value, 3)
            print(
                f"{subject}: MMN = {per_subject[subject]:+.3f} uV "
                f"(std={info.get('n_standard')}, dev={info.get('n_deviant')})"
            )

    values = list(per_subject.values())
    grand_mean = round(float(np.mean(values)), 3) if values else None

    result = {
        "per_subject": per_subject,
        "excluded": excluded,
        "n_analyzed": len(per_subject),
        "grand_mean_uV": grand_mean,
        "choices": {
            "notes": (
                "MNE-Python pipeline, one pass per subject. "
                "Raw EEGLAB .set read with mne.io.read_raw_eeglab (data already in "
                "volts after MNE's uV->V conversion). The three ocular channels "
                "(HEOG_left, HEOG_right, VEOG_lower), which the .set file mislabels "
                "as EEG, are retyped to EOG so they are excluded from the reference, "
                "the rejection criterion and the ROI. FP1/FP2 renamed to Fp1/Fp2 and "
                "the standard_1005 montage attached. "
                "Zero-phase FIR band-pass 0.1-30 Hz (firwin) applied to the "
                "continuous data at the native 1024 Hz; no resampling (a windowed "
                "mean amplitude is insensitive to sampling rate). "
                "Scalp EEG re-referenced offline to the average of P9 and P10, the "
                "mastoid-equivalent reference conventionally used for the auditory "
                "MMN with this montage (falls back to a common average reference if "
                "P9/P10 are missing). "
                "Events taken from the BIDS *_events.tsv 'onset' column (seconds x "
                "sfreq, rounded): value 80 = standard, 70 = deviant; value 180 "
                "(first-stream standards) and all non-stimulus codes are discarded, "
                "as are any events whose epoch would run past the recording edges. "
                "All 80-coded standards are used (no post-deviant exclusion, no "
                "trial-count equalisation, so the standard ERP is maximally clean). "
                "Epochs -200 to +500 ms, baseline-corrected on the -200 to 0 ms "
                "pre-stimulus interval. Artifact rejection by peak-to-peak amplitude "
                "> 100 uV on scalp EEG channels (Fp1/Fp2 are included, so blinks are "
                "caught by this criterion); no ICA, to keep the pipeline "
                "deterministic. "
                "Condition averages computed separately, then the difference wave "
                "deviant - standard via mne.combine_evoked(weights=[1, -1]). "
                "MMN = mean of the difference wave over 100-250 ms, averaged across "
                "Fz, FCz and Cz, converted to microvolts (negative = MMN present). "
                "A subject is excluded only if the file is unreadable or fewer than "
                "10 artifact-free trials remain in either condition."
            ),
            "filter_hz": [L_FREQ, H_FREQ],
            "reference": "average of P9 and P10",
            "epoch_s": [TMIN, TMAX],
            "baseline_s": list(BASELINE),
            "rejection_peak_to_peak_uV": {"eeg": 100},
            "ica": False,
            "roi": ROI,
            "measurement_window_s": list(WIN),
            "measure": "mean amplitude of deviant-minus-standard difference wave",
            "trials": {"standard": CODE_STANDARD, "deviant": CODE_DEVIANT,
                       "discarded": CODE_FIRST_STREAM},
            "per_subject_trial_counts": {
                s: {k: v for k, v in d.items() if k.startswith("n_")}
                for s, d in details.items()
            },
        },
    }

    with open(OUT_JSON, "w") as fh:
        json.dump(result, fh, indent=2)

    print(f"\nAnalyzed {result['n_analyzed']}/{len(SUBJECTS)} subjects; "
          f"grand mean MMN = {grand_mean} uV")
    print(f"Wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
