"""Post-release audit of original AEA versus retained MNE-BIDS trial identities.

Runs the original subject functions, never their group/figure-writing entrypoints.
Reference FIF files are read only. Identity is the original source TSV data-row index,
validated against onset, original code, relabeled BIDS events and raw annotations.
No selection index is interpreted as a TSV row without that independent mapping.

Example (aeais environment):
    python tools/validation/validate_trial_identity.py --jobs 2 --out projects/trial-identity/new-results.json --ids-out projects/trial-identity/new-event-ids.json
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools/benchmark"))
COMPONENTS = {
    "MMN": ("validate_mmn_group", "subject_mmn", "mmn_group_results.json", "mmn_uV", "deviant", "standard", 40),
    "P3": ("validate_p3_group", "subject_p3", "p3_group_results.json", "p3_uV", "target", "standard", 20),
    "N170": ("validate_n170_erpcore_group", "subject_n170", "n170_erpcore_results.json", "n170_uV", "face", "car", 20),
    "ERN": ("validate_ern_erpcore_group", "subject_ern", "ern_erpcore_results.json", "ern_uV", "error", "correct", 20),
    "N400": ("validate_n400_erpcore_group", "subject_n400", "n400_erpcore_results.json", "n400_uV", "unrelated", "related", 20),
}
TRIAL_COLUMNS = ["source_row_0based", "source_onset_s", "source_sample", "source_code", "condition",
                 "aea_input_index", "aea_sample_256Hz", "aea_retained", "aea_drop_reasons",
                 "reference_input_index", "reference_sample_256Hz", "reference_retained", "reference_drop_reasons"]


def condition_for(component, code):
    """Original runners' condition definitions, checked against their actual event codes."""
    if component == "MMN":
        return {70: "deviant", 80: "standard"}.get(code)
    if component == "P3" and 11 <= code <= 55:
        return "target" if code // 10 == code % 10 else "standard"
    if component == "N170" and 1 <= code <= 80:
        return "face" if code <= 40 else "car"
    if component == "ERN" and 111 <= code <= 222:
        return "correct" if code // 100 == code % 10 else "error"
    if component == "N400":
        return {211: "related", 212: "related", 221: "unrelated", 222: "unrelated"}.get(code)
    return None


def unique_match(candidates, description):
    if len(candidates) != 1:
        raise ValueError(f"{description}: expected one source event, found {len(candidates)}")
    return int(candidates[0])


def validate_selection(events, selection, drop_log, input_events):
    """Selection indexes the Epochs input-event sequence, with empty log for retained rows."""
    selection = np.asarray(selection, int)
    if len(drop_log) != len(input_events):
        raise ValueError("drop_log length differs from mapped input-event sequence")
    if len(set(selection.tolist())) != len(selection):
        raise ValueError("duplicate selection index")
    if not np.array_equal(events, input_events[selection]):
        raise ValueError("retained events do not equal input_events[selection]")
    empty = np.array([i for i, reasons in enumerate(drop_log) if not reasons], int)
    if not np.array_equal(selection, empty):
        raise ValueError("selection and empty drop_log entries disagree")


def membership_summary(aea_rows, reference_rows):
    aea, reference = set(aea_rows), set(reference_rows)
    if len(aea) != len(aea_rows) or len(reference) != len(reference_rows):
        raise ValueError("duplicate retained source identity")
    return {"aea_retained": len(aea), "reference_retained": len(reference),
            "intersection": len(aea & reference), "union": len(aea | reference),
            "aea_only_source_rows": sorted(aea - reference),
            "reference_only_source_rows": sorted(reference - aea),
            "exact_membership": aea == reference}


def reference_mapping(component, subject, source, bids, deriv):
    """Map retained raw annotations -> events -> pre/clean FIF, independently of selection."""
    import mne
    import pandas as pd
    for col in ("onset", "sample", "value"):
        pd.testing.assert_series_equal(source[col], bids[col], check_names=False)
    raw_path = deriv / f"{subject}_task-{component}_proc-filt_raw.fif"
    pre_path = deriv / f"{subject}_task-{component}_epo.fif"
    clean_path = deriv / f"{subject}_task-{component}_proc-clean_epo.fif"
    raw = mne.io.read_raw_fif(raw_path, preload=False, verbose="ERROR")
    pre = mne.read_epochs(pre_path, preload=False, verbose="ERROR")
    clean = mne.read_epochs(clean_path, preload=False, verbose="ERROR")
    if raw.first_samp != 0 or raw.info["sfreq"] != 256:
        raise ValueError("retained reference time base differs from original benchmark")
    # MNE-BIDS disambiguates a trial_type only when it contains multiple values.
    # In MMN sub-003/sub-016 this applies to STATUS/1 and STATUS/4, not the tones.
    distinct_codes = bids.groupby("trial_type")["value"].nunique()
    expected_names = np.array([f"{name}/{int(code)}" if distinct_codes[name] > 1 else str(name)
                               for name, code in zip(bids.trial_type, bids.value)])
    # One native sample bounds the match; unique source event and descriptor are mandatory.
    # Saved annotation floating-point precision can slightly alter the TSV onset.
    annotation_rows, onset_errors = [], []
    for annotation in raw.annotations:
        candidates = np.flatnonzero((expected_names == annotation["description"]) &
                                   (abs(source.onset.to_numpy() - annotation["onset"]) <= 1 / 1024))
        row = unique_match(candidates, "reference raw annotation")
        annotation_rows.append(row)
        onset_errors.append(float(annotation["onset"] - source.iloc[row].onset))
    if len(set(annotation_rows)) != len(source) or len(annotation_rows) != len(source):
        raise ValueError("retained raw annotations do not map bijectively to all TSV events")
    all_events, event_id = mne.events_from_annotations(raw, verbose="ERROR")
    annotation_events = np.array([
        [int(np.round(a["onset"] * 256)), 0, event_id[a["description"]]]
        for a in raw.annotations], dtype=int)
    if not np.array_equal(all_events, annotation_events):
        raise ValueError("annotation conversion differs from retained reference event stream")
    inverse = {v: k for k, v in event_id.items()}
    selected_annotations = [i for i, row in enumerate(annotation_rows)
                            if condition_for(component, int(source.iloc[row].value))]
    input_events = all_events[selected_annotations]
    input_rows = [annotation_rows[i] for i in selected_annotations]
    validate_selection(pre.events, pre.selection, pre.drop_log, input_events)
    pre_rows = []
    for event, name in zip(pre.events, pre.metadata.event_name):
        candidates = np.flatnonzero(np.all(all_events == event, axis=1))
        ix = unique_match(candidates, "reference pre-epoch event")
        row = annotation_rows[ix]
        if inverse[event[2]] != name or expected_names[row] != name:
            raise ValueError("pre-epoch event code/metadata/source label mismatch")
        if condition_for(component, int(source.iloc[row].value)) != name.split("/")[0]:
            raise ValueError("reference condition differs from original-code condition")
        pre_rows.append(row)
    if pre_rows != [input_rows[i] for i in pre.selection]:
        raise ValueError("independent pre-FIF identity mapping disagrees with selection")
    eligible = {i for i, value in enumerate(source.value) if condition_for(component, int(value))}
    if set(input_rows) != eligible or len(input_rows) != len(eligible):
        raise ValueError("reference epoch input does not cover all original eligible source events")
    validate_selection(clean.events, clean.selection, clean.drop_log, input_events)
    pre_index = {int(selection): i for i, selection in enumerate(pre.selection)}
    for j, name in enumerate(clean.metadata.event_name):
        if name != pre.metadata.iloc[pre_index[int(clean.selection[j])]].event_name:
            raise ValueError("clean and pre metadata event identities disagree")
    return pre, clean, input_rows, {
        "source_bids_onset_sample_code_exact": True,
        "raw_annotation_source_bijection": True,
        "pre_events_match_retained_raw_annotations": True,
        "full_input_recovered_from_retained_raw_annotations": True,
        "pre_selection_drop_log_consistent": True,
        "pre_epoch_drops": [{"input_index": i, "source_row_0based": input_rows[i], "reasons": list(reasons)}
                            for i, reasons in enumerate(pre.drop_log) if reasons],
        "clean_selection_drop_log_consistent": True,
        "source_events": len(source), "eligible_source_events": len(input_rows),
        "max_abs_annotation_onset_minus_tsv_s": max(abs(x) for x in onset_errors),
        "reference_paths": [str(p.resolve()) for p in (raw_path, pre_path, clean_path)],
    }, input_events


def run_subject(component, subject):
    import mne
    import pandas as pd
    mne.set_log_level("ERROR")
    started = time.monotonic()
    module_name, function_name, certified_name, metric, positive, negative, _ = COMPONENTS[component]
    runner = importlib.import_module(module_name)
    original = json.loads((HERE / certified_name).read_text(encoding="utf-8-sig"))
    certified = {x["subject"]: x for x in original["per_subject"]}.get(subject)
    historical_ref = json.loads((ROOT / "tools/benchmark" / f"bidspipe_{component.lower()}_results.json").read_text(encoding="utf-8-sig"))
    certified_ref = {x["subject"]: x for x in historical_ref["per_subject"]}.get(subject)
    source_path = runner.DATA / subject / "eeg" / f"{subject}_task-{component}_events.tsv"
    base = runner.DATA.parent
    bids_path = base / f"erpcore_{component.lower()}_bench_bids" / subject / "eeg" / source_path.name
    deriv = base / f"erpcore_{component.lower()}_bench_deriv" / subject / "eeg"
    source = pd.read_csv(source_path, sep="\t")
    bids = pd.read_csv(bids_path, sep="\t")
    pre, reference, ref_rows, checks, ref_events = reference_mapping(component, subject, source, bids, deriv)
    captured = {}
    epoch_constructor = mne.Epochs

    def capture_epochs(raw, events, *args, **kwargs):
        epochs = epoch_constructor(raw, events, *args, **kwargs)
        captured.update(raw=raw, events=events.copy(), epochs=epochs,
                        settings={k: kwargs[k] for k in ("event_id", "tmin", "tmax", "baseline", "reject")})
        return epochs

    exclusion = None
    with patch.object(mne, "Epochs", capture_epochs):
        try:
            _, amplitude, _, _ = getattr(runner, function_name)(subject)
        except RuntimeError as exc:
            if not str(exc).startswith("too few epochs"):
                raise
            exclusion = str(exc)
            amplitude = None
    epochs, events, raw = captured["epochs"], captured["events"], captured["raw"]
    validate_selection(epochs.events, epochs.selection, epochs.drop_log, events)
    inverse = {v: k for k, v in epochs.event_id.items()}
    source_conditions = np.array([condition_for(component, int(code)) for code in source.value])
    source_samples = np.round(source.onset.to_numpy() * raw.info["sfreq"]).astype(int)
    aea_rows = []
    for event in events:
        candidates = np.flatnonzero((source_samples == event[0]) & (source_conditions == inverse[event[2]]))
        aea_rows.append(unique_match(candidates, "AEA runner input event"))
    if len(set(aea_rows)) != len(aea_rows) or set(aea_rows) != set(ref_rows):
        raise ValueError("AEA and reference candidate event universes differ")
    if raw.info["sfreq"] != 256 or raw.first_samp != 0:
        raise ValueError("AEA time base differs from original benchmark")
    checks["aea_input_source_bijection"] = True
    checks["aea_selection_drop_log_consistent"] = True
    checks["candidate_event_universe_exact"] = True
    ai, ri = {row: i for i, row in enumerate(aea_rows)}, {row: i for i, row in enumerate(ref_rows)}
    akeep, rkeep = set(epochs.selection.tolist()), set(reference.selection.tolist())
    trial_rows = []
    for row in sorted(ai):
        a, r = ai[row], ri[row]
        src = source.iloc[row]
        trial_rows.append([int(row), float(src.onset), int(src["sample"]), int(src.value), str(source_conditions[row]),
                           a, int(events[a, 0]), a in akeep, list(epochs.drop_log[a]),
                           r, int(ref_events[r, 0]), r in rkeep, list(reference.drop_log[r])])
    memberships = {}
    for condition in (positive, negative):
        memberships[condition] = membership_summary(
            [row for row in aea_rows if ai[row] in akeep and source_conditions[row] == condition],
            [row for row in ref_rows if ri[row] in rkeep and source_conditions[row] == condition])
    mismatch_rows = sorted({row for value in memberships.values()
                            for key in ("aea_only_source_rows", "reference_only_source_rows") for row in value[key]})
    discrepancies = []
    annotation_raw = mne.io.read_raw_fif(checks["reference_paths"][0], preload=False, verbose="ERROR") if mismatch_rows else None
    for row in mismatch_rows:
        a, r = ai[row], ri[row]
        info = dict(zip(TRIAL_COLUMNS, next(x for x in trial_rows if x[0] == row)))
        info["source_tsv_line_1based_including_header"] = row + 2
        annotation_index = unique_match(np.flatnonzero(abs(annotation_raw.annotations.onset - source.iloc[row].onset) <= 1 / 1024),
                                        "discrepant reference annotation")
        annotation_onset = float(annotation_raw.annotations.onset[annotation_index])
        info["reference_retained_annotation_onset_s"] = annotation_onset
        info["source_onset_times_sfreq"] = float(source.iloc[row].onset * 256)
        info["reference_annotation_onset_times_sfreq"] = annotation_onset * 256
        # Inspect the actual window used by the original Epochs object before rejection.
        start = int(events[a, 0] + np.round(epochs.tmin * 256))
        data = raw.get_data(start=start, stop=start + len(epochs.times))
        channels = list(epochs.drop_log[a]) + list(reference.drop_log[r])
        info["peak_to_peak_uV"] = {}
        pre_match = np.flatnonzero(pre.selection == r)
        ref_data = pre[pre_match].get_data(copy=True)[0] if len(pre_match) else None
        for channel in sorted(set(channels) & set(raw.ch_names) & set(pre.ch_names)):
            info["peak_to_peak_uV"][channel] = {
                "aea_original_window": float(np.ptp(data[raw.ch_names.index(channel)]) * 1e6),
                "reference_saved_pre_epoch": None if ref_data is None else float(np.ptp(ref_data[pre.ch_names.index(channel)]) * 1e6)}
        discrepancies.append(info)
    counts = {k: int(len(epochs[k])) for k in (positive, negative)}
    ref_counts = {k: int(len(reference[k])) for k in (positive, negative)}
    # Confirm retained reference epochs are those behind historical evoked counts/amplitudes.
    extractor = importlib.import_module(f"extract_bidspipe_{component.lower()}")
    ref_amplitude, ref_npos, ref_nneg, _ = getattr(extractor, f"subject_{component.lower()}")(deriv / f"{subject}_task-{component}_ave.fif")
    if ref_counts != {positive: int(ref_npos), negative: int(ref_nneg)}:
        raise ValueError("clean epoch membership counts differ from retained evoked nave")
    clean_diff = mne.combine_evoked([reference[positive].average(), reference[negative].average()], weights=[1, -1])
    roi = [clean_diff.ch_names.index(c) for c in extractor.ROI]
    window = getattr(extractor, f"{component}_WIN")
    mask = (clean_diff.times >= window[0]) & (clean_diff.times <= window[1])
    clean_amplitude = float(clean_diff.data[roi][:, mask].mean() * 1e6)
    historical_a_counts = None if certified is None else {positive: certified["n_dev"], negative: certified["n_std"]}
    historical_r_counts = None if certified_ref is None else {positive: certified_ref["n_dev"], negative: certified_ref["n_std"]}
    shifts = Counter(int(events[ai[row], 0] - ref_events[ri[row], 0]) for row in ai)
    retained_shifts = Counter(int(events[ai[row], 0] - ref_events[ri[row], 0]) for row in ai
                              if ai[row] in akeep and ri[row] in rkeep)
    result = {"component": component, "subject": subject, "status": "complete",
              "worker_pid": os.getpid(), "runtime_s": round(time.monotonic() - started, 3),
              "source_events_tsv": str(source_path.resolve()), "bids_events_tsv": str(bids_path.resolve()),
              "aea_evidence": "current regeneration of original subject function; historical AEA trial IDs were not saved",
              "reference_evidence": "retained original reference raw/pre-epoch/clean-epoch/evoked FIFs",
              "aea_original_runner": f"tools/validation/{module_name}.py:{function_name}",
              "epoch_settings": captured["settings"], "checks": checks,
              "historical_aea_included": certified is not None,
              "historical_reference_included": certified_ref is not None,
              "current_aea_exclusion": exclusion,
              "aea_counts": counts, "reference_counts": ref_counts,
              "historical_aea_counts": historical_a_counts, "historical_reference_counts": historical_r_counts,
              "aea_counts_match_historical": None if certified is None else counts == historical_a_counts,
              "reference_counts_match_historical": None if certified_ref is None else ref_counts == historical_r_counts,
              "aea_amplitude_uV": amplitude,
              "historical_aea_amplitude_uV": None if certified is None else certified[metric],
              "aea_amplitude_matches_historical_3dp": None if certified is None else round(amplitude, 3) == certified[metric],
              "reference_evoked_amplitude_uV": float(ref_amplitude),
              "reference_clean_epoch_average_amplitude_uV": clean_amplitude,
              "reference_clean_minus_saved_evoked_amplitude_uV": clean_amplitude - float(ref_amplitude),
              "reference_amplitude_matches_historical_3dp": None if certified_ref is None else round(ref_amplitude, 3) == certified_ref[metric],
              "condition_membership": memberships,
              "all_conditions_exact_membership": all(x["exact_membership"] for x in memberships.values()),
              "sample_difference_aea_minus_reference": {str(k): v for k, v in sorted(shifts.items())},
              "shared_retained_sample_difference_aea_minus_reference": {str(k): v for k, v in sorted(retained_shifts.items())},
              "discrepancies": discrepancies}
    return result, {"component": component, "subject": subject, "trials": trial_rows}


def audit_subject(component, subject):
    try:
        return run_subject(component, subject)
    except Exception as exc:
        # Preserve failed records explicitly; no fallback or reduced-spec replacement.
        import traceback
        return {"component": component, "subject": subject, "status": "error", "worker_pid": os.getpid(),
                "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()}, None


def aggregate(records):
    summary = {}
    for component in COMPONENTS:
        rows = [r for r in records if r["component"] == component]
        if not rows:
            continue
        good = [r for r in rows if r["status"] == "complete"]
        certified = [r for r in good if r["historical_aea_included"] and r["historical_reference_included"]]
        shifts = Counter()
        certified_shifts = Counter()
        shared_retained_shifts = Counter()
        for row in good:
            shifts.update(row["sample_difference_aea_minus_reference"])
        for row in certified:
            certified_shifts.update(row["sample_difference_aea_minus_reference"])
            shared_retained_shifts.update(row["shared_retained_sample_difference_aea_minus_reference"])
        summary[component] = {
            "attempted": len(rows), "completed": len(good), "errors": len(rows) - len(good),
            "certified_common_subjects": len(certified),
            "exact_membership_subjects_all_available": sum(r["all_conditions_exact_membership"] for r in good),
            "exact_membership_subjects_certified_common": sum(r["all_conditions_exact_membership"] for r in certified),
            "mismatch_subjects": [r["subject"] for r in good if not r["all_conditions_exact_membership"]],
            "historically_excluded_aea_subjects": [r["subject"] for r in good if not r["historical_aea_included"]],
            "aea_historical_count_mismatches": [r["subject"] for r in good if r["aea_counts_match_historical"] is False],
            "aea_historical_amplitude_mismatches": [r["subject"] for r in good if r["aea_amplitude_matches_historical_3dp"] is False],
            "reference_historical_count_mismatches": [r["subject"] for r in good if r["reference_counts_match_historical"] is False],
            "reference_historical_amplitude_mismatches": [r["subject"] for r in good if r["reference_amplitude_matches_historical_3dp"] is False],
            "sample_difference_aea_minus_reference_all_candidates": dict(sorted(shifts.items())),
            "sample_difference_aea_minus_reference_certified_candidates": dict(sorted(certified_shifts.items())),
            "sample_difference_aea_minus_reference_certified_shared_retained": dict(sorted(shared_retained_shifts.items())),
            "certified_retained_totals": {key: sum(m[key] for r in certified for m in r["condition_membership"].values())
                                          for key in ("aea_retained", "reference_retained", "intersection", "union")},
            "discrepant_trial_identities": sum(len(r["discrepancies"]) for r in good),
        }
    return summary


def select_subjects(data, component, requested=None):
    expected = COMPONENTS[component][-1]
    subjects = sorted(p.name for p in data.glob("sub-*") if p.is_dir())[:expected]
    if len(subjects) != expected:
        raise ValueError(f"{component}: expected {expected} source subjects; found {len(subjects)}")
    unknown = set(requested or []) - set(subjects)
    if unknown:
        raise ValueError(f"{component}: unknown requested subjects {sorted(unknown)}")
    return [s for s in subjects if not requested or s in requested]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--components", nargs="+", choices=COMPONENTS, default=list(COMPONENTS))
    parser.add_argument("--subjects", nargs="+", help="Optional subject IDs for a diagnostic subset")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--out", type=Path, default=ROOT / "projects/trial-identity/trial_identity_results.json")
    parser.add_argument("--ids-out", type=Path, default=ROOT / "projects/trial-identity/trial_identity_event_ids.json")
    args = parser.parse_args()
    reserved = {HERE / "trial_identity_results.json", HERE / "trial_identity_event_ids.json"}
    if args.out.resolve() in reserved or args.ids_out.resolve() in reserved:
        parser.error("Retained supplemental artifacts are read-only; choose new paths under projects/trial-identity/")
    if args.out.resolve() == args.ids_out.resolve():
        parser.error("Summary and trial identities need distinct output files")
    import mne, pandas, scipy
    tasks = []
    for component in args.components:
        runner = importlib.import_module(COMPONENTS[component][0])
        try:
            subjects = select_subjects(runner.DATA, component, args.subjects)
        except ValueError as exc:
            parser.error(str(exc))
        tasks.extend((component, s) for s in subjects)
    # Begin with the known discrepancy while retaining every scheduled record.
    tasks.sort(key=lambda x: (x != ("MMN", "sub-030"), list(COMPONENTS).index(x[0]), x[1]))
    result = {"audit": "post-release original AEA/reference trial-identity supplement", "schema_version": 1,
              "started_utc": datetime.now(timezone.utc).isoformat(), "parent_pid": os.getpid(),
              "command": sys.argv, "python_executable": sys.executable,
              "versions": {"mne": mne.__version__, "numpy": np.__version__, "pandas": pandas.__version__, "scipy": scipy.__version__},
              "planned_records": len(tasks), "completed": False,
              "identity_definition": "Original TSV data-row index (0-based), with onset, source sample and original event code; line number including header is row+2",
              "trial_id_companion": str(args.ids_out), "per_subject": []}
    ids = {"columns": TRIAL_COLUMNS, "per_subject": []}
    print(f"START pid={os.getpid()} tasks={len(tasks)} workers={args.jobs}", flush=True)
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(audit_subject, *task): task for task in tasks}
        for future in as_completed(futures):
            record, trial_ids = future.result()
            result["per_subject"].append(record)
            if trial_ids is not None:
                ids["per_subject"].append(trial_ids)
            print(json.dumps({k: record.get(k) for k in ("component", "subject", "status", "worker_pid", "runtime_s", "all_conditions_exact_membership", "error")}), flush=True)
            result["summary"] = aggregate(result["per_subject"])
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    result["completed"] = all(r["status"] == "complete" for r in result["per_subject"]) and len(result["per_subject"]) == len(tasks)
    result["finished_utc"] = datetime.now(timezone.utc).isoformat()
    result["per_subject"].sort(key=lambda x: (list(COMPONENTS).index(x["component"]), x["subject"]))
    ids["per_subject"].sort(key=lambda x: (list(COMPONENTS).index(x["component"]), x["subject"]))
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    args.ids_out.parent.mkdir(parents=True, exist_ok=True)
    # Compact arrays retain all identities/drop reasons without repeating 13 key names per trial.
    args.ids_out.write_text(json.dumps(ids, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2), flush=True)
    print(f"FINISH pid={os.getpid()} complete={result['completed']}", flush=True)
    return 0 if result["completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
