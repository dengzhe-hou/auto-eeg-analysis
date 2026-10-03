#!/usr/bin/env python
"""
Auditory Mismatch Negativity (MMN) pipeline -- ERP CORE MMN (sub-001 ... sub-040).

Implements the recipe:
  1. Preprocess : 0.1-30 Hz zero-phase FIR, drop EOG, RANSAC -> interpolate ->
                  average reference of scalp channels, resample to 256 Hz.
  2. ICA        : not used (ERP CORE MMN is clean passive data); a simple
                  +/-100 uV epoch rejection is used instead, as the recipe allows.
  3. Epoch      : -0.2 to 0.5 s, baseline (-0.2, 0), reject +/-100 uV,
                  require >= 50 deviants and >= 150 standards after rejection.
  4. Measure    : deviant - standard difference wave, mean amplitude over
                  Fz/FCz/Cz in the 100-250 ms window, in microvolts.

Standalone: python pipeline.py
"""

import csv
import json
import os
import sys
import traceback

import numpy as np
import mne

mne.set_log_level("ERROR")

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
DATA_ROOT = "/home/hou/mne_data/MNE-erpcoremmn2021-data"
OUT_DIR = (
    "/tmp/claude-1137/-home-hou-Research-auto-eeg-analysis/"
    "b4a153ed-22fa-4b6a-ad04-d134656fecf4/scratchpad/gen_scale/L1_7"
)
OUT_JSON = os.path.join(OUT_DIR, "result.json")

SUBJECTS = ["sub-%03d" % i for i in range(1, 41)]

TASK = "MMN"

# Event codes in the BIDS events.tsv `value` column.
CODE_STANDARD = 80
CODE_DEVIANT = 70
CODE_FIRST_STREAM = 180  # excluded

# EOG channels are typed as EEG in the .set file -> drop them by name so they
# never enter the average reference.
EOG_NAMES = ["HEOG_left", "HEOG_right", "VEOG_lower"]

# Filtering / resampling
L_FREQ = 0.1
H_FREQ = 30.0
SFREQ_TARGET = 256.0  # >= 200 Hz, integer decimation of the 1024 Hz original

# Epoching
TMIN, TMAX = -0.2, 0.5
BASELINE = (-0.2, 0.0)
REJECT = dict(eeg=100e-6)  # +/- 100 uV (MNE stores EEG in volts)

# Minimum trial counts after rejection
MIN_DEVIANTS = 50
MIN_STANDARDS = 150

# Measurement
ROI = ["Fz", "FCz", "Cz"]
WIN_TMIN, WIN_TMAX = 0.100, 0.250

RANDOM_STATE = 42

CHOICES = {
    "filter": (
        "0.1-30 Hz zero-phase FIR (firwin, Hamming, 'auto' transition "
        "bandwidths), applied at the native 1024 Hz before resampling"
    ),
    "resample_hz": SFREQ_TARGET,
    "reference": "average of the 30 scalp EEG channels (EOG dropped first)",
    "bad_channels": (
        "autoreject.Ransac fitted on unreferenced, baseline-corrected epochs; "
        "flagged channels interpolated on the continuous data (spherical "
        "splines) and then included in the average reference"
    ),
    "ica": (
        "not used -- ERP CORE MMN is clean passive data, so only the +/-100 uV "
        "peak-to-peak epoch rejection is applied (option explicitly allowed by "
        "the recipe)"
    ),
    "montage": "standard_1020 with match_case=False (handles 'FP1'/'FP2')",
    "events": (
        "read from *_events.tsv `value` column: 80=standard, 70=deviant; "
        "180 (first-stream) excluded. Onsets (seconds) attached as annotations "
        "so that sample indices stay exact across resampling."
    ),
    "measure": (
        "deviant-minus-standard difference of the two per-subject evoked "
        "averages; amplitude = mean over Fz/FCz/Cz and over all samples with "
        "0.100 s <= t <= 0.250 s, converted to uV"
    ),
    "random_state": RANDOM_STATE,
    "notes": (
        "Unweighted per-condition averages (each condition averaged over its "
        "own surviving trials); the grand mean is the unweighted mean of the "
        "per-subject amplitudes. Subjects with <50 deviants or <150 standards "
        "after rejection, or that fail to process, are listed in 'excluded'. "
        "All reported values rounded to 3 decimal places."
    ),
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def read_events_tsv(path):
    """Return (onsets_sec, codes) for stimulus rows with value in {70, 80}."""
    onsets, codes = [], []
    with open(path, "r", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            raw_val = (row.get("value") or "").strip()
            raw_onset = (row.get("onset") or "").strip()
            if not raw_val or not raw_onset or raw_val == "n/a" or raw_onset == "n/a":
                continue
            try:
                code = int(float(raw_val))
                onset = float(raw_onset)
            except ValueError:
                continue
            if code in (CODE_STANDARD, CODE_DEVIANT):
                onsets.append(onset)
                codes.append(code)
            # CODE_FIRST_STREAM (180) and any other codes are dropped.
    order = np.argsort(np.asarray(onsets, dtype=float), kind="stable")
    onsets = np.asarray(onsets, dtype=float)[order]
    codes = np.asarray(codes, dtype=int)[order]
    return onsets, codes


def load_raw(subject):
    """Load raw EEG, drop EOG, set montage."""
    set_path = os.path.join(
        DATA_ROOT, subject, "eeg", "%s_task-%s_eeg.set" % (subject, TASK)
    )
    raw = mne.io.read_raw_eeglab(set_path, preload=True)

    drop = [ch for ch in EOG_NAMES if ch in raw.ch_names]
    if drop:
        raw.drop_channels(drop)

    raw.set_channel_types({ch: "eeg" for ch in raw.ch_names})
    raw.set_montage("standard_1020", match_case=False, on_missing="raise")
    return raw


def attach_events_as_annotations(raw, subject):
    """Attach standard/deviant onsets as annotations (robust to resampling)."""
    ev_path = os.path.join(
        DATA_ROOT, subject, "eeg", "%s_task-%s_events.tsv" % (subject, TASK)
    )
    onsets, codes = read_events_tsv(ev_path)
    if len(onsets) == 0:
        raise RuntimeError("no standard/deviant events found")

    desc = np.where(codes == CODE_DEVIANT, "deviant", "standard")
    annot = mne.Annotations(
        onset=onsets, duration=np.zeros_like(onsets), description=desc
    )
    raw.set_annotations(annot)
    return raw


def make_epochs(raw, reject=None):
    events, event_id_all = mne.events_from_annotations(
        raw, event_id={"standard": CODE_STANDARD, "deviant": CODE_DEVIANT}
    )
    event_id = {k: v for k, v in event_id_all.items() if k in ("standard", "deviant")}
    epochs = mne.Epochs(
        raw,
        events,
        event_id=event_id,
        tmin=TMIN,
        tmax=TMAX,
        baseline=BASELINE,
        reject=reject,
        preload=True,
        proj=False,
        picks="eeg",
        reject_by_annotation=False,
        verbose=False,
    )
    return epochs


def find_bads_ransac(epochs):
    """RANSAC bad-channel detection; returns a list of channel names."""
    try:
        from autoreject import Ransac
    except Exception:
        return []  # RANSAC unavailable -> no channels flagged
    ransac = Ransac(n_jobs=1, random_state=RANDOM_STATE, verbose=False)
    ransac.fit(epochs)
    return list(ransac.bad_chs_)


def roi_window_amplitude_uv(evoked_diff):
    """Mean amplitude (uV) over ROI channels within the measurement window."""
    picks = [evoked_diff.ch_names.index(ch) for ch in ROI]
    times = evoked_diff.times
    tol = 1e-9
    mask = (times >= WIN_TMIN - tol) & (times <= WIN_TMAX + tol)
    if not mask.any():
        raise RuntimeError("empty measurement window")
    data = evoked_diff.data[np.ix_(picks, np.where(mask)[0])]  # volts
    return float(data.mean() * 1e6)


# --------------------------------------------------------------------------- #
# Per-subject pipeline
# --------------------------------------------------------------------------- #
def process_subject(subject):
    raw = load_raw(subject)
    raw = attach_events_as_annotations(raw, subject)

    # --- 1. Filter (zero-phase FIR) then resample -------------------------- #
    raw.filter(
        l_freq=L_FREQ,
        h_freq=H_FREQ,
        method="fir",
        phase="zero",
        fir_window="hamming",
        fir_design="firwin",
        l_trans_bandwidth="auto",
        h_trans_bandwidth="auto",
        n_jobs=1,
        verbose=False,
    )
    if raw.info["sfreq"] > SFREQ_TARGET:
        raw.resample(SFREQ_TARGET, npad="auto", verbose=False)

    # --- 2. RANSAC bad channels -> interpolate ----------------------------- #
    epochs_for_ransac = make_epochs(raw, reject=None)
    bads = find_bads_ransac(epochs_for_ransac)
    del epochs_for_ransac

    raw.info["bads"] = sorted(set(bads))
    if raw.info["bads"]:
        raw.interpolate_bads(reset_bads=True, mode="accurate", verbose=False)

    # --- 3. Average reference over scalp channels -------------------------- #
    raw.set_eeg_reference("average", projection=False, ch_type="eeg", verbose=False)

    # --- 4. Epoch with +/-100 uV rejection --------------------------------- #
    epochs = make_epochs(raw, reject=REJECT)

    n_dev = len(epochs["deviant"])
    n_std = len(epochs["standard"])
    if n_dev < MIN_DEVIANTS or n_std < MIN_STANDARDS:
        raise RuntimeError(
            "too few trials after rejection (deviants=%d < %d or standards=%d < %d)"
            % (n_dev, MIN_DEVIANTS, n_std, MIN_STANDARDS)
        )

    # --- 5. Difference wave and measurement -------------------------------- #
    ev_dev = epochs["deviant"].average()
    ev_std = epochs["standard"].average()
    missing = [ch for ch in ROI if ch not in ev_dev.ch_names]
    if missing:
        raise RuntimeError("missing ROI channels: %s" % missing)

    diff = mne.combine_evoked([ev_dev, ev_std], weights=[1, -1])
    amp_uv = roi_window_amplitude_uv(diff)

    return amp_uv, dict(n_deviants=n_dev, n_standards=n_std, bads=list(bads))


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    per_subject = {}
    excluded = []

    for subject in SUBJECTS:
        try:
            amp_uv, info = process_subject(subject)
            per_subject[subject] = round(float(amp_uv), 3)
            print(
                "[ok]   %s  amp=%8.3f uV   deviants=%3d standards=%3d  bads=%s"
                % (
                    subject,
                    amp_uv,
                    info["n_deviants"],
                    info["n_standards"],
                    info["bads"] if info["bads"] else "-",
                ),
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            excluded.append(subject)
            print("[skip] %s  %s" % (subject, exc), flush=True)
            if os.environ.get("MMN_DEBUG"):
                traceback.print_exc(file=sys.stdout)

    values = np.asarray(list(per_subject.values()), dtype=float)
    grand_mean = round(float(values.mean()), 3) if values.size else None

    result = {
        "per_subject": per_subject,
        "excluded": excluded,
        "n_analyzed": len(per_subject),
        "grand_mean_uV": grand_mean,
        "choices": CHOICES,
    }

    with open(OUT_JSON, "w") as fh:
        json.dump(result, fh, indent=2)

    print(
        "\nn_analyzed=%d  excluded=%d  grand_mean_uV=%s\nwrote %s"
        % (len(per_subject), len(excluded), grand_mean, OUT_JSON)
    )


if __name__ == "__main__":
    main()
