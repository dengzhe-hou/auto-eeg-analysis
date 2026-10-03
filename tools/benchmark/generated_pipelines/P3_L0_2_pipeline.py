#!/usr/bin/env python
"""
P3b (P300) analysis of the ERP CORE "P3" active visual oddball dataset.

Per subject:
  * target-minus-standard difference wave
  * mean amplitude over the Fz / Cz / Pz / CPz ROI in the 300-500 ms window (uV)

Pipeline (standard ERP practice, no external protocol):
  read .set -> bipolar HEOG -> montage -> 0.1-30 Hz FIR band-pass -> resample 256 Hz
  -> re-reference to the average of P9/P10 -> ICA ocular correction (EOG-guided)
  -> epoch -200..800 ms, baseline -200..0 ms -> +-100 uV peak-to-peak rejection
  -> condition averages -> difference wave -> ROI x time-window mean.

Standalone: `python pipeline.py`. Writes result.json next to this file.
"""

import json
import os
import traceback

import numpy as np
import pandas as pd

import mne

mne.set_log_level("ERROR")

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
BIDS_ROOT = "/home/hou/mne_data/erpcore-P3"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(OUT_DIR, "result.json")

SUBJECTS = [f"sub-{i:03d}" for i in range(1, 21)]

# Signal processing
L_FREQ = 0.1                 # high-pass (Hz)
H_FREQ = 30.0                # low-pass (Hz)
RESAMPLE_SFREQ = 256.0       # Hz (well above Nyquist for a 30 Hz low-pass)
REF_CHANNELS = ["P9", "P10"] # mastoid-equivalent linked reference (ERP CORE convention)

# ICA (ocular artifact correction)
ICA_N_COMPONENTS = 15
ICA_HP = 1.0                 # high-pass for the ICA-fitting copy only
ICA_RANDOM_STATE = 97
ICA_EOG_Z = 3.0
ICA_MAX_EXCLUDE = 3

# Epoching
TMIN, TMAX = -0.2, 0.8
BASELINE = (-0.2, 0.0)
REJECT_P2P = dict(eeg=100e-6)  # applied after ocular correction

# Measurement
ROI = ["Fz", "Cz", "Pz", "CPz"]
WIN = (0.300, 0.500)

# Quality control
MIN_TRIALS_PER_CONDITION = 10

EOG_RAW = ["HEOG_left", "HEOG_right", "VEOG_lower"]
EVENT_ID = {"standard": 1, "target": 2}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def load_events(events_tsv, sfreq, n_times, first_samp=0):
    """Build an MNE events array from the BIDS events.tsv.

    `value` is a 2-digit code 11-55: TENS = the block's target letter,
    UNITS = the letter shown on this trial.  TARGET iff tens == units.
    Codes 201/202 are button presses and are ignored.
    """
    df = pd.read_csv(events_tsv, sep="\t")
    val = pd.to_numeric(df["value"], errors="coerce")
    onset = pd.to_numeric(df["onset"], errors="coerce")

    tens = val // 10
    units = val % 10
    is_stim = (
        val.notna()
        & onset.notna()
        & val.between(11, 55)
        & tens.between(1, 5)
        & units.between(1, 5)
    )

    onset = onset[is_stim].to_numpy(dtype=float)
    tens = tens[is_stim].to_numpy(dtype=float)
    units = units[is_stim].to_numpy(dtype=float)

    codes = np.where(tens == units, EVENT_ID["target"], EVENT_ID["standard"])
    samples = np.round(onset * sfreq).astype(int) + int(first_samp)

    # Keep only events whose full epoch fits inside the recording.
    lo = int(first_samp) + int(np.ceil(abs(TMIN) * sfreq)) + 1
    hi = int(first_samp) + n_times - int(np.ceil(TMAX * sfreq)) - 1
    keep = (samples >= lo) & (samples <= hi)
    samples, codes = samples[keep], codes[keep]

    order = np.argsort(samples, kind="stable")
    samples, codes = samples[order], codes[order]

    # Guard against two events collapsing onto one sample after resampling.
    uniq = np.concatenate(([True], np.diff(samples) > 0))
    samples, codes = samples[uniq], codes[uniq]

    events = np.column_stack(
        [samples, np.zeros_like(samples), codes.astype(int)]
    ).astype(int)
    n_dropped = int(np.sum(~keep)) + int(np.sum(~uniq))
    return events, n_dropped


def preprocess(raw):
    """Filter, reference and ocular-correct a raw recording."""
    raw.rename_channels({"FP1": "Fp1", "FP2": "Fp2"})

    # Bipolar horizontal EOG; VEOG_lower is kept as the (monopolar) blink channel.
    raw = mne.set_bipolar_reference(
        raw, anode="HEOG_left", cathode="HEOG_right", ch_name="HEOG", drop_refs=True
    )
    raw.rename_channels({"VEOG_lower": "VEOG"})
    raw.set_channel_types({"HEOG": "eog", "VEOG": "eog"})

    raw.set_montage("standard_1005", match_case=False, on_missing="warn")

    # Band-pass (zero-phase FIR) on EEG + EOG.
    raw.filter(
        l_freq=L_FREQ,
        h_freq=H_FREQ,
        picks=["eeg", "eog"],
        method="fir",
        fir_design="firwin",
        phase="zero",
    )
    raw.resample(RESAMPLE_SFREQ, npad="auto")

    # Re-reference the scalp EEG (BioSemi is recorded against CMS and must be
    # re-referenced offline).
    raw.set_eeg_reference(ref_channels=REF_CHANNELS, projection=False)

    # ---- ICA ocular correction -------------------------------------------- #
    n_excluded = 0
    try:
        raw_ica = raw.copy().filter(
            l_freq=ICA_HP,
            h_freq=None,
            picks=["eeg", "eog"],
            method="fir",
            fir_design="firwin",
            phase="zero",
        )
        ica = mne.preprocessing.ICA(
            n_components=ICA_N_COMPONENTS,
            method="fastica",
            max_iter="auto",
            random_state=ICA_RANDOM_STATE,
        )
        ica.fit(raw_ica, picks="eeg", reject=dict(eeg=500e-6), tstep=2.0)

        bad_idx, scores = ica.find_bads_eog(
            raw_ica, ch_name=["VEOG", "HEOG"], threshold=ICA_EOG_Z
        )
        if len(bad_idx) > ICA_MAX_EXCLUDE:
            strength = np.max(np.abs(np.atleast_2d(scores)), axis=0)
            bad_idx = list(
                np.array(bad_idx)[np.argsort(strength[bad_idx])[::-1]][:ICA_MAX_EXCLUDE]
            )
        ica.exclude = sorted(int(i) for i in bad_idx)
        n_excluded = len(ica.exclude)
        if n_excluded:
            ica.apply(raw)
        del raw_ica
    except Exception:
        n_excluded = -1  # ICA failed; rely on peak-to-peak rejection alone

    return raw, n_excluded


def roi_mean_uv(evoked):
    """Mean amplitude (uV) over the ROI channels and the measurement window."""
    picks = [evoked.ch_names.index(ch) for ch in ROI]
    tmask = (evoked.times >= WIN[0] - 1e-9) & (evoked.times <= WIN[1] + 1e-9)
    return float(evoked.data[picks][:, tmask].mean() * 1e6)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def analyze_subject(sub):
    eeg_dir = os.path.join(BIDS_ROOT, sub, "eeg")
    set_path = os.path.join(eeg_dir, f"{sub}_task-P3_eeg.set")
    tsv_path = os.path.join(eeg_dir, f"{sub}_task-P3_events.tsv")

    raw = mne.io.read_raw_eeglab(set_path, preload=True)
    raw, n_ica = preprocess(raw)

    events, _ = load_events(
        tsv_path, raw.info["sfreq"], raw.n_times, first_samp=raw.first_samp
    )

    epochs = mne.Epochs(
        raw,
        events,
        event_id=EVENT_ID,
        tmin=TMIN,
        tmax=TMAX,
        baseline=BASELINE,
        picks=["eeg"],
        reject=REJECT_P2P,
        preload=True,
        reject_by_annotation=True,
        proj=False,
    )

    n_tar = len(epochs["target"])
    n_std = len(epochs["standard"])
    info = {
        "n_target": n_tar,
        "n_standard": n_std,
        "n_presented": int(events.shape[0]),
        "ica_components_removed": n_ica,
    }

    if n_tar < MIN_TRIALS_PER_CONDITION or n_std < MIN_TRIALS_PER_CONDITION:
        raise RuntimeError(
            f"too few surviving trials (target={n_tar}, standard={n_std}; "
            f"minimum {MIN_TRIALS_PER_CONDITION} per condition)"
        )

    ev_tar = epochs["target"].average()
    ev_std = epochs["standard"].average()
    diff = mne.combine_evoked([ev_tar, ev_std], weights=[1, -1])

    info["p3b_uV"] = roi_mean_uv(diff)
    return info


def main():
    per_subject, excluded, reasons, details = {}, [], {}, {}

    for sub in SUBJECTS:
        try:
            info = analyze_subject(sub)
            per_subject[sub] = round(info.pop("p3b_uV"), 3)
            details[sub] = info
            print(f"{sub}: {per_subject[sub]:+.3f} uV  {info}", flush=True)
        except Exception as exc:
            excluded.append(sub)
            reasons[sub] = f"{type(exc).__name__}: {exc}"
            print(f"{sub}: EXCLUDED -- {reasons[sub]}", flush=True)
            traceback.print_exc()

    vals = list(per_subject.values())
    grand = round(float(np.mean(vals)), 3) if vals else None

    result = {
        "per_subject": per_subject,
        "excluded": excluded,
        "n_analyzed": len(per_subject),
        "grand_mean_uV": grand,
        "choices": {
            "notes": (
                "ERP CORE P3 visual oddball. TARGET = tens digit == units digit of the "
                "2-digit stimulus code (11/22/33/44/55), STANDARD = all other stimulus "
                "codes 11-55; response codes 201/202 ignored and no accuracy-based trial "
                "screening applied. Reference: BioSemi data are recorded against CMS, so "
                "the scalp EEG was re-referenced offline to the average of P9 and P10 "
                "(the mastoid-equivalent linked reference used by ERP CORE for the P3). "
                "FP1/FP2 renamed Fp1/Fp2 and a standard_1005 montage applied. HEOG "
                "derived bipolarly as HEOG_left - HEOG_right; VEOG_lower kept as the "
                "blink channel; all three retyped as EOG so they are excluded from the "
                "scalp average and from epoch rejection. Zero-phase FIR band-pass "
                "0.1-30 Hz, then resampled 1024 -> 256 Hz. Ocular artifacts corrected "
                "with FastICA (15 components, fit on a 1 Hz high-passed copy) removing "
                "components correlated with VEOG/HEOG at |z| > 3 (max 3 components). "
                "Epochs -200 to 800 ms, baseline-corrected on -200 to 0 ms, rejected at "
                "100 uV peak-to-peak across the 30 scalp channels. Difference wave = "
                "target-average minus standard-average. P3b = mean amplitude of the "
                "difference wave averaged over Fz, Cz, Pz, CPz and over 300-500 ms. "
                "No manual bad-channel interpolation. A subject is excluded if either "
                "condition retains fewer than 10 artifact-free trials or if loading "
                "fails."
            ),
            "reference": "average of P9 and P10 (offline re-reference from CMS)",
            "filter_hz": [L_FREQ, H_FREQ],
            "filter_design": "zero-phase FIR (firwin), applied to EEG and EOG",
            "resample_hz": RESAMPLE_SFREQ,
            "artifact_correction": (
                f"FastICA n_components={ICA_N_COMPONENTS}, EOG-correlation "
                f"|z|>{ICA_EOG_Z}, max {ICA_MAX_EXCLUDE} components removed"
            ),
            "epoch_s": [TMIN, TMAX],
            "baseline_s": list(BASELINE),
            "rejection_uV_p2p": 100,
            "roi": ROI,
            "window_ms": [int(WIN[0] * 1000), int(WIN[1] * 1000)],
            "measure": "mean amplitude of the target-minus-standard difference wave",
            "target_rule": "tens digit == units digit (11, 22, 33, 44, 55)",
            "min_trials_per_condition": MIN_TRIALS_PER_CONDITION,
            "exclusion_reasons": reasons,
            "per_subject_details": details,
        },
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nWrote {OUT_JSON}  (n={len(per_subject)}, grand mean={grand} uV)")


if __name__ == "__main__":
    main()
