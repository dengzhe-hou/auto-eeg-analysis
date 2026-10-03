#!/usr/bin/env python3
"""
Auditory Mismatch Negativity (MMN) from the ERP CORE MMN dataset (BIDS-like layout).

Per subject:
  * read continuous EEGLAB recording
  * standard preprocessing (montage, filtering, mastoid-equivalent re-reference)
  * epoch standards (value 80) and deviants (value 70)
  * artifact rejection
  * MMN difference wave = deviant  MINUS  standard
  * dependent measure = mean amplitude of the difference wave over the
    frontocentral ROI {Fz, FCz, Cz} in the 100-250 ms window, in microvolts

Writes a JSON summary next to this script. Standalone: `python pipeline.py`.
"""

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
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(OUT_DIR, "result.json")

SUBJECTS = [f"sub-{i:03d}" for i in range(1, 41)]

EOG_CHANNELS = ["HEOG_left", "HEOG_right", "VEOG_lower"]
RENAME = {"FP1": "Fp1", "FP2": "Fp2"}  # match the 10-05 montage naming

# Reference: average of P9/P10 (mastoid-equivalent). This is the conventional
# choice for auditory MMN -- the MMN generator in auditory cortex is a
# tangential dipole that inverts polarity at/below the mastoids, so a
# mastoid-type reference maximises the frontocentral negativity. It is also the
# reference used in the ERP CORE reference pipeline for this paradigm.
REF_CHANNELS = ["P9", "P10"]

L_FREQ = 0.1          # Hz, high-pass (removes drift, safe for ERP mean amplitude)
H_FREQ = 30.0         # Hz, low-pass (removes muscle/line noise)

TMIN, TMAX = -0.2, 0.8          # s, epoch window
BASELINE = (-0.2, 0.0)          # s, pre-stimulus baseline correction

EVENT_ID = {"standard": 80, "deviant": 70}   # 180 = first-stream standards, dropped

REJECT_P2P_EEG = 100e-6         # V, peak-to-peak epoch rejection on scalp EEG
REJECT_P2P_EOG = 200e-6         # V, peak-to-peak epoch rejection on EOG (blinks)

ROI = ["Fz", "FCz", "Cz"]
WIN_START, WIN_END = 0.100, 0.250   # s, MMN measurement window

MIN_EPOCHS_PER_COND = 20        # subject-level data-quality criterion


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def read_events_tsv(path, sfreq, n_times):
    """Parse the BIDS events.tsv -> MNE events array (n, 3) using `onset` (s)."""
    with open(path, "r") as fh:
        lines = [ln.rstrip("\n") for ln in fh if ln.strip()]
    header = lines[0].split("\t")
    i_onset = header.index("onset")
    i_value = header.index("value")

    rows = []
    for ln in lines[1:]:
        parts = ln.split("\t")
        if len(parts) <= max(i_onset, i_value):
            continue
        raw_val = parts[i_value].strip()
        try:
            code = int(float(raw_val))
        except ValueError:
            continue  # e.g. STATUS/boundary rows with non-numeric codes
        if code not in EVENT_ID.values():
            continue  # drops 180 (first stream of standards) and anything else
        try:
            onset = float(parts[i_onset])
        except ValueError:
            continue
        samp = int(round(onset * sfreq))
        if 0 <= samp < n_times:
            rows.append([samp, 0, code])

    events = np.asarray(rows, dtype=int)
    if events.size == 0:
        return np.empty((0, 3), dtype=int)
    # guarantee monotonically increasing, unique sample indices
    events = events[np.argsort(events[:, 0])]
    _, keep = np.unique(events[:, 0], return_index=True)
    return events[np.sort(keep)]


def mark_bad_channels(raw):
    """Flag flat / grossly noisy scalp channels so they don't nuke every epoch."""
    picks = mne.pick_types(raw.info, eeg=True, eog=False, exclude=[])
    if len(picks) < 4:
        return []
    data = raw.get_data(picks=picks)
    sds = np.std(data, axis=1)
    med = np.median(sds)
    bads = []
    for ch_i, sd in zip(picks, sds):
        name = raw.ch_names[ch_i]
        if sd < 1e-8 or (med > 0 and sd > 5.0 * med):
            bads.append(name)
    # never discard the reference or the ROI channels this way
    bads = [b for b in bads if b not in REF_CHANNELS and b not in ROI]
    return bads


def mean_amplitude(evoked, roi, tmin, tmax):
    """Mean amplitude (microvolts) over `roi` channels within [tmin, tmax] s."""
    picks = [evoked.ch_names.index(ch) for ch in roi]
    times = evoked.times
    mask = (times >= tmin - 1e-9) & (times <= tmax + 1e-9)
    if not mask.any():
        raise RuntimeError("measurement window falls outside the epoch")
    seg = evoked.data[np.ix_(picks, np.flatnonzero(mask))]
    return float(seg.mean() * 1e6)   # V -> microvolts


# --------------------------------------------------------------------------- #
# Per-subject pipeline
# --------------------------------------------------------------------------- #
def process_subject(sub):
    eeg_path = os.path.join(DATA_ROOT, sub, "eeg", f"{sub}_task-MMN_eeg.set")
    evt_path = os.path.join(DATA_ROOT, sub, "eeg", f"{sub}_task-MMN_events.tsv")
    if not os.path.exists(eeg_path):
        raise FileNotFoundError(eeg_path)
    if not os.path.exists(evt_path):
        raise FileNotFoundError(evt_path)

    raw = mne.io.read_raw_eeglab(eeg_path, preload=True)

    # --- channel bookkeeping ------------------------------------------------
    ren = {k: v for k, v in RENAME.items() if k in raw.ch_names}
    if ren:
        raw.rename_channels(ren)
    eog_present = [ch for ch in EOG_CHANNELS if ch in raw.ch_names]
    if eog_present:
        raw.set_channel_types({ch: "eog" for ch in eog_present})
    try:
        raw.set_montage("standard_1005", on_missing="ignore", match_case=False)
    except Exception:
        pass

    missing_roi = [ch for ch in ROI if ch not in raw.ch_names]
    if missing_roi:
        raise RuntimeError(f"missing ROI channel(s): {missing_roi}")

    # --- filtering (before referencing / epoching) ---------------------------
    raw.filter(L_FREQ, H_FREQ, picks=["eeg", "eog"],
               method="fir", phase="zero", fir_design="firwin")

    # --- bad-channel handling ------------------------------------------------
    bads = mark_bad_channels(raw)
    raw.info["bads"] = sorted(set(list(raw.info["bads"]) + bads))
    interpolated = list(raw.info["bads"])
    if interpolated:
        try:
            raw.interpolate_bads(reset_bads=True)
        except Exception:
            raw.info["bads"] = []   # no digitisation -> just keep the channels

    # --- re-reference ---------------------------------------------------------
    ref_present = [ch for ch in REF_CHANNELS if ch in raw.ch_names]
    if len(ref_present) == len(REF_CHANNELS):
        raw.set_eeg_reference(ref_present, projection=False)
        ref_used = "+".join(ref_present) + " (average)"
    else:
        raw.set_eeg_reference("average", projection=False)
        ref_used = "average of all scalp electrodes (P9/P10 unavailable)"

    # --- events ---------------------------------------------------------------
    sfreq = raw.info["sfreq"]
    events = read_events_tsv(evt_path, sfreq, raw.n_times)
    n_std_raw = int(np.sum(events[:, 2] == EVENT_ID["standard"])) if events.size else 0
    n_dev_raw = int(np.sum(events[:, 2] == EVENT_ID["deviant"])) if events.size else 0
    if n_std_raw == 0 or n_dev_raw == 0:
        raise RuntimeError(f"no usable events (std={n_std_raw}, dev={n_dev_raw})")

    # --- epoching + artifact rejection ---------------------------------------
    reject = {"eeg": REJECT_P2P_EEG}
    if eog_present:
        reject["eog"] = REJECT_P2P_EOG

    epochs = mne.Epochs(
        raw, events, event_id=EVENT_ID, tmin=TMIN, tmax=TMAX,
        baseline=BASELINE, picks=["eeg", "eog"], reject=reject,
        preload=True, reject_by_annotation=True, verbose=False,
    )

    n_std = len(epochs["standard"])
    n_dev = len(epochs["deviant"])
    if n_std < MIN_EPOCHS_PER_COND or n_dev < MIN_EPOCHS_PER_COND:
        raise RuntimeError(
            f"too few surviving epochs (standard={n_std}, deviant={n_dev}; "
            f"minimum {MIN_EPOCHS_PER_COND} per condition)"
        )

    ev_std = epochs["standard"].average(picks="eeg")
    ev_dev = epochs["deviant"].average(picks="eeg")
    diff = mne.combine_evoked([ev_dev, ev_std], weights=[1, -1])   # deviant - standard

    amp = mean_amplitude(diff, ROI, WIN_START, WIN_END)

    info = {
        "n_standard_events": n_std_raw,
        "n_deviant_events": n_dev_raw,
        "n_standard_epochs": n_std,
        "n_deviant_epochs": n_dev,
        "pct_epochs_rejected": round(
            100.0 * (1.0 - (n_std + n_dev) / float(n_std_raw + n_dev_raw)), 2),
        "interpolated_channels": interpolated,
        "reference": ref_used,
        "sfreq": float(sfreq),
    }
    return amp, info


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    per_subject = {}
    excluded = []
    exclusion_reasons = {}
    diagnostics = {}

    for sub in SUBJECTS:
        try:
            amp, info = process_subject(sub)
        except Exception as exc:
            excluded.append(sub)
            exclusion_reasons[sub] = f"{type(exc).__name__}: {exc}"
            print(f"[{sub}] EXCLUDED -- {type(exc).__name__}: {exc}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            continue
        per_subject[sub] = round(amp, 3)
        diagnostics[sub] = info
        print(f"[{sub}] MMN = {amp:+.3f} uV  "
              f"(std={info['n_standard_epochs']}, dev={info['n_deviant_epochs']}, "
              f"rejected={info['pct_epochs_rejected']}%)", flush=True)

    values = list(per_subject.values())
    grand_mean = round(float(np.mean(values)), 3) if values else None

    result = {
        "per_subject": per_subject,
        "excluded": excluded,
        "n_analyzed": len(per_subject),
        "grand_mean_uV": grand_mean,
        "choices": {
            "notes": (
                "ERP CORE auditory MMN (80 dB standards vs 70 dB deviants). Per subject: "
                "read the EEGLAB .set with mne.io.read_raw_eeglab; FP1/FP2 renamed Fp1/Fp2 and "
                "standard_1005 montage applied; HEOG_left/HEOG_right/VEOG_lower retyped as EOG so "
                "they are excluded from the scalp average and from the ERP. Zero-phase FIR "
                "band-pass 0.1-30 Hz on the continuous data. Flat/grossly noisy scalp channels "
                "(SD < 1e-8 V or SD > 5x the median channel SD, never the reference or ROI "
                "channels) were flagged and spherically interpolated. Re-referenced offline to the "
                "average of P9 and P10 -- the mastoid-equivalent reference conventional for "
                "auditory MMN, because the supratemporal MMN generator is a tangential dipole "
                "that reverses polarity at the mastoids, so this reference maximises the "
                "frontocentral negativity (it is also the ERP CORE reference for this paradigm). "
                "Events were taken from the BIDS events.tsv using the onset column converted to "
                "samples (round(onset * 1024)); value 80 = standard, 70 = deviant, and value 180 "
                "(the first stream of standards, which has no preceding standard context) was "
                "discarded. Epochs -200 to 800 ms, baseline-corrected to the -200 to 0 ms "
                "pre-stimulus interval; epochs exceeding 100 uV peak-to-peak on any scalp channel "
                "or 200 uV peak-to-peak on any EOG channel were rejected, as were epochs "
                "overlapping BAD annotations. All accepted standards were used (no exclusion of "
                "standards following a deviant). The MMN difference wave is deviant minus "
                "standard; the reported measure is its mean amplitude across Fz, FCz and Cz over "
                "100-250 ms, in microvolts (negative = larger MMN). A subject is excluded if "
                "fewer than 20 epochs survive in either condition or the recording cannot be "
                "read. grand_mean_uV is the unweighted mean of the per-subject values."
            ),
            "reference": "average of P9 and P10 (mastoid-equivalent)",
            "filter_hz": [L_FREQ, H_FREQ],
            "filter_details": "zero-phase FIR (firwin), applied to continuous data",
            "epoch_s": [TMIN, TMAX],
            "baseline_s": list(BASELINE),
            "event_codes": {"standard": 80, "deviant": 70, "dropped": 180},
            "artifact_rejection": {
                "eeg_peak_to_peak_uV": REJECT_P2P_EEG * 1e6,
                "eog_peak_to_peak_uV": REJECT_P2P_EOG * 1e6,
                "bad_channel_rule": "SD < 1e-8 V or SD > 5x median channel SD -> interpolate",
            },
            "roi": ROI,
            "measurement_window_ms": [WIN_START * 1000, WIN_END * 1000],
            "measure": "mean amplitude of the (deviant - standard) difference wave, uV",
            "min_epochs_per_condition": MIN_EPOCHS_PER_COND,
            "exclusion_reasons": exclusion_reasons,
            "per_subject_diagnostics": diagnostics,
        },
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w") as fh:
        json.dump(result, fh, indent=2)

    print(f"\nAnalyzed {len(per_subject)}/{len(SUBJECTS)} subjects; "
          f"grand mean MMN = {grand_mean} uV")
    print(f"Wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
