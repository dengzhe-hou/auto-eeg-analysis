"""Run the single-participant Flankers case study into a new output directory.

The repair keeps all retained trials and the three planned domains. Compatibility
labels are permuted within original block × target-side strata. This assumes
conditional exchangeability, not a reconstruction of the task randomization.

Use saved epochs without refitting ICA::

    python tools/run_full_case_study.py --reuse-epochs --out /path/to/new-run

Omit ``--reuse-epochs`` for the original preprocessing, ICA and epoching steps
from ``--project/raw/sub-01.fif``. Both modes preserve the source project and
its historical plan/results. A separate plotter reads the output arrays.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess
import time

import mne
import numpy as np

if __package__:
    from .case_study_stats import blocked_cluster_test
else:
    from case_study_stats import blocked_cluster_test


SEED = 42
N_PERMUTATIONS = 5000
FORMING_ALPHA = 0.05
CLUSTER_ALPHA = 0.05 / 3
ROI = ["FCz", "Fz", "Cz"]
FREQUENCIES = np.arange(4.0, 30.0, 1.0)
CLAIM_SPECS = (
    {"claim_id": "C1", "name": "Stimulus-locked N2 compatibility contrast",
     "window_s": [0.2, 0.35], "tail": -1,
     "feature_axes": ["time", "channel"]},
    {"claim_id": "C2", "name": "Response-locked compatibility contrast",
     "window_s": [0.0, 0.1], "tail": -1,
     "feature_axes": ["time", "channel"]},
    {"claim_id": "C3", "name": "Frontal theta compatibility contrast",
     "window_s": [0.2, 0.5], "freq_range_hz": [4.0, 8.0], "tail": 1,
     "feature_axes": ["time", "frequency", "channel"]},
)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


def source_events(raw: mne.io.BaseRaw) -> tuple[np.ndarray, np.ndarray, dict]:
    """Read explicit annotation names, retaining original raw samples."""
    ids = {
        "response/left": 1, "response/right": 2,
        "stimulus/compatible/target_left": 3,
        "stimulus/compatible/target_right": 4,
        "stimulus/incompatible/target_left": 5,
        "stimulus/incompatible/target_right": 6,
    }
    events, _ = mne.events_from_annotations(raw, event_id=ids, verbose=False)
    stimuli = events[np.isin(events[:, 2], [3, 4, 5, 6])]
    responses = events[np.isin(events[:, 2], [1, 2])]
    if len(stimuli) == 0 or len(responses) == 0:
        raise ValueError("The Flankers source needs stimulus and response annotations.")
    gaps = np.diff(stimuli[:, 0]) / raw.info["sfreq"]
    block = np.r_[0, np.cumsum(gaps > 2.0)]
    report = {
        "event_id": ids, "block_gap_threshold_s": 2.0,
        "block_break_after_trials": (np.flatnonzero(gaps > 2.0) + 1).tolist(),
        "block_sizes": np.bincount(block).tolist(),
        "between_block_gaps_s": gaps[gaps > 2.0].tolist(),
        "within_block_max_gap_s": float(gaps[gaps <= 2.0].max()),
        "original_counts_per_block": [
            {str(k): int(v) for k, v in Counter(
                stimuli[block == b, 2].tolist()).items()}
            for b in np.unique(block)
        ],
        "randomization_boundary": (
            "Block structure and target side recovered from original event records; "
            "the complete original task randomization algorithm was not verified."
        ),
    }
    return stimuli, responses, report


def condition_response_events(stimuli: np.ndarray, responses: np.ndarray) -> np.ndarray:
    """Label the response by preceding stimulus compatibility, not correctness."""
    preceding = np.searchsorted(stimuli[:, 0], responses[:, 0], side="left") - 1
    keep = preceding >= 0
    result = responses[keep].copy()
    codes = stimuli[preceding[keep], 2]
    result[:, 2] = np.where(np.isin(codes, [5, 6]), 202, 201)
    return result


def trial_metadata(epochs: mne.Epochs, stimuli: np.ndarray,
                   responses: np.ndarray, sfreq: float, *, response_locked: bool) -> dict:
    """Join saved epoch event samples to the original, unremapped trial table."""
    samples = epochs.events[:, 0]
    if response_locked:
        if not np.all(np.isin(samples, responses[:, 0])):
            raise ValueError("A saved response epoch has no original response event.")
        indices = np.searchsorted(stimuli[:, 0], samples, side="left") - 1
        if np.any(indices < 0):
            raise ValueError("A saved response epoch precedes the first stimulus.")
    else:
        indices = np.searchsorted(stimuli[:, 0], samples)
        if np.any(indices >= len(stimuli)) or not np.array_equal(
                stimuli[indices, 0], samples):
            raise ValueError("Saved stimulus epoch samples do not match original events.")
    if len(np.unique(indices)) != len(indices):
        raise ValueError("More than one retained epoch maps to the same stimulus trial.")
    codes = stimuli[indices, 2]
    labels = np.isin(codes, [5, 6])
    expected_codes = np.where(labels, 202 if response_locked else 102,
                              201 if response_locked else 101)
    if not np.array_equal(epochs.events[:, 2], expected_codes):
        raise ValueError("Saved epoch labels disagree with original stimulus codes.")
    blocks = np.r_[0, np.cumsum(np.diff(stimuli[:, 0]) / sfreq > 2.0)][indices]
    target_side = np.isin(codes, [4, 6]).astype(int)
    strata = blocks * 2 + target_side
    counts = []
    for stratum in np.unique(strata):
        group = strata == stratum
        n_comp, n_incomp = int(np.sum(group & ~labels)), int(np.sum(group & labels))
        if min(n_comp, n_incomp) == 0:
            raise ValueError("A retained block × target-side stratum lacks one condition.")
        counts.append({"stratum": int(stratum), "block": int(stratum // 2 + 1),
                       "target_side": "right" if stratum % 2 else "left",
                       "compatible": n_comp, "incompatible": n_incomp})
    return {"raw_event_sample": samples.tolist(),
            "original_stimulus_index": indices.tolist(),
            "original_stimulus_sample": stimuli[indices, 0].tolist(),
            "original_stimulus_code": codes.tolist(), "block_zero_based": blocks.tolist(),
            "target_side_right": target_side.tolist(), "strata": strata.tolist(),
            "incompatible": labels.tolist(), "counts_per_stratum": counts}


def build_epochs(out: Path, raw: mne.io.BaseRaw, stimuli: np.ndarray,
                 responses: np.ndarray) -> tuple[mne.Epochs, mne.Epochs, dict]:
    """Execute the historical upstream configuration, saving into the new run."""
    from mne_icalabel import label_components

    raw_eeg = raw.copy().load_data().pick_types(eeg=True)
    raw_eeg.filter(l_freq=0.1, h_freq=30.0, n_jobs=1)
    raw_eeg.notch_filter(60.0, n_jobs=1)
    raw_eeg.set_eeg_reference("average", projection=False)
    pp = out / "preprocess-stage/sub-01"
    pp.mkdir(parents=True)
    raw_eeg.save(pp / "sub-01_preprocessed_raw.fif", overwrite=False)
    write_json(pp / "preprocess_summary.json", {
        "bandpass_hz": [0.1, 30.0], "notch_hz": 60.0, "reference": "average",
        "n_channels": len(raw_eeg.ch_names), "sfreq": raw_eeg.info["sfreq"],
    })
    raw_hp = raw_eeg.copy().filter(l_freq=1.0, h_freq=None)
    ica = mne.preprocessing.ICA(n_components=15, method="infomax", random_state=SEED,
                                max_iter="auto", fit_params={"extended": True})
    ica.fit(raw_hp)
    component_labels = label_components(raw_hp, ica, method="iclabel")["labels"]
    ica.exclude = [i for i, label in enumerate(component_labels)
                   if label in {"eye blink", "muscle artifact", "heart beat"}]
    clean = raw_eeg.copy()
    ica.apply(clean)
    ica_dir = out / "ica-stage/sub-01"
    ica_dir.mkdir(parents=True)
    clean.save(ica_dir / "sub-01_ica-cleaned_raw.fif", overwrite=False)
    ica_summary = {"method": "infomax_extended", "n_components": int(ica.n_components_),
                   "labels": component_labels, "excluded": ica.exclude, "seed": SEED}
    write_json(ica_dir / "ica_summary.json", ica_summary)
    stimulus_events = stimuli.copy()
    stimulus_events[:, 2] = np.where(np.isin(stimuli[:, 2], [5, 6]), 102, 101)
    stim = mne.Epochs(clean, stimulus_events,
                      event_id={"compatible": 101, "incompatible": 102},
                      tmin=-0.2, tmax=0.8, baseline=(-0.2, 0),
                      preload=True, reject={"eeg": 150e-6})
    resp = mne.Epochs(clean, condition_response_events(stimuli, responses),
                      event_id={"comp_resp": 201, "incomp_resp": 202},
                      tmin=-0.4, tmax=0.6, baseline=(-0.4, -0.2),
                      preload=True, reject={"eeg": 150e-6})
    epoch_dir = out / "epoch-stage/sub-01"
    epoch_dir.mkdir(parents=True)
    stim.save(epoch_dir / "sub-01_stim-epo.fif", overwrite=False)
    resp.save(epoch_dir / "sub-01_resp-epo.fif", overwrite=False)
    write_json(epoch_dir / "epoch_summary.json", {
        "stim_locked": {"n": len(stim), "per_cond": {k: len(stim[k]) for k in stim.event_id}},
        "resp_locked": {"n": len(resp), "per_cond": {k: len(resp[k]) for k in resp.event_id}},
        "peak_to_peak_reject_uV": 150.0,
    })
    return stim, resp, {"upstream_rerun": True, "ica": ica_summary,
                        "epochs_source": str(epoch_dir.resolve())}


def effect_summary(values: np.ndarray, labels: np.ndarray) -> dict:
    """Report all-trial planned-domain means and pooled sample-SD Cohen's d."""
    a, b = values[labels], values[~labels]
    pooled_variance = ((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / (
        len(a) + len(b) - 2)
    if pooled_variance <= 0:
        raise ValueError("Pooled trial variance must be positive to report Cohen's d.")
    return {"mean_a": float(a.mean()), "mean_b": float(b.mean()),
            "diff": float(a.mean() - b.mean()),
            "cohens_d": float((a.mean() - b.mean()) / np.sqrt(pooled_variance)),
            "n_per_condition": {"incompatible": len(a), "compatible": len(b)},
            "condition_a": "incompatible", "condition_b": "compatible",
            "effect_size_definition": (
                "Difference of condition means of each trial's full planned-domain average, "
                "divided by pooled within-condition sample SD (ddof=1); descriptive, "
                "without block or target-side adjustment."
            )}


def run_claim(spec: dict, data: np.ndarray, metadata: dict, times: np.ndarray,
              spatial_adjacency, out: Path, *, unit: str, frequencies=None) -> dict:
    """Test every retained trial in the complete specified feature domain."""
    labels = np.asarray(metadata["incompatible"], dtype=bool)
    strata = np.asarray(metadata["strata"], dtype=int)
    dimensions = data.shape[1:]
    if frequencies is None:
        adjacency = mne.stats.combine_adjacency(len(times), spatial_adjacency).tocsr()
    else:
        adjacency = mne.stats.combine_adjacency(
            len(times), len(frequencies), spatial_adjacency).tocsr()
    flat = data.reshape(len(data), -1)
    stats_dir = out / "stats-stage"
    stats_dir.mkdir(exist_ok=True)
    input_path = stats_dir / f"{spec['claim_id']}_inputs.npz"
    np.savez_compressed(input_path, X=flat, labels=labels, strata=strata,
                        feature_shape=np.asarray(dimensions),
                        feature_axes=np.asarray(spec["feature_axes"]),
                        adjacency_data=adjacency.data, adjacency_indices=adjacency.indices,
                        adjacency_indptr=adjacency.indptr, adjacency_shape=np.asarray(adjacency.shape),
                        raw_event_samples=np.asarray(metadata["raw_event_sample"]))
    result = blocked_cluster_test(
        flat, labels, strata, adjacency, tail=spec["tail"],
        n_permutations=N_PERMUTATIONS, seed=SEED, forming_alpha=FORMING_ALPHA)
    t_obs = np.asarray(result["t_obs"]).reshape(dimensions)
    cluster_labels = np.asarray(result["cluster_labels"]).reshape(dimensions)
    p_values = np.asarray(result["cluster_p"])
    cluster_summaries = []
    for index, p in enumerate(p_values, 1):
        members = cluster_labels == index
        coordinates = np.where(members)
        entry = {"id": index, "p": float(p), "p_bonferroni": min(1.0, float(p) * 3),
                 "significant": bool(p < CLUSTER_ALPHA),
                 "signed_t_sum": float(t_obs[members].sum()),
                 "mass": float(abs(t_obs[members].sum())),
                 "n_features": int(members.sum()),
                 "time_ms": [float(times[coordinates[0].min()] * 1000),
                             float(times[coordinates[0].max()] * 1000)],
                 "channels": [ROI[i] for i in np.unique(coordinates[-1])]}
        if frequencies is not None:
            entry["freq_range_hz"] = [float(frequencies[coordinates[1].min()]),
                                      float(frequencies[coordinates[1].max()])]
        cluster_summaries.append(entry)
    array_path = stats_dir / f"{spec['claim_id']}_arrays.npz"
    np.savez_compressed(array_path, t_obs=t_obs, cluster_labels=cluster_labels,
                        cluster_p=p_values, H0=result["H0"], times=times,
                        frequencies=np.array([]) if frequencies is None else frequencies,
                        channels=np.asarray(ROI), trial_labels=labels, trial_strata=strata,
                        raw_event_samples=np.asarray(metadata["raw_event_sample"]))
    significant = [x["id"] for x in cluster_summaries if x["significant"]]
    summary = {
        "claim_id": spec["claim_id"], "name": spec["name"],
        "spec": {**spec, "roi": ROI, "n_permutations": N_PERMUTATIONS, "seed": SEED,
                 "forming_alpha": FORMING_ALPHA, "cluster_alpha": CLUSTER_ALPHA,
                 "permutation_unit": "trial", "permutation_strata": "block × target side",
                 "test": "pooled independent-samples t, within-stratum label permutation",
                 "adjacency": "ROI triangulation × adjacent time samples" +
                              (" × adjacent frequency bins" if frequencies is not None else "")},
        "unit": unit, **effect_summary(data.mean(axis=tuple(range(1, data.ndim))), labels),
        "feature_shape": list(dimensions), "threshold": float(result["threshold"]),
        "df": int(result["df"]), "cluster_alpha": CLUSTER_ALPHA,
        "cluster_p": p_values.tolist(), "clusters": cluster_summaries,
        "significant_clusters": significant, "n_sig": len(significant),
        "min_p": float(p_values.min()) if len(p_values) else None,
        "verdict": "supports" if significant else "does_not_support",
        "statistics_file": str(array_path.relative_to(out)),
        "statistics_input_file": str(input_path.relative_to(out)),
        "cluster_domain_note": "Cluster extent is not an onset/offset confidence interval.",
    }
    write_json(stats_dir / f"{spec['claim_id']}_cluster_perm.json", summary)
    return summary


def environment_record() -> dict:
    repo = Path(__file__).resolve().parents[1]
    return {"python": platform.python_version(), "platform": platform.platform(),
            "packages": {name: version(name) for name in ("mne", "numpy", "scipy", "mne-icalabel")},
            "git_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
            "git_dirty": bool(subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=repo, text=True).strip())}


def reports(summary: dict, out: Path) -> None:
    c1, c2, _ = summary["claims"]
    scope = ("Only downstream analysis was executed from saved ICA-cleaned epochs; "
             "preprocessing and ICA were not rerun." if summary["reuse_epochs"] else
             "Preprocessing, ICA, epoching and downstream analysis were executed in this run.")
    methods = f"""# Flankers case-study methods

This is an internally produced single-participant demonstration using ERP CORE Subject-001. {scope}
The source epoch configuration is 0.1–30 Hz zero-phase FIR filtering, 60 Hz notch filtering,
average reference, extended Infomax ICA with 15 components and seed 42, and ICLabel exclusion
of eye-blink, muscle-artifact and heart-beat components. Actual component labels/exclusions are
recorded in the ICA summary identified in summary.json.
Stimulus epochs span −0.2 to 0.8 s with a −0.2 to 0 s baseline. Response epochs span −0.4 to
0.6 s with a −0.4 to −0.2 s baseline. Rejection uses a 150 µV peak-to-peak EEG threshold.
All {sum(c1['n_per_condition'].values())} retained stimulus trials and
{sum(c2['n_per_condition'].values())} retained response trials were included without equal-count truncation.

C1 compares incompatible minus compatible stimulus-locked activity at FCz/Fz/Cz in 200–350 ms.
C2 makes the same compatibility contrast on response-locked activity at FCz/Fz/Cz in 0–100 ms.
C2 is not the canonical error-minus-correct ERN contrast. C3 tests the complete 4–8 Hz,
200–500 ms, FCz/Fz/Cz domain. Morlet power uses 4–29 Hz, n_cycles=freqs/3, zero_mean=True,
use_fft=False, and decim=4. Baseline normalization is applied separately to every trial and
channel/frequency before averaging: 10 log10(power / mean baseline power), in dB. This same
quantity is used in statistics, figures and descriptive summaries.

Each claim uses a pooled independent-samples t statistic with compatibility-label permutations
restricted to original block × target-side strata, retaining each stratum's condition counts.
This assumes conditional exchangeability within the strata; the original task randomization
algorithm was not reconstructed. Original samples link each retained epoch to its stimulus,
block and target side. Block gaps greater than 2 s separate the recorded 40-trial blocks.
The cluster adjacency combines the original three-channel triangulation with neighboring time
samples and, for C3, neighboring frequency bins. All tests use 5,000 permutations, seed 42,
one-sided cluster-forming p=0.05, tails −1/−1/+1, and cluster p<0.05/3 after Bonferroni across
the three claims. Cluster masses sum signed t values; negative-tail null maxima use positive
absolute masses. Full observed maps, cluster labels, every cluster p-value and permutation
null are saved. Cluster extents are not onset/offset confidence intervals.

Cohen's d is reported for every claim regardless of significance, using each trial's full
planned-domain mean and pooled within-condition sample variance (ddof=1). It is a descriptive
effect size without block or side adjustment. Inference is conditional on this participant's
retained trials and does not support population conclusions. Methods are produced by the saved
Python program from its configuration and result records, not a new LLM generation.

Execution time for this run scope: {summary['elapsed_seconds']:.3f} s.
Environment: Python {summary['environment']['python']}, MNE {summary['environment']['packages']['mne']},
NumPy {summary['environment']['packages']['numpy']}, SciPy {summary['environment']['packages']['scipy']}.
"""
    rows = ["# FINDINGS: repaired ERP CORE Flankers case study", "", scope, "",
            "All three originally planned claims and all retained trials are reported.", ""]
    for claim in summary["claims"]:
        rows.extend([f"## {claim['claim_id']}: {claim['name']}", "",
                     f"- Incompatible: {claim['mean_a']:.6g} {claim['unit']}; compatible: {claim['mean_b']:.6g} {claim['unit']}.",
                     f"- Difference: {claim['diff']:.6g} {claim['unit']}; pooled Cohen's d: {claim['cohens_d']:.6g}.",
                     f"- Retained trials: {claim['n_per_condition']}.",
                     f"- Cluster p-values: {claim['cluster_p']}.",
                     f"- Result at cluster alpha 0.05/3: {claim['verdict']} ({claim['n_sig']} significant clusters).", ""])
    rows.extend(["## Scope", "", "Single participant; trial-level conditional inference only.",
                 "Historical results remain in the original project; this output does not change the v0.3.2 release.",
                 f"Run elapsed time: {summary['elapsed_seconds']:.3f} s for the scope stated above.", ""])
    report_dir = out / "report-stage"
    report_dir.mkdir(exist_ok=True)
    (report_dir / "methods.md").write_text(methods, encoding="utf-8")
    (out / "FINDINGS.md").write_text("\n".join(rows), encoding="utf-8")
    write_json(report_dir / "execution.json", {
        key: summary[key] for key in ("started_utc", "elapsed_seconds", "reuse_epochs", "environment", "inputs")})


def run(project: Path, out: Path, *, reuse_epochs: bool = False) -> dict:
    """Execute a new analysis without modifying its source project."""
    project, out = project.resolve(), out.resolve()
    if out == project or out in project.parents:
        raise ValueError("--out must be a new run directory, not the source project or its parent.")
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {out}")
    out.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    started = datetime.now(timezone.utc).isoformat()
    mne.set_log_level("WARNING")
    np.random.seed(SEED)
    raw_path = project / "raw/sub-01.fif"
    raw = mne.io.read_raw_fif(raw_path, preload=False, verbose=False)
    stimuli, responses, source_report = source_events(raw)
    if reuse_epochs:
        epoch_dir = project / "epoch-stage/sub-01"
        stim = mne.read_epochs(epoch_dir / "sub-01_stim-epo.fif", preload=True, verbose=False)
        resp = mne.read_epochs(epoch_dir / "sub-01_resp-epo.fif", preload=True, verbose=False)
        upstream = {"upstream_rerun": False, "epochs_source": str(epoch_dir),
                    "ica_summary_source": str(project / "ica-stage/sub-01/ica_summary.json")}
    else:
        stim, resp, upstream = build_epochs(out, raw, stimuli, responses)
    if not np.array_equal(stim.ch_names, resp.ch_names):
        raise ValueError("Stimulus and response epochs must have the same channel order.")
    roi_indices = [stim.ch_names.index(name) for name in ROI]
    roi_info = mne.pick_info(stim.info, roi_indices)
    spatial_adjacency, adjacency_names = mne.channels.find_ch_adjacency(roi_info, ch_type="eeg")
    order = [list(adjacency_names).index(name) for name in ROI]
    spatial_adjacency = spatial_adjacency.tocsr()[order][:, order]
    stim_metadata = trial_metadata(stim, stimuli, responses, raw.info["sfreq"], response_locked=False)
    resp_metadata = trial_metadata(resp, stimuli, responses, raw.info["sfreq"], response_locked=True)
    write_json(out / "input_trials.json", {"source": source_report,
                                            "stimulus": stim_metadata, "response": resp_metadata})
    stim_labels = np.asarray(stim_metadata["incompatible"], dtype=bool)
    resp_labels = np.asarray(resp_metadata["incompatible"], dtype=bool)
    stim_data, resp_data = stim.get_data(copy=False), resp.get_data(copy=False)
    plot = {"stim_times": stim.times, "resp_times": resp.times,
            "channel_names": np.asarray(stim.ch_names),
            "channel_pos_head_m": np.array([ch["loc"][:3] for ch in stim.info["chs"]]),
            "roi_names": np.asarray(ROI), "roi_indices": np.asarray(roi_indices)}
    claims = []
    for spec, data, epochs, metadata, labels, prefix in (
            (CLAIM_SPECS[0], stim_data, stim, stim_metadata, stim_labels, "stim"),
            (CLAIM_SPECS[1], resp_data, resp, resp_metadata, resp_labels, "resp")):
        mask = (epochs.times >= spec["window_s"][0]) & (epochs.times <= spec["window_s"][1])
        values = data[:, roi_indices][:, :, mask].transpose(0, 2, 1) * 1e6
        print(f"{spec['claim_id']}: {len(values)} trials, domain {values.shape[1:]}", flush=True)
        claims.append(run_claim(spec, values, metadata, epochs.times[mask],
                                spatial_adjacency, out, unit="uV"))
        plot[f"{prefix}_comp_uV"] = data[~labels].mean(axis=0) * 1e6
        plot[f"{prefix}_incomp_uV"] = data[labels].mean(axis=0) * 1e6
        plot[f"{prefix}_diff_uV"] = plot[f"{prefix}_incomp_uV"] - plot[f"{prefix}_comp_uV"]
    n2_mask = (stim.times >= 0.2) & (stim.times <= 0.35)
    plot["stim_topomap_uV"] = plot["stim_diff_uV"][:, n2_mask].mean(axis=1)
    plot["topomap_window_s"] = np.asarray(CLAIM_SPECS[0]["window_s"])

    # Morlet transforms are channel-wise; selecting the planned ROI retains
    # exactly its values without unnecessary full-head per-trial TFR storage.
    tfr = stim.copy().pick(ROI).compute_tfr(
        method="morlet", freqs=FREQUENCIES, n_cycles=FREQUENCIES / 3,
        return_itc=False, decim=4, average=False, output="power",
        use_fft=False, zero_mean=True, n_jobs=1, verbose=False)
    tfr.apply_baseline(baseline=(-0.2, 0), mode="logratio", verbose=False)
    tfr.data *= 10.0
    theta_mask = (tfr.freqs >= 4) & (tfr.freqs <= 8)
    tfr_mask = (tfr.times >= 0.2) & (tfr.times <= 0.5)
    c3_values = tfr.data[:, :, theta_mask][:, :, :, tfr_mask].transpose(0, 3, 2, 1)
    print(f"C3: {len(c3_values)} trials, domain {c3_values.shape[1:]}", flush=True)
    claims.append(run_claim(CLAIM_SPECS[2], c3_values, stim_metadata, tfr.times[tfr_mask],
                            spatial_adjacency, out, unit="dB", frequencies=tfr.freqs[theta_mask]))
    plot["tfr_times"], plot["tfr_freqs"] = tfr.times, tfr.freqs
    plot["tfr_comp_db"] = tfr.data[~stim_labels].mean(axis=0)
    plot["tfr_incomp_db"] = tfr.data[stim_labels].mean(axis=0)
    plot["tfr_diff_db"] = plot["tfr_incomp_db"] - plot["tfr_comp_db"]
    for condition in ("comp", "incomp", "diff"):
        plot[f"theta_{condition}_db"] = plot[f"tfr_{condition}_db"][:, theta_mask].mean(axis=(0, 1))
    del c3_values, tfr

    # Preserve the original epoch-level Welch PSD and condition averages.
    spectral = stim.compute_psd(method="welch", fmin=1, fmax=30, n_jobs=1, verbose=False)
    psd_data = spectral.get_data()[:, roi_indices]
    plot["psd_freqs"] = spectral.freqs
    plot["psd_comp"] = psd_data[~stim_labels].mean(axis=0)
    plot["psd_incomp"] = psd_data[stim_labels].mean(axis=0)
    plot["psd_comp_roi"] = plot["psd_comp"].mean(axis=0)
    plot["psd_incomp_roi"] = plot["psd_incomp"].mean(axis=0)
    spectral_summary = {}
    for band, (low, high) in {"theta": (4, 8), "alpha": (8, 13), "beta": (13, 30)}.items():
        mask = (spectral.freqs >= low) & (spectral.freqs <= high)
        comp = float(plot["psd_comp"][:, mask].mean())
        incomp = float(plot["psd_incomp"][:, mask].mean())
        spectral_summary[band] = {"compatible_power": comp, "incompatible_power": incomp,
                                   "incompatible_compatible_ratio": incomp / comp,
                                   "unit": "V^2/Hz", "freq_range_hz": [low, high]}
    np.savez_compressed(out / "plot_arrays.npz", **plot)
    environment = environment_record()
    summary = {
        "case": "flankers", "source_project": str(project), "output_directory": str(out),
        "started_utc": started, "reuse_epochs": reuse_epochs,
        "elapsed_seconds": time.perf_counter() - start,
        "runtime_scope": "cached-epochs downstream analysis" if reuse_epochs else "raw-FIF through downstream analysis",
        "environment": environment,
        "inputs": {"raw": str(raw_path.resolve()), **upstream,
                   "stimulus_shape": list(stim_data.shape), "response_shape": list(resp_data.shape),
                   "sfreq": stim.info["sfreq"], "trial_metadata_file": "input_trials.json"},
        "source_design": source_report,
        "inference_scope": "Single participant, retained trial-level conditional exchangeability within block × target side.",
        "claims": claims, "spectral_summary": spectral_summary,
        "tfr_spec": {"frequencies_hz": FREQUENCIES.tolist(), "n_cycles": "freqs/3",
                     "decim": 4, "baseline_s": [-0.2, 0.0], "unit": "dB",
                     "normalization": "10*log10(power/mean_baseline_power), each trial before averaging",
                     "zero_mean": True, "use_fft": False},
        "historical_outputs_untouched": True,
        "release_boundary": "New repair run, not part of immutable v0.3.2.",
    }
    write_json(out / "summary.json", summary)
    reports(summary, out)
    print(f"Completed {summary['runtime_scope']} in {summary['elapsed_seconds']:.3f} s: {out}", flush=True)
    return summary


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path("projects/erp-core-full"))
    parser.add_argument("--out", type=Path, required=True,
                        help="New or empty output directory; historical results are never overwritten.")
    parser.add_argument("--reuse-epochs", action="store_true",
                        help="Reuse source epochs and skip upstream preprocessing and ICA.")
    args = parser.parse_args(argv)
    run(args.project, args.out, reuse_epochs=args.reuse_epochs)


if __name__ == "__main__":
    main()
