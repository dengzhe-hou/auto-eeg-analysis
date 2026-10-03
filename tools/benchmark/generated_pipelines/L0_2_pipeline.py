#!/usr/bin/env python
"""
Auditory Mismatch Negativity (MMN) -- ERP CORE passive auditory oddball dataset.

For every subject (sub-001 ... sub-040) this script computes the deviant-minus-
standard difference wave and reports its mean amplitude over Fz, FCz and Cz in
the 100-250 ms post-stimulus window (microvolts).

Analysis choices (standard ERP practice for auditory MMN; see notes in the
emitted JSON):
  * EOG channels re-typed to 'eog' so they never enter referencing, artifact
    thresholds or the EEG average.
  * 'FP1'/'FP2' renamed to 'Fp1'/'Fp2' and a standard_1020 montage attached.
  * Events taken from the BIDS *_events.tsv `onset` column (seconds);
    value 80 = standard, 70 = deviant.  Value 180 (the first stream of
    standards, which cannot elicit a mismatch response) is discarded.
  * Zero-phase FIR band-pass 0.1-30 Hz.
  * Ocular correction by ICA (extended infomax) fitted on a 1-30 Hz copy,
    ocular components identified by correlation with the EOG channels.
  * Re-referenced to the average of P9/P10 (the mastoid-equivalent sites in
    this montage) -- the conventional reference for auditory MMN, since MMN
    inverts polarity below the Sylvian fissure.
  * Epochs -200 to 800 ms, baseline corrected on -200 to 0 ms, decimated to
    256 Hz, epochs with >150 uV peak-to-peak on any EEG channel rejected.
  * Subject-level averages per condition (trial counts NOT equalized: the
    extra standards simply give a cleaner standard ERP), difference wave =
    deviant - standard, then mean amplitude over Fz/FCz/Cz in 100-250 ms.
  * A subject is excluded if fewer than 20 artifact-free trials survive in
    either condition (or if the recording cannot be read).

Run standalone:  python pipeline.py
"""

from __future__ import annotations

import json
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

import mne

mne.set_log_level("ERROR")

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
DATA_ROOT = Path("/home/hou/mne_data/MNE-erpcoremmn2021-data")
OUT_DIR = Path(
    "/tmp/claude-1137/-home-hou-Research-auto-eeg-analysis/"
    "b4a153ed-22fa-4b6a-ad04-d134656fecf4/scratchpad/gen_scale/L0_2"
)
OUT_JSON = OUT_DIR / "result.json"

SUBJECTS = [f"sub-{i:03d}" for i in range(1, 41)]

EOG_CHANNELS = ["HEOG_left", "HEOG_right", "VEOG_lower"]
RENAME = {"FP1": "Fp1", "FP2": "Fp2"}
REF_CHANNELS = ["P9", "P10"]          # mastoid-equivalent reference
ROI = ["Fz", "FCz", "Cz"]             # fronto-central MMN cluster

STD_CODE, DEV_CODE = 80, 70           # 180 = first stream of standards (dropped)
EVENT_ID = {"standard": STD_CODE, "deviant": DEV_CODE}

L_FREQ, H_FREQ = 0.1, 30.0            # band-pass for the ERP
ICA_L_FREQ = 1.0                      # high-pass used only to fit the ICA
N_ICA_COMPONENTS = 20
ICA_FIT_DECIM = 8                     # 1024 Hz -> 128 Hz for the ICA fit
MAX_OCULAR_COMPONENTS = 4
RANDOM_STATE = 97

TMIN, TMAX = -0.2, 0.8
BASELINE = (-0.2, 0.0)
EPOCH_DECIM = 4                       # 1024 Hz -> 256 Hz
REJECT = dict(eeg=150e-6)             # peak-to-peak, volts

MEAS_WIN = (0.100, 0.250)             # measurement window, seconds
MIN_TRIALS = 20                       # per condition, after artifact rejection

NOTES = (
    "ERP CORE auditory oddball MMN. Per subject: read EEGLAB .set; re-typed "
    "HEOG_left/HEOG_right/VEOG_lower as EOG; renamed FP1/FP2 -> Fp1/Fp2 and set "
    "standard_1020 montage. Events read from the BIDS *_events.tsv 'onset' "
    "column (seconds), value 80 = standard, 70 = deviant; value 180 "
    "(first stream of standards) discarded. Zero-phase FIR band-pass "
    "0.1-30 Hz. Ocular artifacts corrected with extended-infomax ICA "
    "(20 components, fitted on a 1-30 Hz copy decimated to 128 Hz); ocular "
    "components found by EOG correlation (z>3, correlation>0.5 fallback, at "
    "most 4 removed). Re-referenced to the average of P9/P10 (mastoid "
    "equivalent, conventional for auditory MMN). Epochs -200 to 800 ms, "
    "baseline -200 to 0 ms, decimated to 256 Hz; epochs exceeding 150 uV "
    "peak-to-peak on any EEG channel rejected. Trial counts NOT equalized "
    "between conditions. Difference wave = deviant average - standard "
    "average; reported value = mean amplitude of that difference wave "
    "averaged over Fz, FCz, Cz and over 100-250 ms, in microvolts. Subjects "
    "with fewer than 20 surviving trials in either condition (or unreadable "
    "data) are excluded; grand_mean_uV is the unweighted mean over analyzed "
    "subjects."
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def load_annotations(events_tsv: Path) -> mne.Annotations:
    """Build MNE annotations for standard/deviant tones from the BIDS TSV."""
    df = pd.read_csv(events_tsv, sep="\t")
    values = pd.to_numeric(df["value"], errors="coerce")
    onsets = pd.to_numeric(df["onset"], errors="coerce")

    keep = values.isin([STD_CODE, DEV_CODE]) & onsets.notna()
    df = df.loc[keep]
    values = values.loc[keep].astype(int)
    onsets = onsets.loc[keep].astype(float)

    description = np.where(values.to_numpy() == DEV_CODE, "deviant", "standard")
    return mne.Annotations(
        onset=onsets.to_numpy(),
        duration=np.zeros(len(onsets)),
        description=description,
    )


def remove_ocular_components(raw: mne.io.BaseRaw) -> int:
    """Fit an ICA, drop EOG-correlated components in place.  Returns n removed."""
    raw_ica = raw.copy().filter(ICA_L_FREQ, H_FREQ, picks="eeg", verbose="ERROR")

    n_eeg = len(mne.pick_types(raw.info, eeg=True))
    ica = mne.preprocessing.ICA(
        n_components=min(N_ICA_COMPONENTS, n_eeg - 1),
        method="infomax",
        fit_params=dict(extended=True),
        max_iter="auto",
        random_state=RANDOM_STATE,
    )
    ica.fit(raw_ica, picks="eeg", decim=ICA_FIT_DECIM)

    bad_idx: list[int] = []
    try:
        bad_idx, _ = ica.find_bads_eog(raw_ica, ch_name=EOG_CHANNELS, threshold=3.0)
    except Exception:
        bad_idx = []

    if not bad_idx:
        try:
            bad_idx, _ = ica.find_bads_eog(
                raw_ica, ch_name=EOG_CHANNELS, measure="correlation", threshold=0.5
            )
        except Exception:
            bad_idx = []

    ica.exclude = sorted(set(int(i) for i in bad_idx))[:MAX_OCULAR_COMPONENTS]
    ica.apply(raw)
    del raw_ica
    return len(ica.exclude)


def process_subject(sub: str) -> dict:
    """Full single-subject pipeline.  Returns a result dict."""
    eeg_dir = DATA_ROOT / sub / "eeg"
    set_file = eeg_dir / f"{sub}_task-MMN_eeg.set"
    events_file = eeg_dir / f"{sub}_task-MMN_events.tsv"

    if not set_file.exists() or not events_file.exists():
        return dict(subject=sub, ok=False, reason="missing data file")

    raw = mne.io.read_raw_eeglab(set_file, preload=True, verbose="ERROR")

    # --- channel bookkeeping ------------------------------------------------
    raw.set_channel_types({ch: "eog" for ch in EOG_CHANNELS if ch in raw.ch_names})
    raw.rename_channels({k: v for k, v in RENAME.items() if k in raw.ch_names})
    raw.set_montage(
        mne.channels.make_standard_montage("standard_1020"),
        on_missing="ignore",
        verbose="ERROR",
    )

    missing_roi = [ch for ch in ROI + REF_CHANNELS if ch not in raw.ch_names]
    if missing_roi:
        return dict(subject=sub, ok=False, reason=f"missing channels {missing_roi}")

    # --- events -------------------------------------------------------------
    raw.set_annotations(load_annotations(events_file))

    # --- filtering ----------------------------------------------------------
    raw.filter(
        L_FREQ, H_FREQ, picks=["eeg", "eog"], method="fir", phase="zero",
        fir_design="firwin", verbose="ERROR",
    )

    # --- ocular correction --------------------------------------------------
    try:
        n_ica_removed = remove_ocular_components(raw)
    except Exception:
        n_ica_removed = -1  # ICA failed; fall through on filtered data only

    # --- reference ----------------------------------------------------------
    raw.set_eeg_reference(REF_CHANNELS, verbose="ERROR")

    # --- epoching -----------------------------------------------------------
    events, _ = mne.events_from_annotations(raw, event_id=EVENT_ID, verbose="ERROR")
    epochs = mne.Epochs(
        raw,
        events,
        event_id=EVENT_ID,
        tmin=TMIN,
        tmax=TMAX,
        baseline=BASELINE,
        picks=["eeg", "eog"],
        reject=REJECT,
        decim=EPOCH_DECIM,
        preload=True,
        verbose="ERROR",
    )

    n_std = len(epochs["standard"])
    n_dev = len(epochs["deviant"])
    if n_std < MIN_TRIALS or n_dev < MIN_TRIALS:
        return dict(
            subject=sub, ok=False,
            reason=f"too few clean trials (standard={n_std}, deviant={n_dev})",
        )

    # --- averaging and difference wave --------------------------------------
    ev_std = epochs["standard"].average(picks="eeg")
    ev_dev = epochs["deviant"].average(picks="eeg")
    diff = mne.combine_evoked([ev_dev, ev_std], weights=[1.0, -1.0])

    roi = diff.copy().pick(ROI).crop(*MEAS_WIN)
    amplitude_uv = float(roi.data.mean() * 1e6)

    return dict(
        subject=sub,
        ok=True,
        amplitude_uv=amplitude_uv,
        n_standard=n_std,
        n_deviant=n_dev,
        n_ica_removed=n_ica_removed,
    )


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    per_subject: dict[str, float] = {}
    raw_values: list[float] = []
    excluded: list[str] = []

    for sub in SUBJECTS:
        try:
            res = process_subject(sub)
        except Exception as exc:  # noqa: BLE001 - keep the batch alive
            print(f"[{sub}] FAILED: {exc}")
            traceback.print_exc()
            excluded.append(sub)
            continue

        if not res.get("ok"):
            print(f"[{sub}] excluded: {res.get('reason')}")
            excluded.append(sub)
            continue

        value = res["amplitude_uv"]
        raw_values.append(value)
        per_subject[sub] = round(value, 3)
        print(
            f"[{sub}] MMN = {value:+.3f} uV   "
            f"(std={res['n_standard']}, dev={res['n_deviant']}, "
            f"ICA removed={res['n_ica_removed']})"
        )

    grand_mean = round(float(np.mean(raw_values)), 3) if raw_values else None

    result = {
        "per_subject": per_subject,
        "excluded": excluded,
        "n_analyzed": len(per_subject),
        "grand_mean_uV": grand_mean,
        "choices": {"notes": NOTES},
    }

    with open(OUT_JSON, "w") as fh:
        json.dump(result, fh, indent=2)

    print(f"\nAnalyzed {len(per_subject)} subjects, excluded {len(excluded)}.")
    print(f"Grand mean MMN (Fz/FCz/Cz, 100-250 ms) = {grand_mean} uV")
    print(f"Wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
