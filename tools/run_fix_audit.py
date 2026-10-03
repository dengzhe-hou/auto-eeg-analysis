"""Rerun the approved N100 correction from saved epochs into a new directory.

The 2026-10-04 specification uses six approximate template sites and complete
four-stimulus cycles. It does not recover the original acquisition labels or
establish population inference. Importing this module performs no analysis.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys
import time

import mne
import numpy as np
import scipy
from scipy import stats


ROI_TARGETS = ("Fz", "Cz", "FC1", "FC2", "F3", "F4")
APPROVED_CHANNELS = ("EEG 006", "EEG 021", "EEG 011", "EEG 014", "EEG 005", "EEG 007")
EVENT_NAMES = {1: "auditory/left", 2: "auditory/right", 3: "visual/left",
               4: "visual/right", 5: "smiley", 32: "button"}
EXPECTED_CYCLE = np.array([2, 3, 1, 4])
WINDOW = (0.08, 0.15)
SEED = 42
N_PERMUTATIONS = 5000
ASSUMPTIONS = [
    "This is a single-subject example; it does not support population inference.",
    "Conditions follow fixed within-cycle positions, not randomized assignment; "
    "condition effects cannot be separated from within-cycle position effects.",
    "The sign-flip null assumes independent cycle differences with a symmetric "
    "distribution about zero; the fixed presentation order does not guarantee this.",
    "The six ROI electrodes approximate template sites after coordinate-frame "
    "alignment; their original acquisition labels have not been recovered.",
    "Only complete four-condition cycles enter the approved analysis. The 45 "
    "target trials in smiley-interrupted cycles are explicitly excluded, not "
    "classified as artifact rejections.",
]


def recover_cycles(events: np.ndarray, epoch_events: np.ndarray) -> dict:
    """Recover fixed cycles and match every target event to its saved epoch.

    Unexpected condition positions or missing epochs raise an error rather than
    changing the sample. This function uses event identifiers, not EEG values.
    """
    events = np.asarray(events, dtype=int)
    epoch_events = np.asarray(epoch_events, dtype=int)
    unknown = set(events[:, 2]) - set(EVENT_NAMES)
    if unknown:
        raise ValueError(f"Unexpected event codes: {sorted(unknown)}")
    stimulus_events = events[events[:, 2] != 32]
    if len(stimulus_events) % 4:
        raise ValueError("Stimulus sequence does not contain complete four-position cycles")
    cycle_events = stimulus_events.reshape(-1, 4, 3)
    codes = cycle_events[:, :, 2]
    if np.any((codes != EXPECTED_CYCLE) & (codes != 5)):
        raise ValueError("Non-smiley event does not match the fixed [2, 3, 1, 4] cycle")
    target_events = events[np.isin(events[:, 2], [1, 2, 3, 4])]
    if len(np.unique(target_events[:, 0])) != len(target_events):
        raise ValueError("Duplicate target event sample indices")
    if len(np.unique(epoch_events[:, 0])) != len(epoch_events):
        raise ValueError("Duplicate cached epoch event sample indices")
    target_map = {int(row[0]): int(row[2]) for row in target_events}
    epoch_map = {int(row[0]): (index, int(row[2]))
                 for index, row in enumerate(epoch_events)}
    missing = sorted(set(target_map) - set(epoch_map))
    extra = sorted(set(epoch_map) - set(target_map))
    if missing or extra:
        raise ValueError(f"Cached target epoch mismatch: missing={missing}, extra={extra}")
    mismatched = [sample for sample, code in target_map.items()
                  if epoch_map[sample][1] != code]
    if mismatched:
        raise ValueError(f"Cached epoch condition mismatch at samples: {mismatched}")
    complete_cycles, incomplete_cycles, excluded_trials = [], [], []
    for cycle_index, cycle in enumerate(cycle_events):
        records = []
        for position, row in enumerate(cycle):
            sample, _, code = map(int, row)
            records.append({
                "cycle_index": cycle_index, "position": position,
                "raw_sample": sample, "event_code": code,
                "condition": EVENT_NAMES[code],
                "epoch_index": epoch_map[sample][0] if code != 5 else None,
            })
        record = {"cycle_index": cycle_index, "stimuli": records}
        if np.all(cycle[:, 2] == EXPECTED_CYCLE):
            complete_cycles.append(record)
        else:
            incomplete_cycles.append(record)
            excluded_trials.extend(item for item in records if item["event_code"] != 5)
    return {
        "n_raw_events": len(events), "n_button_events": int(np.sum(events[:, 2] == 32)),
        "n_smiley_events": int(np.sum(events[:, 2] == 5)),
        "n_target_events": len(target_events), "n_cached_target_epochs": len(epoch_events),
        "target_retention_percent": 100 * len(epoch_events) / len(target_events),
        "n_cycles": len(cycle_events), "n_complete_cycles": len(complete_cycles),
        "n_incomplete_cycles": len(incomplete_cycles),
        "n_included_target_trials": 4 * len(complete_cycles),
        "n_excluded_target_trials": len(excluded_trials),
        "complete_cycles": complete_cycles, "incomplete_cycles": incomplete_cycles,
        "excluded_target_trials": excluded_trials,
    }


def resolve_roi(raw_info: mne.Info, epoch_channels: list[str]) -> dict:
    """Find one actual electrode nearest each target in the same head frame."""
    picks = mne.pick_types(raw_info, eeg=True, exclude=[])
    if any(int(raw_info["chs"][i]["coord_frame"]) != 4 for i in picks):
        raise ValueError("Expected EEG channel positions in FIFF head coordinates (4)")
    actual_names = [raw_info["ch_names"][i] for i in picks]
    actual_positions = np.array([raw_info["chs"][i]["loc"][:3] for i in picks])
    montage = mne.channels.transform_to_head(
        mne.channels.make_standard_montage("standard_1020")
    )
    targets = montage.get_positions()["ch_pos"]
    rows = []
    for target in ROI_TARGETS:
        distances = np.linalg.norm(actual_positions - targets[target], axis=1)
        nearest = int(np.argmin(distances))
        channel = actual_names[nearest]
        if channel not in epoch_channels:
            raise ValueError(f"Nearest electrode for {target} is absent from cached epochs: {channel}")
        rows.append({
            "target": target, "actual_channel": channel,
            "actual_head_position_m": actual_positions[nearest].tolist(),
            "target_head_position_m": targets[target].tolist(),
            "distance_mm": float(distances[nearest] * 1000),
        })
    actual_roi = tuple(row["actual_channel"] for row in rows)
    if actual_roi != APPROVED_CHANNELS:
        raise ValueError(f"Nearest-electrode ROI differs from the approved specification: {actual_roi}")
    return {"coordinate_frame": "head", "template": "standard_1020",
            "mapping": rows, "all_sensor_names": actual_names,
            "all_sensor_positions_m": actual_positions.tolist()}


def make_cycle_data(epoch_data: np.ndarray, accounting: dict,
                    roi_indices: list[int]) -> tuple[np.ndarray, np.ndarray]:
    """Return cycle × ROI × time arrays, retaining both modalities per cycle."""
    indices = np.array([[item["epoch_index"] for item in cycle["stimuli"]]
                        for cycle in accounting["complete_cycles"]], dtype=int)
    selected = epoch_data[:, roi_indices, :][indices]
    return selected[:, [0, 2]].mean(axis=1), selected[:, [1, 3]].mean(axis=1)


def describe_clusters(t_obs: np.ndarray, masks: list[np.ndarray],
                      p_values: np.ndarray, times: np.ndarray) -> tuple[list[dict], np.ndarray]:
    """Serialize every cluster, including non-significant clusters."""
    labels = np.zeros(t_obs.shape, dtype=np.int32)
    records = []
    for index, (mask, p_value) in enumerate(zip(masks, p_values)):
        time_indices, channel_indices = np.where(mask)
        unique_channels = np.unique(channel_indices)
        labels[mask] = index + 1  # 0 denotes samples outside every cluster.
        records.append({
            "cluster_id": index, "label": index + 1, "p": float(p_value),
            "significant": bool(p_value < 0.05),
            "t_sum": float(t_obs[mask].sum()), "n_points": int(mask.sum()),
            "time_ms": [float(times[time_indices.min()] * 1000),
                        float(times[time_indices.max()] * 1000)],
            "channels": [APPROVED_CHANNELS[i] for i in unique_channels],
            "targets": [ROI_TARGETS[i] for i in unique_channels],
        })
    return records, labels


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def run_case(project: Path, out: Path) -> dict:
    """Execute the fixed correction; inputs and historical outputs stay untouched."""
    project, out = project.resolve(), out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc)
    clock_start = time.perf_counter()
    environment = {
        "started_utc": started.isoformat(), "python": sys.version,
        "platform": platform.platform(), "mne": mne.__version__,
        "numpy": np.__version__, "scipy": scipy.__version__,
        "runner": str(Path(__file__).resolve()), "project": str(project),
        "output": str(out), "status": "running",
    }
    _write_json(out / "execution.json", environment)
    raw_path = project / "raw/sub-01.fif"
    epochs_path = project / "epoch-stage/sub-01/sub-01-epo.fif"
    raw = mne.io.read_raw_fif(raw_path, preload=False)
    events = mne.find_events(raw, stim_channel="STI 014", shortest_event=1)
    epochs = mne.read_epochs(epochs_path, preload=True)
    accounting = recover_cycles(events, epochs.events)
    expected = {"n_cycles": 76, "n_complete_cycles": 61, "n_incomplete_cycles": 15,
                "n_included_target_trials": 244, "n_excluded_target_trials": 45,
                "n_target_events": 289}
    for field, value in expected.items():
        if accounting[field] != value:
            raise ValueError(f"Approved input accounting mismatch: {field}={accounting[field]}, expected {value}")
    roi = resolve_roi(raw.info, epochs.ch_names)
    roi_indices = [epochs.ch_names.index(channel) for channel in APPROVED_CHANNELS]
    auditory, visual = make_cycle_data(epochs.get_data(), accounting, roi_indices)
    differences = auditory - visual
    time_mask = (epochs.times >= WINDOW[0]) & (epochs.times <= WINDOW[1])
    stat_times = epochs.times[time_mask]
    x_stat = differences[:, :, time_mask].transpose(0, 2, 1)
    degrees_freedom = len(differences) - 1
    threshold = -float(stats.t.ppf(0.95, degrees_freedom))
    roi_info = mne.pick_info(epochs.info, roi_indices)
    adjacency, adjacency_names = mne.channels.find_ch_adjacency(roi_info, ch_type="eeg")
    if list(adjacency_names) != list(APPROVED_CHANNELS):
        raise ValueError("Adjacency channel order differs from the approved ROI order")
    t_obs, masks, p_values, null_distribution = mne.stats.spatio_temporal_cluster_1samp_test(
        x_stat, threshold=threshold, tail=-1, n_permutations=N_PERMUTATIONS,
        seed=SEED, adjacency=adjacency, out_type="mask", n_jobs=1,
    )
    cluster_records, cluster_labels = describe_clusters(t_obs, masks, p_values, stat_times)
    auditory_roi = auditory[:, :, time_mask].mean(axis=(1, 2)) * 1e6
    visual_roi = visual[:, :, time_mask].mean(axis=(1, 2)) * 1e6
    cycle_difference = auditory_roi - visual_roi
    dz = float(cycle_difference.mean() / cycle_difference.std(ddof=1))
    spec = {
        "contrast": "auditory_minus_visual", "statistical_unit": "complete four-stimulus cycle",
        "cycle_pattern": EXPECTED_CYCLE.tolist(),
        "cycle_difference": "(code1 + code2)/2 - (code3 + code4)/2",
        "window_s": list(WINDOW), "roi_targets": list(ROI_TARGETS),
        "roi_channels": list(APPROVED_CHANNELS),
        "test": "mne.stats.spatio_temporal_cluster_1samp_test",
        "tail": -1, "n_permutations": N_PERMUTATIONS, "seed": SEED,
        "cluster_forming_p": 0.05, "cluster_forming_threshold_t": threshold,
        "df": degrees_freedom, "cluster_alpha": 0.05,
        "adjacency": "Delaunay triangulation of the six measured head-coordinate electrodes",
        "max_step": 1, "t_power": 1, "effect_size": "paired cycle-level Cohen dz, sample SD ddof=1",
        "multiple_comparisons": "cluster permutation over six channels and the planned time window; one claim",
    }
    claim = {
        "claim_id": "C1", "claim": "Auditory minus visual N100 in the approved ROI and window",
        "n": len(differences), "n_cycles": len(differences),
        "n_trials_a": 2 * len(differences), "n_trials_b": 2 * len(differences),
        "n_target_trials_used": accounting["n_included_target_trials"],
        "n_target_trials_available": accounting["n_target_events"],
        "n_target_trials_excluded_incomplete_cycles": accounting["n_excluded_target_trials"],
        "mean_a": float(auditory_roi.mean()), "mean_b": float(visual_roi.mean()),
        "mean_diff": float(cycle_difference.mean()), "unit": "µV", "dz": dz,
        "min_p": min((row["p"] for row in cluster_records), default=None),
        "n_sig": sum(row["significant"] for row in cluster_records), "cluster_alpha": 0.05,
        "n_clusters": len(cluster_records), "clusters": cluster_records,
        "spec": spec, "assumptions": ASSUMPTIONS,
    }
    summary = {
        "case": "n100", "condition_a_name": "Auditory", "condition_b_name": "Visual",
        "claims": [claim], "input_files": {"raw": str(raw_path), "epochs": str(epochs_path)},
        "input_accounting": accounting, "roi": roi,
        "cached_epochs": {"tmin": float(epochs.tmin), "tmax": float(epochs.tmax),
                          "baseline": list(epochs.baseline) if epochs.baseline else None,
                          "sfreq_hz": float(epochs.info["sfreq"]),
                          "drop_log_ignored": sum("IGNORED" in reasons for reasons in epochs.drop_log),
                          "retained_condition_counts": {name: len(epochs[name]) for name in epochs.event_id}},
        "assumptions": ASSUMPTIONS,
    }
    stats_dir = out / "stats-stage"
    stats_dir.mkdir()
    _write_json(stats_dir / "C1_cluster_perm.json", claim)
    np.savez_compressed(
        stats_dir / "C1_arrays.npz", t_obs=t_obs, cluster_labels=cluster_labels,
        cluster_p=p_values, H0=null_distribution, times=stat_times,
        roi_channels=np.array(APPROVED_CHANNELS), roi_targets=np.array(ROI_TARGETS),
        adjacency=adjacency.toarray(), cycle_difference_uv=cycle_difference,
        cycle_a_uv=auditory_roi, cycle_b_uv=visual_roi,
        cycle_indices=np.array([row["cycle_index"] for row in accounting["complete_cycles"]]),
    )
    np.savez_compressed(
        stats_dir / "C1_inputs.npz", x_stat_v=x_stat, times=stat_times,
        window_s=np.array(WINDOW), roi_channels=np.array(APPROVED_CHANNELS),
        cycle_indices=np.array([row["cycle_index"] for row in accounting["complete_cycles"]]),
        raw_samples=np.array([[item["raw_sample"] for item in row["stimuli"]]
                              for row in accounting["complete_cycles"]]),
        event_codes=np.array([[item["event_code"] for item in row["stimuli"]]
                              for row in accounting["complete_cycles"]]),
        epoch_indices=np.array([[item["epoch_index"] for item in row["stimuli"]]
                                 for row in accounting["complete_cycles"]]),
    )
    traces = {"condition_a": auditory.mean(axis=1) * 1e6,
              "condition_b": visual.mean(axis=1) * 1e6,
              "difference": differences.mean(axis=1) * 1e6}
    plot_arrays = {key + "_uv": values.mean(axis=0) for key, values in traces.items()}
    plot_arrays.update({key + "_sem_uv": values.std(axis=0, ddof=1) / np.sqrt(len(values))
                        for key, values in traces.items()})
    np.savez_compressed(
        out / "plot_arrays.npz", **plot_arrays, times=epochs.times,
        condition_a_name=np.array("Auditory"), condition_b_name=np.array("Visual"),
        roi_positions_m=np.array([row["actual_head_position_m"] for row in roi["mapping"]]),
        target_positions_m=np.array([row["target_head_position_m"] for row in roi["mapping"]]),
        roi_channels=np.array(APPROVED_CHANNELS), roi_targets=np.array(ROI_TARGETS),
        all_sensor_positions_m=np.array(roi["all_sensor_positions_m"]),
        all_sensor_names=np.array(roi["all_sensor_names"]), window_s=np.array(WINDOW),
        stat_times=stat_times, t_obs=t_obs, cluster_labels=cluster_labels, cluster_p=p_values,
    )
    _write_json(out / "summary.json", summary)
    roi_description = "; ".join(f"{row['target']} represented by {row['actual_channel']} "
                                f"({row['distance_mm']:.2f} mm)" for row in roi["mapping"])
    methods = (
        "# N100 correction methods\n\n"
        "Saved single-subject epochs were reused without rerunning preprocessing. "
        "The historical voltage rejection threshold was 150 µV peak-to-peak. "
        f"All {accounting['n_cached_target_epochs']}/{accounting['n_target_events']} target epochs "
        f"were retained ({accounting['target_retention_percent']:.1f}%). The "
        f"{accounting['n_button_events'] + accounting['n_smiley_events']} non-target events "
        "were not artifact rejections.\n\n"
        "The raw stimulus sequence, retaining smileys and excluding button presses, comprises "
        "76 fixed [auditory/right, visual/left, auditory/left, visual/right] cycles. "
        "The approved analysis uses 61 complete cycles, each contributing the mean of its two "
        "auditory epochs minus the mean of its two visual epochs. The 45 target trials in the "
        "15 smiley-interrupted cycles are excluded from this analysis and are individually "
        "listed in summary.json. No additional target epoch is missing.\n\n"
        "The standard_1020 montage was transformed to head coordinates before selecting the "
        f"nearest measured electrode for each planned target: {roi_description}. These are "
        "approximate template-site correspondences, not recovered acquisition labels.\n\n"
        "One negative-tailed spatiotemporal cluster test covered all six electrodes and "
        f"80–150 ms, with 5000 sign-flip permutations, seed 42, and a cluster-forming "
        f"t threshold of {threshold:.8f} (one-sided p = 0.05, df = 60). Channel adjacency "
        "was obtained by Delaunay triangulation of measured electrode positions. Cluster mass "
        "was the sum of t statistics; temporal adjacency connected successive time samples. "
        "All clusters and their probabilities are retained. Cycle-level Cohen dz is the mean "
        "ROI/window difference divided by its sample standard deviation (ddof = 1). "
        "Waveforms, mean amplitudes, and SEM use the same 61 cycles and 244 trials.\n\n"
        + "\n".join(f"- {assumption}" for assumption in ASSUMPTIONS) + "\n"
    )
    (out / "methods.md").write_text(methods, encoding="utf-8")
    cluster_lines = [f"- Cluster {row['cluster_id']}: p = {row['p']:.6g}, "
                     f"t sum = {row['t_sum']:.6g}, significant = {row['significant']}."
                     for row in cluster_records]
    findings = (
        "# N100 corrected run\n\n"
        f"Auditory mean: {claim['mean_a']:.6f} µV; visual mean: {claim['mean_b']:.6f} µV; "
        f"auditory minus visual: {claim['mean_diff']:.6f} µV; cycle-level dz: {dz:.6f}.\n\n"
        "The analysis uses 61 complete cycles (122 auditory and 122 visual trials). "
        "The 45 target trials in incomplete cycles are retained in input-accounting records "
        "and excluded from this approved analysis.\n\n"
        f"{claim['n_sig']} significant clusters out of {len(cluster_records)} total clusters.\n\n"
        + ("\n".join(cluster_lines) if cluster_lines else "No clusters passed the forming threshold.")
        + "\n\n" + "\n".join(f"- {item}" for item in ASSUMPTIONS) + "\n"
    )
    (out / "FINDINGS.md").write_text(findings, encoding="utf-8")
    environment.update({"finished_utc": datetime.now(timezone.utc).isoformat(),
                        "elapsed_seconds": time.perf_counter() - clock_start,
                        "status": "completed"})
    _write_json(out / "execution.json", environment)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path("projects/mne-sample-audvis"))
    parser.add_argument("--out", type=Path, required=True,
                        help="New output directory; an existing path is never overwritten")
    args = parser.parse_args()
    summary = run_case(args.project, args.out)
    print(json.dumps({"case": summary["case"], "output": str(args.out.resolve()),
                      "claim": summary["claims"][0]}, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
