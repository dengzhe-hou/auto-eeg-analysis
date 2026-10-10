"""Run the complete v0.3.2 N400 recipe on 20 locally cached ERP CORE participants.

Uses the recipe's explicitly documented no-ICA / reject=None benchmark branch.
The recipe's declared CPz/Cz/Pz inference domain is used, not the historical
validation runner's all-channel domain. Raw datasets are never downloaded.

Run: python tools/examples/run_recipe_case.py --run-dir projects/n400-recipe-case/runs/run-001
Replay retained inference: append --replay with the same --run-dir.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RECIPE = "recipes/n400-semantic/RECIPE.md"
SUBJECTS = [f"sub-{i:03d}" for i in range(1, 21)]
ROI = ["CPz", "Cz", "Pz"]
WINDOW = (0.3, 0.5)
RELATED, UNRELATED = 1, 2


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def display_path(path: Path) -> str:
    path = path.resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def prepare_run_directory(run_dir: Path) -> None:
    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError(f"Full analysis requires a fresh empty run directory: {run_dir}. "
                              "Use --replay for an existing completed run.")
    run_dir.mkdir(parents=True, exist_ok=True)


def find_subject_inputs(data_root: Path, sub: str) -> tuple[Path, Path]:
    """Read the official OSF session layout or an existing sessionless cache."""
    locations = (
        (data_root / sub / "ses-N400" / "eeg", f"{sub}_ses-N400_task-N400"),
        (data_root / sub / "eeg", f"{sub}_task-N400"),
    )
    for directory, prefix in locations:
        input_set = directory / f"{prefix}_eeg.set"
        if input_set.is_file():
            input_events = directory / f"{prefix}_events.tsv"
            if not input_events.is_file():
                raise FileNotFoundError(input_events)
            return input_set, input_events
    expected = [str(directory / f"{prefix}_eeg.set") for directory, prefix in locations]
    raise FileNotFoundError(f"No N400 EEG input for {sub}; expected one of: {expected}")


def target_events(frame, sfreq: float) -> np.ndarray:
    """Map the actual ERP CORE target codes; prime codes do not enter epochs."""
    selected = frame[frame["value"].isin([211, 212, 221, 222])]
    samples = np.round(selected["onset"].to_numpy() * sfreq).astype(int)
    codes = np.where(selected["value"].isin([211, 212]), RELATED, UNRELATED)
    return np.column_stack([samples, np.zeros(len(samples), dtype=int), codes])[
        np.argsort(samples)
    ]


def roi_adjacency(info):
    import mne

    full, names = mne.channels.find_ch_adjacency(info, ch_type="eeg")
    idx = [names.index(name) for name in ROI]
    return full.tocsr()[idx][:, idx]


def validate_channels(ch_names):
    missing = [name for name in ROI if name not in ch_names]
    if len(ch_names) < 16 or missing:
        raise ValueError(f"Recipe requires >=16 EEG channels including {ROI}; missing={missing}")


def validate_trial_counts(counts):
    if set(counts) != {"related", "unrelated"} or min(counts.values()) < 30:
        raise ValueError(f"Recipe requires >=30 retained trials in each condition: {counts}")


def compute_statistics(related, unrelated, times, ch_names, adjacency):
    import mne
    from scipy import stats

    idx = [list(ch_names).index(name) for name in ROI]
    mask = (times >= WINDOW[0]) & (times <= WINDOW[1])
    differences = unrelated - related
    roi_differences = differences[:, idx][:, :, mask]
    x = roi_differences.transpose(0, 2, 1)
    threshold = -stats.t.ppf(0.95, len(x) - 1)
    t_obs, clusters, p_values, h0 = mne.stats.spatio_temporal_cluster_1samp_test(
        x, threshold=threshold, tail=-1, n_permutations=5000, seed=42,
        adjacency=adjacency, out_type="mask", n_jobs=1, verbose=False,
    )
    cluster_masks = np.asarray(clusters, dtype=bool).reshape((-1, *t_obs.shape))
    subject_uv = roi_differences.mean(axis=(1, 2)) * 1e6
    summaries = []
    for cluster, p in zip(cluster_masks, p_values):
        ts, cs = np.where(cluster)
        summaries.append({
            "p": float(p), "n_samples": int(cluster.sum()),
            "time_bounds_s": [float(times[mask][ts.min()]), float(times[mask][ts.max()])],
            "channels": [ROI[i] for i in np.unique(cs)],
        })
    return {
        "n_subjects": len(subject_uv), "roi": ROI, "window_s": list(WINDOW),
        "contrast": "unrelated - related", "statistical_unit": "participant",
        "n_permutations": 5000, "seed": 42, "tail": -1,
        "cluster_forming_p": 0.05, "threshold_t": float(threshold),
        "df": len(subject_uv) - 1, "cluster_alpha": 0.05,
        "grand_mean_uV": float(subject_uv.mean()),
        "sem_uV": float(stats.sem(subject_uv)),
        "clusters": summaries,
        "n_significant_clusters": int((p_values < 0.05).sum()),
        "min_cluster_p": float(p_values.min()) if len(p_values) else None,
        "hypothesis_supported": bool(subject_uv.mean() < 0 and (p_values < 0.05).any()),
    }, {"t_obs": t_obs, "cluster_masks": cluster_masks, "p_values": p_values,
        "h0": h0, "subject_uV": subject_uv}


def create_plan(run_dir: Path, data_root: Path) -> dict:
    recipe_text = subprocess.check_output(
        ["git", "show", f"v0.3.2:{RECIPE}"], cwd=ROOT, text=True,
    )
    (run_dir / "template-stage").mkdir(parents=True, exist_ok=True)
    (run_dir / "template-stage" / "RECIPE.md").write_text(recipe_text, encoding="utf-8")
    (run_dir / "template-stage" / "run_recipe_case.py").write_text(
        Path(__file__).read_text(encoding="utf-8-sig"), encoding="utf-8")
    spec = {
        "release": "v0.3.2", "recipe": "n400-semantic", "recipe_version": "v0.1.0",
        "subjects": SUBJECTS, "data_root": str(data_root),
        "target_codes": {"related": [211, 212], "unrelated": [221, 222]},
        "exclude_channels": ["HEOG_left", "HEOG_right", "VEOG_lower"],
        "montage": "standard_1020", "filter_hz": [0.1, 30.0],
        "filter_method": "fir", "filter_phase": "zero", "filter_design": "firwin",
        "resample_hz": 256, "reference": "average",
        "ica": "omitted: explicit recipe benchmark branch", "reject": None,
        "reject_by_annotation": True, "min_trials_per_condition": 30,
        "epoch_s": [-0.2, 0.8], "baseline_s": [-0.2, 0.0],
        "roi": ROI, "window_s": list(WINDOW), "tail": -1,
        "n_permutations": 5000, "seed": 42,
        "adjacency": "full 30-channel montage triangulation subset to CPz,Cz,Pz",
        "peak_map": "descriptive, at most negative grand-average ROI sample within 300-500 ms",
    }
    write_json(run_dir / "plan.json", spec)
    (run_dir / "DATASET_BRIEF.md").write_text(
        "# ERP CORE N400 recipe case\n\n"
        "Twenty cached ERP CORE participants, sub-001 through sub-020; all included a priori. "
        "The source study has 40 participants; this worked example uses the fixed cached 20, "
        "matching the released recipe's validation cohort, and is not a new benchmark cohort.\n\n"
        f"Source root: `{data_root}`. Each input has 30 scalp EEG and three EOG channels at "
        "1024 Hz, with 60 related and 60 unrelated target events. Prime events are excluded. "
        "Dataset paper: Kappenman et al. (2021), NeuroImage 225, 117465, "
        "https://doi.org/10.1016/j.neuroimage.2020.117465. No data download or migration.\n",
        encoding="utf-8",
    )
    (run_dir / "ANALYSIS_PLAN.md").write_text(
        "# Frozen analysis plan\n\n"
        "Use released v0.3.2 `n400-semantic` v0.1.0 with all 20 cached participants. "
        "Drop the three EOG channels before average referencing; 0.1–30 Hz zero-phase FIR, "
        "resample to 256 Hz, standard_1020 montage. Use the recipe's explicitly documented "
        "no-ICA, reject=None benchmark branch; retain annotation rejection. The benchmark "
        "branch does not remove ocular components or apply amplitude-based rejection.\n\n"
        "Target-word epochs: −0.2 to 0.8 s, baseline −0.2 to 0 s; retain at least 30 "
        "trials per condition for every participant. Any failed participant stops completion; "
        "do not silently exclude participants. C1: unrelated minus related in CPz/Cz/Pz, "
        "300–500 ms, one-sample second-level spatiotemporal cluster test, negative tail, "
        "5000 permutations, seed 42, negative cluster-forming t at one-sided p<0.05 and df=19. "
        "Build adjacency on all 30 scalp channels, then subset to the three-channel ROI. "
        "This differs from the historical all-channel validation test and has its own result.\n\n"
        "F1 includes related/unrelated/difference grand averages at the declared ROI, a "
        "descriptive N400 peak topomap, and all participant ROI amplitudes. Shading is "
        "across-participant SEM. Peak selection is descriptive and does not change the "
        "predeclared inferential domain. Replay the fixed statistical computation from "
        "retained participant averages and require identical statistics, cluster masks, "
        "p values, and permutation null distribution. No performance comparison.\n",
        encoding="utf-8",
    )
    return spec


def run_subject(sub: str, data_root: Path, run_dir: Path):
    import mne
    import pandas as pd

    input_set, input_events = find_subject_inputs(data_root, sub)
    raw = mne.io.read_raw_eeglab(input_set, preload=True, verbose="ERROR")
    source_sfreq = raw.info["sfreq"]
    raw.drop_channels(["HEOG_left", "HEOG_right", "VEOG_lower"])
    raw.pick("eeg")
    validate_channels(raw.ch_names)
    assert len(raw.ch_names) == 30
    raw.set_montage("standard_1020", match_case=False, on_missing="raise", verbose="ERROR")
    raw.filter(0.1, 30.0, method="fir", phase="zero", fir_design="firwin",
               n_jobs=1, verbose="ERROR")
    raw.resample(256.0, verbose="ERROR")
    raw.set_eeg_reference("average", projection=False, verbose="ERROR")
    frame = pd.read_csv(input_events, sep="\t")
    events = target_events(frame, raw.info["sfreq"])
    assert len(events) == 120, f"{sub}: expected 120 source target events"
    pre_path = run_dir / "preprocess-stage" / sub
    pre_path.mkdir(parents=True, exist_ok=True)
    raw.save(pre_path / "preprocessed_raw.fif", overwrite=True, verbose="ERROR")
    epochs = mne.Epochs(
        raw, events, event_id={"related": RELATED, "unrelated": UNRELATED},
        tmin=-0.2, tmax=0.8, baseline=(-0.2, 0.0), preload=True,
        reject=None, reject_by_annotation=True, verbose="ERROR",
    )
    counts = {condition: len(epochs[condition]) for condition in epochs.event_id}
    validate_trial_counts(counts)
    epoch_path = run_dir / "epoch-stage" / sub
    epoch_path.mkdir(parents=True, exist_ok=True)
    epochs.save(epoch_path / "target-epo.fif", overwrite=True, verbose="ERROR")
    evokeds = [epochs[condition].average() for condition in ("related", "unrelated")]
    difference = mne.combine_evoked(evokeds[::-1], weights=[1, -1])
    difference.comment = "unrelated - related"
    erp_path = run_dir / "erp-stage" / sub
    erp_path.mkdir(parents=True, exist_ok=True)
    mne.write_evokeds(erp_path / "conditions-ave.fif", [*evokeds, difference],
                     overwrite=True, verbose="ERROR")
    receipt = {
        "subject": sub, "source_set": str(input_set), "source_events": str(input_events),
        "source_sampling_hz": source_sfreq, "output_sampling_hz": raw.info["sfreq"],
        "scalp_channels": raw.ch_names, "input_targets": len(events),
        "retained_trials": counts,
        "dropped_events": [{"index": i, "reasons": list(reasons)}
                           for i, reasons in enumerate(epochs.drop_log) if reasons],
        "ica": "not run; explicit recipe benchmark branch", "reject": None,
        "reference_max_abs_V": float(np.abs(raw.get_data().mean(axis=0)).max()),
    }
    write_json(pre_path / "receipt.json", receipt)
    return evokeds, receipt


def replay(run_dir: Path) -> dict:
    from scipy.sparse import load_npz

    arrays = np.load(run_dir / "erp-stage" / "group_arrays.npz")
    expected = np.load(run_dir / "stats-stage" / "cluster_arrays.npz")
    summary, actual = compute_statistics(
        arrays["related"], arrays["unrelated"], arrays["times"], arrays["ch_names"],
        load_npz(run_dir / "stats-stage" / "roi_adjacency.npz"),
    )
    checks = {name: bool(np.array_equal(expected[name], value)) for name, value in actual.items()}
    checks["summary"] = summary == json.loads(
        (run_dir / "stats-stage" / "summary.json").read_text(encoding="utf-8-sig"))
    result = {"scope": "group statistics replay from saved participant evokeds",
              "exact_equal": checks, "passed": all(checks.values())}
    write_json(run_dir / "audit-stage" / "replay.json", result)
    assert result["passed"], result
    return result


def run(data_root: Path, run_dir: Path, public_out: Path):
    import mne
    from scipy.sparse import save_npz
    from gen_recipe_case_figures import render

    create_plan(run_dir, data_root)
    related, unrelated, receipts = [], [], []
    for sub in SUBJECTS:
        evokeds, receipt = run_subject(sub, data_root, run_dir)
        related.append(evokeds[0].data)
        unrelated.append(evokeds[1].data)
        receipts.append(receipt)
        print(f"{sub}: {receipt['retained_trials']}", flush=True)
    related, unrelated = np.asarray(related), np.asarray(unrelated)
    info, times = evokeds[0].info, evokeds[0].times
    arrays_path = run_dir / "erp-stage" / "group_arrays.npz"
    np.savez_compressed(arrays_path, related=related, unrelated=unrelated, times=times,
                        ch_names=info["ch_names"], subjects=SUBJECTS)
    mne.io.write_info(run_dir / "erp-stage" / "group-info.fif", info, overwrite=True)
    adjacency = roi_adjacency(info)
    (run_dir / "stats-stage").mkdir(exist_ok=True)
    save_npz(run_dir / "stats-stage" / "roi_adjacency.npz", adjacency)
    summary, stats_arrays = compute_statistics(related, unrelated, times, info["ch_names"], adjacency)
    write_json(run_dir / "stats-stage" / "summary.json", summary)
    np.savez_compressed(run_dir / "stats-stage" / "cluster_arrays.npz", **stats_arrays)
    replay_result = replay(run_dir)
    figure_files = render(run_dir)
    roi_idx = [info["ch_names"].index(name) for name in ROI]
    public_out.parent.mkdir(parents=True, exist_ok=True)
    figure_data_path = public_out.with_name("recipe_case_figure_data.npz")
    np.savez_compressed(
        figure_data_path, times=times, subjects=SUBJECTS, roi=ROI,
        related_roi_uV=related[:, roi_idx] * 1e6,
        unrelated_roi_uV=unrelated[:, roi_idx] * 1e6,
        grand_average_difference_uV=(unrelated-related).mean(0) * 1e6,
        all_ch_names=info["ch_names"],
        positions_m=np.array([ch["loc"][:3] for ch in info["chs"]]),
    )
    versions = {name: importlib.metadata.version(name)
                for name in ["mne", "numpy", "scipy", "pandas", "matplotlib"]}
    write_json(run_dir / "report-stage" / "receipts.json", receipts)
    methods = (
        "Twenty ERP CORE participants (sub-001–sub-020) were analyzed using the "
        "n400-semantic recipe v0.1.0 distributed with AEA v0.3.2. Three EOG channels were "
        "removed before the remaining 30 EEG channels were filtered with a zero-phase "
        "0.1–30 Hz FIR filter, resampled from 1024 to 256 Hz, and average referenced. "
        "Electrode locations used the standard_1020 montage. The recipe's explicitly "
        "documented benchmark branch was selected before analysis: ICA and amplitude-based "
        "trial rejection were omitted (reject=None); annotation-based rejection remained "
        "enabled. Target-word codes 211/212 and 221/222 defined related and unrelated "
        "conditions, respectively. Epochs spanned −200 to 800 ms, with −200 to 0 ms baseline "
        "correction. Each participant retained at least 30 target trials per condition. "
        "Participant-level unrelated-minus-related ERPs were tested in the prespecified "
        "CPz/Cz/Pz ROI from 300 to 500 ms using a negative-tailed, one-sample "
        "spatiotemporal cluster-permutation test (5000 permutations, seed 42). The "
        "cluster-forming threshold was the negative one-sided p<0.05 t value at 19 degrees "
        "of freedom; cluster-level alpha was 0.05. Sensor adjacency was triangulated "
        "using the full 30-channel montage and restricted to the ROI. Grand-average "
        "uncertainty is SEM across participants. The topomap at the most negative "
        "grand-average ROI sample within 300–500 ms is descriptive. This ROI-restricted "
        "test is distinct from the released validation runner's all-channel test."
    )
    (run_dir / "report-stage" / "methods.md").write_text(methods + "\n", encoding="utf-8")
    complete = {
        "case": "n400-recipe-case", "release": "v0.3.2", "recipe": RECIPE,
        "scope": "post-release supplement implementing the released recipe; not a v0.3.2 script",
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "branch": "documented no-ICA, reject=None benchmark branch",
        "cohort": "fixed cached ERP CORE sub-001 through sub-020",
        "status": "complete", "required_stages_complete": True,
        "inference_domain": "CPz/Cz/Pz, 300-500 ms; different from historical all-channel validation",
        "results": summary,
        "retained_trials_per_subject": [
            {"subject": r["subject"], **r["retained_trials"], "n400_uV": float(amplitude)}
            for r, amplitude in zip(receipts, stats_arrays["subject_uV"])
        ],
        "replay": replay_result, "versions": versions,
        "figures": [display_path(p) for p in figure_files],
        "private_outputs": display_path(run_dir),
        "figure_source_data": display_path(figure_data_path),
        "limitations": [
            "No ICA or amplitude-based artifact rejection in this documented benchmark branch.",
            "The 20 cached participants are a worked-example cohort, not the full 40-person source cohort.",
            "Peak topography is descriptive; cluster inference does not localize each electrode/time point.",
            "No held-out benchmark, runtime performance, or clinical efficacy claim.",
        ],
    }
    write_json(run_dir / "report-stage" / "summary.json", complete)
    write_json(public_out, complete)
    (run_dir / "RECIPE_CASE.md").write_text(
        "# Complete N400 released-recipe case\n\n"
        "All required stages completed under the frozen plan. Optional ICA was omitted "
        "under the recipe's explicit benchmark branch, recorded before execution. "
        "C1 uses the recipe-declared ROI, correcting the domain mismatch in the old "
        "validation runner without changing its archived output.\n\n"
        f"N={summary['n_subjects']}; unrelated−related mean={summary['grand_mean_uV']:.6f} µV "
        f"(SEM={summary['sem_uV']:.6f}); cluster minimum p={summary['min_cluster_p']}; "
        f"significant clusters={summary['n_significant_clusters']}. "
        "See stats-stage/summary.json for the complete primary result and "
        "audit-stage/replay.json for exact saved-array replay.\n\n"
        "No resting-state duration was lengthened and no sessions were pooled. "
        "The N400 case uses already local data. The N17015 and MMN extensions remain separate.\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": complete["status"], "results": summary}, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path,
                        default=Path.home() / "mne_data" / "erpcore-N400")
    parser.add_argument("--run-dir", type=Path,
                        default=ROOT / "projects/n400-recipe-case/runs/run-001")
    parser.add_argument("--out", type=Path,
                        help="Summary path (default: RUN_DIR/summary.json); compact figure data alongside")
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    if args.replay:
        print(json.dumps(replay(args.run_dir), indent=2))
        return
    prepare_run_directory(args.run_dir)
    if args.out is None:
        args.out = args.run_dir / "summary.json"
    process = {"pid": os.getpid(), "started_utc": datetime.now(timezone.utc).isoformat(),
               "argv": sys.argv, "exit_code": None}
    write_json(args.run_dir / "process.json", process)
    try:
        run(args.data_root, args.run_dir, args.out)
        process["exit_code"] = 0
    except BaseException:
        process["exit_code"] = 1
        process["error"] = traceback.format_exc()
        raise
    finally:
        process["finished_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(args.run_dir / "process.json", process)


if __name__ == "__main__":
    main()
