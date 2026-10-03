#!/usr/bin/env python3
"""
Auditory Mismatch Negativity (MMN) from the ERP CORE MMN dataset.

Per subject:
  1. Load the EEGLAB .set recording (30 scalp EEG + 3 EOG, 1024 Hz).
  2. Fix channel naming ('FP1'/'FP2' -> 'Fp1'/'Fp2'), mark the EOG channels as
     EOG, attach a standard_1005 montage.
  3. Band-pass 0.1-30 Hz (zero-phase FIR), then downsample to 256 Hz.
  4. Re-reference to the average of the 30 scalp electrodes.
  5. Ocular artifact correction with ICA (components correlated with the
     HEOG/VEOG channels are removed).  Falls back to no ICA if it fails.
  6. Epoch -200..+500 ms around standards (value 80) and deviants (value 70),
     baseline-correct on -200..0 ms, drop epochs exceeding 100 uV
     peak-to-peak on any scalp channel.
  7. MMN difference wave = deviant average - standard average.
  8. Mean amplitude of the difference wave over Fz, FCz, Cz in 100-250 ms.

Writes a JSON summary.  Run with no arguments.
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
    "b4a153ed-22fa-4b6a-ad04-d134656fecf4/scratchpad/gen_scale/L0_8"
)
OUT_JSON = os.path.join(OUT_DIR, "result.json")

SUBJECTS = ["sub-%03d" % i for i in range(1, 41)]

EOG_CHANNELS = ["HEOG_left", "HEOG_right", "VEOG_lower"]
RENAME = {"FP1": "Fp1", "FP2": "Fp2"}

STANDARD_VALUE = 80
DEVIANT_VALUE = 70

L_FREQ = 0.1          # Hz, high-pass
H_FREQ = 30.0         # Hz, low-pass
SFREQ_TARGET = 256.0  # Hz, after filtering

TMIN, TMAX = -0.2, 0.5
BASELINE = (-0.2, 0.0)

REJECT_P2P = 100e-6   # V, peak-to-peak on scalp EEG (after ICA cleaning)
FLAT_P2P = 0.1e-6     # V, flat-channel guard

ICA_N_COMPONENTS = 20
ICA_HP_FOR_FIT = 1.0  # Hz, high-pass used only for fitting the ICA

MEAS_WIN = (0.100, 0.250)  # s
ROI = ["Fz", "FCz", "Cz"]

MIN_TRIALS_PER_CONDITION = 20


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def read_events_tsv(path):
    """Return list of (onset_seconds, integer_value) from a BIDS events.tsv."""
    events = []
    with open(path, "r", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            onset_raw = row.get("onset", "")
            value_raw = row.get("value", "")
            if onset_raw is None or value_raw is None:
                continue
            onset_raw = str(onset_raw).strip()
            value_raw = str(value_raw).strip()
            if onset_raw in ("", "n/a") or value_raw in ("", "n/a"):
                continue
            try:
                onset = float(onset_raw)
                value = int(round(float(value_raw)))
            except ValueError:
                continue
            events.append((onset, value))
    return events


def resolve_roi(ch_names, wanted):
    """Case-insensitive lookup of the ROI channels; raises if any is missing."""
    lower = {name.lower(): name for name in ch_names}
    resolved = []
    for want in wanted:
        if want.lower() not in lower:
            raise RuntimeError("ROI channel %r not found in recording" % want)
        resolved.append(lower[want.lower()])
    return resolved


def prepare_raw(set_path):
    """Load and preprocess the continuous data (filter, resample, ref, ICA)."""
    raw = mne.io.read_raw_eeglab(set_path, preload=True)

    # Harmonise channel names with the standard 10-05 montage.
    rename = {old: new for old, new in RENAME.items() if old in raw.ch_names}
    if rename:
        raw.rename_channels(rename)

    # The three ocular channels are stored as EEG in the file.
    types = {ch: "eog" for ch in EOG_CHANNELS if ch in raw.ch_names}
    if types:
        raw.set_channel_types(types)

    try:
        montage = mne.channels.make_standard_montage("standard_1005")
        raw.set_montage(montage, on_missing="ignore", match_case=False)
    except Exception:
        pass  # electrode positions are not needed for this measurement

    # Band-pass at the native sampling rate, then downsample.
    raw.filter(
        l_freq=L_FREQ,
        h_freq=H_FREQ,
        picks=["eeg", "eog"],
        method="fir",
        fir_design="firwin",
        phase="zero",
    )
    if raw.info["sfreq"] > SFREQ_TARGET:
        raw.resample(SFREQ_TARGET)

    # Average reference over the scalp electrodes (EOG channels are excluded
    # automatically because of their channel type).
    raw.set_eeg_reference("average", projection=False)

    ica_info = clean_ocular(raw)
    return raw, ica_info


def clean_ocular(raw):
    """ICA-based removal of ocular components.  Returns a short description."""
    eog_present = [ch for ch in EOG_CHANNELS if ch in raw.ch_names]
    if not eog_present:
        return {"applied": False, "reason": "no EOG channels", "n_excluded": 0}

    n_eeg = len(mne.pick_types(raw.info, eeg=True, eog=False))
    n_comp = int(min(ICA_N_COMPONENTS, max(2, n_eeg - 1)))

    for method in ("infomax", "fastica"):
        try:
            fit_kwargs = {}
            if method == "infomax":
                fit_kwargs["fit_params"] = dict(extended=True)
            ica = mne.preprocessing.ICA(
                n_components=n_comp,
                method=method,
                max_iter="auto",
                random_state=97,
                **fit_kwargs,
            )
            raw_for_fit = raw.copy().filter(
                l_freq=ICA_HP_FOR_FIT,
                h_freq=None,
                picks=["eeg", "eog"],
                method="fir",
                fir_design="firwin",
                phase="zero",
            )
            ica.fit(raw_for_fit, picks="eeg")

            bad_idx = []
            for ch in eog_present:
                try:
                    idx, _ = ica.find_bads_eog(raw_for_fit, ch_name=ch)
                except Exception:
                    idx = []
                bad_idx.extend(idx)
            bad_idx = sorted(set(int(i) for i in bad_idx))

            ica.exclude = bad_idx
            if bad_idx:
                ica.apply(raw)
            del raw_for_fit
            return {
                "applied": True,
                "method": method,
                "n_components": n_comp,
                "n_excluded": len(bad_idx),
                "excluded": bad_idx,
            }
        except Exception as exc:  # try the next backend
            last_error = "%s: %s" % (type(exc).__name__, exc)
            continue

    return {"applied": False, "reason": last_error, "n_excluded": 0}


def build_epochs(raw, events_path):
    """Epoch standards and deviants from the BIDS events file."""
    tsv = read_events_tsv(events_path)
    sfreq = float(raw.info["sfreq"])
    n_times = raw.n_times

    rows = []
    for onset, value in tsv:
        if value not in (STANDARD_VALUE, DEVIANT_VALUE):
            continue  # e.g. 180 = first stimulus of a stream
        sample = int(round(onset * sfreq))
        if sample < 0 or sample >= n_times:
            continue
        rows.append([sample, 0, value])

    if not rows:
        raise RuntimeError("no standard/deviant events found")

    events = np.array(sorted(rows, key=lambda r: r[0]), dtype=int)
    # Guard against duplicate sample indices introduced by rounding.
    keep = np.concatenate(([True], np.diff(events[:, 0]) > 0))
    events = events[keep]

    event_id = {"standard": STANDARD_VALUE, "deviant": DEVIANT_VALUE}

    epochs = mne.Epochs(
        raw,
        events=events,
        event_id=event_id,
        tmin=TMIN,
        tmax=TMAX,
        baseline=BASELINE,
        picks=["eeg"],
        reject=dict(eeg=REJECT_P2P),
        flat=dict(eeg=FLAT_P2P),
        reject_by_annotation=True,
        preload=True,
        verbose=False,
    )
    return epochs


def mmn_amplitude(epochs):
    """Return (amplitude_uV, n_standard, n_deviant) for one subject."""
    n_std = len(epochs["standard"])
    n_dev = len(epochs["deviant"])
    if n_std < MIN_TRIALS_PER_CONDITION or n_dev < MIN_TRIALS_PER_CONDITION:
        raise RuntimeError(
            "too few clean trials (standard=%d, deviant=%d, minimum=%d)"
            % (n_std, n_dev, MIN_TRIALS_PER_CONDITION)
        )

    ev_std = epochs["standard"].average()
    ev_dev = epochs["deviant"].average()
    diff = mne.combine_evoked([ev_dev, ev_std], weights=[1, -1])

    roi = resolve_roi(diff.ch_names, ROI)
    picks = [diff.ch_names.index(ch) for ch in roi]

    times = diff.times
    mask = (times >= MEAS_WIN[0]) & (times <= MEAS_WIN[1])
    if not mask.any():
        raise RuntimeError("measurement window empty")

    # Volts -> microvolts; average over ROI channels and over the time window.
    amp_uV = float(diff.data[np.ix_(picks, np.where(mask)[0])].mean() * 1e6)
    return amp_uV, n_std, n_dev


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    per_subject = {}
    excluded = []
    reasons = {}
    trial_counts = {}
    ica_summary = {}

    for sub in SUBJECTS:
        eeg_dir = os.path.join(DATA_ROOT, sub, "eeg")
        set_path = os.path.join(eeg_dir, "%s_task-MMN_eeg.set" % sub)
        events_path = os.path.join(eeg_dir, "%s_task-MMN_events.tsv" % sub)

        print("[%s] processing" % sub, file=sys.stderr, flush=True)
        raw = None
        try:
            if not os.path.exists(set_path):
                raise RuntimeError("missing file %s" % set_path)
            if not os.path.exists(events_path):
                raise RuntimeError("missing file %s" % events_path)

            raw, ica_info = prepare_raw(set_path)
            ica_summary[sub] = ica_info

            epochs = build_epochs(raw, events_path)
            amp_uV, n_std, n_dev = mmn_amplitude(epochs)

            per_subject[sub] = round(amp_uV, 3)
            trial_counts[sub] = {"standard": n_std, "deviant": n_dev}
            print(
                "[%s] MMN = %.3f uV (std=%d, dev=%d)" % (sub, amp_uV, n_std, n_dev),
                file=sys.stderr,
                flush=True,
            )
            del epochs
        except Exception as exc:
            excluded.append(sub)
            reasons[sub] = "%s: %s" % (type(exc).__name__, exc)
            print(
                "[%s] EXCLUDED -- %s" % (sub, reasons[sub]),
                file=sys.stderr,
                flush=True,
            )
            traceback.print_exc(file=sys.stderr)
        finally:
            del raw

    values = list(per_subject.values())
    grand_mean = round(float(np.mean(values)), 3) if values else None

    notes = (
        "MNE-Python. Per subject: read EEGLAB .set; renamed FP1/FP2 -> Fp1/Fp2; "
        "HEOG_left/HEOG_right/VEOG_lower re-typed as EOG (excluded from the ERP); "
        "standard_1005 montage. Zero-phase FIR band-pass 0.1-30 Hz at the native "
        "1024 Hz, then resampled to 256 Hz. Average reference over the 30 scalp "
        "electrodes. Ocular artifacts corrected with extended-Infomax ICA "
        "(20 components) removing components correlated with the EOG channels; "
        "if ICA failed the subject was still analysed with threshold rejection "
        "only. Epochs -200 to +500 ms on events value=80 (standard) and value=70 "
        "(deviant); value=180 (first stimulus of a stream) discarded. Baseline "
        "-200 to 0 ms. Epochs with >100 uV peak-to-peak on any scalp channel "
        "(or a flat channel) dropped. All retained standards were used, i.e. no "
        "pre-deviant-only selection. MMN = deviant average minus standard "
        "average; reported value is the mean amplitude of that difference wave "
        "averaged over Fz, FCz, Cz and over 100-250 ms, in microvolts. Subjects "
        "with fewer than 20 clean trials in either condition, or with unreadable "
        "files, were excluded."
    )

    result = {
        "per_subject": per_subject,
        "excluded": excluded,
        "n_analyzed": len(per_subject),
        "grand_mean_uV": grand_mean,
        "choices": {
            "notes": notes,
            "software": "MNE-Python (%s)" % mne.__version__,
            "filter_hz": [L_FREQ, H_FREQ],
            "filter_design": "zero-phase FIR, firwin, applied at 1024 Hz",
            "resample_hz": SFREQ_TARGET,
            "reference": "average of the 30 scalp EEG electrodes",
            "eog_handling": (
                "HEOG_left/HEOG_right/VEOG_lower set to type EOG; extended-Infomax "
                "ICA with EOG-correlation component rejection"
            ),
            "epoch_s": [TMIN, TMAX],
            "baseline_s": list(BASELINE),
            "artifact_rejection": "peak-to-peak > 100 uV on any scalp EEG channel",
            "event_codes": {"standard": STANDARD_VALUE, "deviant": DEVIANT_VALUE},
            "contrast": "deviant minus standard",
            "roi": ROI,
            "measurement_window_s": list(MEAS_WIN),
            "measure": "mean amplitude (uV)",
            "min_trials_per_condition": MIN_TRIALS_PER_CONDITION,
            "exclusion_reasons": reasons,
            "trial_counts": trial_counts,
            "ica": ica_summary,
        },
    }

    with open(OUT_JSON, "w") as fh:
        json.dump(result, fh, indent=2)

    print(
        "\nWrote %s | n_analyzed=%d | grand mean = %s uV"
        % (OUT_JSON, len(per_subject), grand_mean),
        file=sys.stderr,
        flush=True,
    )


if __name__ == "__main__":
    main()
