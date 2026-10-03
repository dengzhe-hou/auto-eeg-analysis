#!/usr/bin/env python
"""
Auditory Mismatch Negativity (MMN) from the ERP CORE MMN dataset.

For every subject (sub-001 ... sub-040) the script:
  1. loads the EEGLAB recording,
  2. marks the three ocular channels as EOG (they are typed EEG in the .set),
  3. renames FP1/FP2 -> Fp1/Fp2 and attaches the standard_1005 montage,
  4. band-pass filters 0.1-30 Hz (zero-phase FIR),
  5. re-references the EEG to the average of the mastoid-adjacent sites P9/P10
     (the classic MMN reference, also the ERP CORE reference),
  6. epochs -200 to +500 ms around standards (value 80) and deviants (value 70),
     baseline corrects on -200..0 ms and rejects epochs by peak-to-peak amplitude,
  7. averages each condition and forms the deviant-minus-standard difference wave,
  8. measures the mean amplitude of that difference wave over Fz/FCz/Cz in the
     100-250 ms post-stimulus window (microvolts).

Events with value 180 (the leading "first-stream" standards) are discarded.

Run standalone:  python pipeline.py
"""

import csv
import json
import traceback
from pathlib import Path

import numpy as np
import mne

mne.set_log_level("ERROR")

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
DATA_ROOT = Path("/home/hou/mne_data/MNE-erpcoremmn2021-data")
OUT_DIR = Path(
    "/tmp/claude-1137/-home-hou-Research-auto-eeg-analysis/"
    "b4a153ed-22fa-4b6a-ad04-d134656fecf4/scratchpad/gen_scale/L0_3"
)
OUT_JSON = OUT_DIR / "result.json"

SUBJECTS = [f"sub-{i:03d}" for i in range(1, 41)]

EOG_CHANNELS = ["HEOG_left", "HEOG_right", "VEOG_lower"]
RENAME = {"FP1": "Fp1", "FP2": "Fp2"}
REF_CHANNELS = ["P9", "P10"]          # mastoid-adjacent linked reference
ROI = ["Fz", "FCz", "Cz"]             # fronto-central MMN cluster

STANDARD_CODE = 80
DEVIANT_CODE = 70                     # 180 = first-stream standards -> dropped

L_FREQ, H_FREQ = 0.1, 30.0            # band-pass (Hz)
TMIN, TMAX = -0.2, 0.5                # epoch limits (s)
BASELINE = (-0.2, 0.0)                # pre-stimulus baseline (s)
MEAS_WIN = (0.100, 0.250)             # MMN measurement window (s)
DECIM_TO = 256.0                      # epochs are decimated to this rate (Hz)

REJECT = dict(eeg=100e-6, eog=150e-6)  # peak-to-peak artifact thresholds (V)
MIN_TRIALS = 20                        # min. retained epochs per condition


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def read_events(tsv_path, sfreq, n_times):
    """Build an MNE events array from a BIDS *_events.tsv file."""
    rows = []
    with open(tsv_path, newline="") as fid:
        reader = csv.DictReader(fid, delimiter="\t")
        for row in reader:
            try:
                code = int(round(float(row["value"])))
                onset = float(row["onset"])
            except (KeyError, TypeError, ValueError):
                continue
            if code not in (STANDARD_CODE, DEVIANT_CODE):
                continue  # drops the 180 first-stream standards
            samp = int(round(onset * sfreq))
            if 0 <= samp < n_times:
                rows.append((samp, 0, code))

    if not rows:
        return np.empty((0, 3), dtype=int)

    events = np.array(rows, dtype=int)
    events = events[np.argsort(events[:, 0], kind="stable")]
    # guard against duplicated latencies (MNE requires unique, ascending samples)
    _, keep = np.unique(events[:, 0], return_index=True)
    return events[np.sort(keep)]


def preprocess_raw(set_path):
    """Load and clean one recording."""
    raw = mne.io.read_raw_eeglab(set_path, preload=True)

    present_eog = [ch for ch in EOG_CHANNELS if ch in raw.ch_names]
    if present_eog:
        raw.set_channel_types({ch: "eog" for ch in present_eog})

    raw.rename_channels({old: new for old, new in RENAME.items()
                         if old in raw.ch_names})
    try:
        raw.set_montage("standard_1005", match_case=False, on_missing="ignore")
    except Exception:
        pass  # montage is cosmetic here; the measurement does not need it

    raw.filter(l_freq=L_FREQ, h_freq=H_FREQ, method="fir",
               fir_design="firwin", phase="zero", verbose="ERROR")

    refs = [ch for ch in REF_CHANNELS if ch in raw.ch_names]
    if len(refs) == len(REF_CHANNELS):
        raw.set_eeg_reference(ref_channels=refs, verbose="ERROR")
    else:  # fall back to an average reference if P9/P10 are unavailable
        raw.set_eeg_reference(ref_channels="average", verbose="ERROR")

    return raw


def mmn_for_subject(subject):
    """Return (value_uV, info_dict). Raises on unusable data."""
    eeg_dir = DATA_ROOT / subject / "eeg"
    set_path = eeg_dir / f"{subject}_task-MMN_eeg.set"
    tsv_path = eeg_dir / f"{subject}_task-MMN_events.tsv"
    if not set_path.exists():
        raise FileNotFoundError(str(set_path))
    if not tsv_path.exists():
        raise FileNotFoundError(str(tsv_path))

    raw = preprocess_raw(str(set_path))
    sfreq = raw.info["sfreq"]

    events = read_events(tsv_path, sfreq, raw.n_times)
    if events.size == 0:
        raise RuntimeError("no usable events")

    decim = max(1, int(round(sfreq / DECIM_TO)))
    epochs = mne.Epochs(
        raw, events,
        event_id={"standard": STANDARD_CODE, "deviant": DEVIANT_CODE},
        tmin=TMIN, tmax=TMAX, baseline=BASELINE,
        reject=REJECT, decim=decim, preload=True,
        reject_by_annotation=True, proj=False, verbose="ERROR",
    )

    n_std = len(epochs["standard"])
    n_dev = len(epochs["deviant"])
    if n_std < MIN_TRIALS or n_dev < MIN_TRIALS:
        raise RuntimeError(
            f"too few clean epochs (standard={n_std}, deviant={n_dev})")

    ev_std = epochs["standard"].average()
    ev_dev = epochs["deviant"].average()
    diff = mne.combine_evoked([ev_dev, ev_std], weights=[1, -1])

    missing = [ch for ch in ROI if ch not in diff.ch_names]
    if missing:
        raise RuntimeError(f"missing ROI channels: {missing}")

    roi = diff.copy().pick(ROI).crop(tmin=MEAS_WIN[0], tmax=MEAS_WIN[1])
    value_uV = float(roi.data.mean() * 1e6)

    info = dict(n_standard=int(n_std), n_deviant=int(n_dev),
                n_events=int(events.shape[0]))
    return value_uV, info


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    per_subject = {}
    excluded = []
    detail = {}

    for subject in SUBJECTS:
        try:
            value_uV, info = mmn_for_subject(subject)
        except Exception as exc:  # noqa: BLE001 - keep the batch running
            excluded.append(subject)
            detail[subject] = f"{type(exc).__name__}: {exc}"
            print(f"[{subject}] EXCLUDED -> {detail[subject]}")
            traceback.print_exc()
            continue

        per_subject[subject] = round(value_uV, 3)
        detail[subject] = info
        print(f"[{subject}] MMN = {value_uV:+.3f} uV "
              f"(std={info['n_standard']}, dev={info['n_deviant']})")

    values = list(per_subject.values())
    grand_mean = round(float(np.mean(values)), 3) if values else None

    result = {
        "per_subject": per_subject,
        "excluded": excluded,
        "n_analyzed": len(per_subject),
        "grand_mean_uV": grand_mean,
        "choices": {
            "notes": (
                "ERP CORE MMN pipeline in MNE-Python. EOG channels "
                "(HEOG_left/HEOG_right/VEOG_lower) retyped as EOG so they are "
                "excluded from referencing and get their own rejection "
                "threshold; FP1/FP2 renamed to Fp1/Fp2 and standard_1005 "
                "montage attached. Zero-phase FIR band-pass 0.1-30 Hz on the "
                "continuous data, then EEG re-referenced to the average of "
                "P9/P10 (mastoid-adjacent linked reference, standard for MMN "
                "and used by ERP CORE). Events taken from *_events.tsv "
                "(sample = round(onset*sfreq)); value 80 = standard, 70 = "
                "deviant, value 180 (first-stream standards) discarded. Epochs "
                "-200 to +500 ms, baseline -200 to 0 ms, decimated to ~256 Hz, "
                "artifact rejection by peak-to-peak amplitude (EEG 100 uV, EOG "
                "150 uV); no ICA. Condition averages subtracted "
                "(deviant - standard) and the difference wave averaged over "
                "Fz, FCz, Cz and over 100-250 ms; reported in microvolts. "
                "A subject is excluded only if a file is missing/unreadable or "
                "fewer than 20 clean epochs remain in either condition."
            ),
            "reference": "average of P9 and P10",
            "filter_hz": [L_FREQ, H_FREQ],
            "epoch_s": [TMIN, TMAX],
            "baseline_s": list(BASELINE),
            "measurement_window_s": list(MEAS_WIN),
            "roi": ROI,
            "artifact_rejection_uV": {"eeg_ptp": 100, "eog_ptp": 150},
            "min_trials_per_condition": MIN_TRIALS,
            "decimated_sfreq_hz": DECIM_TO,
            "per_subject_detail": detail,
        },
    }

    with open(OUT_JSON, "w") as fid:
        json.dump(result, fid, indent=2)

    print(f"\nAnalyzed {len(per_subject)}/{len(SUBJECTS)} subjects; "
          f"grand mean = {grand_mean} uV")
    print(f"Wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
