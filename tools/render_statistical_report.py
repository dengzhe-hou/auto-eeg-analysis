"""Opt-in, deterministic result section for approved one-sample ERP clusters.

Read the contract/result JSON format in tools/erp_cluster_report.schema.json.
The NPZ must retain data, positive, negative (participant x time x channel, V),
participant_ids, times (s), ch_names, contrast, unit, cluster_p and H0.
All three data arrays use the same approved ROI/window and participant ordering.
The contract's input_sfreq and epoch_time_origin_s must come from independently
checked complete source epoch/evoked metadata, not from the cropped report arrays.

The utility recomputes the descriptive summary from arrays and checks recorded
values before rendering. It checks report/result agreement, not the underlying
biological interpretation, artifact decisions or permutation implementation.
Other designs, estimators, intervals and two-sided tests remain unsupported here;
do not change an approved analysis to use this renderer.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import jsonschema
import numpy as np
from scipy import stats

SCHEMA = Path(__file__).with_name("erp_cluster_report.schema.json")
RTOL = ATOL = 1e-12


class ReportValidationError(ValueError):
    """A declared result or actual text disagrees with its source inputs."""


class UnsupportedReport(ValueError):
    """The approved analysis is outside this renderer's implemented scope."""


def _require(condition, message):
    if not condition:
        raise ReportValidationError(message)


def _same_number(actual, expected, field):
    _require(np.allclose(actual, expected, rtol=RTOL, atol=ATOL),
             f"{field} disagrees with source arrays: {actual!r} versus {expected!r}")


def build_statement(contract, results, arrays):
    """Validate declared outputs against retained arrays and return render fields."""
    supported = {"report_type": "one_sample_erp_cluster", "observation_unit": "participant",
                 "test": "spatio_temporal_cluster_1samp_test", "summary": "arithmetic_mean"}
    for key, expected in supported.items():
        if key in contract and contract[key] != expected:
            raise UnsupportedReport(f"Unsupported {key}={contract[key]!r}; supported: {expected!r}")
    if "tail" in contract and contract["tail"] not in (-1, 1):
        raise UnsupportedReport("Only one-sided ERP cluster reports are implemented; preserve the approved tail.")
    interval = {"method": "student_t", "level": .95, "sidedness": "two-sided"}
    if "descriptive_ci" in contract and contract["descriptive_ci"] != interval:
        raise UnsupportedReport("Only the explicitly approved descriptive two-sided 95% Student t interval is implemented.")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8-sig"))
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(
        {"contract": contract, "results": results}), key=lambda error: str(list(error.absolute_path)))
    if errors:
        raise ReportValidationError("; ".join(
            f"{'.'.join(map(str, error.absolute_path))}: {error.message}" for error in errors))
    for key in ("contrast", "roi_channels", "window_s", "input_unit", "tail",
                "cluster_forming_alpha", "cluster_alpha", "n_permutations_requested", "seed"):
        _require(results[key] == contract[key], f"results.{key} differs from the approved contract")

    data, positive, negative = [np.asarray(arrays[key]) for key in ("data", "positive", "negative")]
    ids = np.asarray(arrays["participant_ids"]).astype(str).tolist()
    times = np.asarray(arrays["times"])
    channels = np.asarray(arrays["ch_names"]).astype(str).tolist()
    _require(data.ndim == 3 and data.shape == positive.shape == negative.shape,
             "data/positive/negative must share participant x time x channel shape")
    _require(data.shape == (len(ids), len(times), len(channels)), "array coordinates do not match data shape")
    _require(len(ids) >= 2 and len(ids) == len(set(ids)), "participant identifiers must be unique with N>=2")
    _require(ids == results["participant_ids"], "participant ordering differs from the result record")
    excluded = results["excluded_participants"]
    _require(not set(ids).intersection(excluded) and set(ids).union(excluded) == set(contract["cohort"]),
             "included participants and explicit exclusions must account for the approved cohort")
    _require(channels == contract["roi_channels"], "array channels differ from the approved ROI/order")
    _require(np.asarray(arrays["contrast"]).astype(str).tolist() == contract["contrast"],
             "array contrast differs from the approved positive-minus-negative contrast")
    _require(np.asarray(arrays["unit"]).item() == "V", "input arrays must explicitly declare V")
    start, stop = contract["window_s"]
    _require(start <= stop, "approved measurement window is reversed")
    sfreq, origin = contract["input_sfreq"], contract["epoch_time_origin_s"]
    # A 1e-12 s allowance handles the arithmetic representation of a grid edge;
    # it does not permit an omitted boundary sample or a changed sampling rate.
    first = int(np.ceil((start-origin-ATOL)*sfreq))
    last = int(np.floor((stop-origin+ATOL)*sfreq))
    expected_times = origin + np.arange(first, last+1)/sfreq
    _require(len(expected_times) > 0 and times.shape == expected_times.shape
             and np.allclose(times, expected_times, rtol=0, atol=ATOL),
             "input times do not match the complete approved-window grid from source metadata")
    _same_number(data, positive-negative, "positive-minus-negative contrast array")
    amplitudes = data.mean(axis=(1, 2)) * 1e6
    mean, sd = float(amplitudes.mean()), float(amplitudes.std(ddof=1))
    sem = sd / np.sqrt(len(ids))
    # A zero sample SD is a valid descriptive interval of zero width.
    ci = [mean, mean] if sem == 0 else list(stats.t.interval(.95, len(ids)-1, loc=mean, scale=sem))
    for key, expected in {"roi_mean_uv": mean, "roi_sd_uv": sd, "roi_sem_uv": sem,
                          "roi_ci95_uv": ci}.items():
        _same_number(results[key], expected, key)
    tail = contract["tail"]
    threshold = tail * stats.t.ppf(1-contract["cluster_forming_alpha"], len(ids)-1)
    _same_number(results["threshold"], threshold, "cluster-forming threshold")
    p_values = np.asarray(arrays["cluster_p"])
    _require(p_values.ndim == 1 and np.all(np.isfinite(p_values))
             and np.all((p_values >= 0) & (p_values <= 1)), "cluster_p must be a one-dimensional probability vector")
    _require(np.array_equal(p_values, results["cluster_p_values"]), "recorded cluster p values differ from saved arrays")
    _require(len(arrays["H0"]) == results["n_permutations_actual"], "actual permutation count differs from saved H0")
    significant = np.flatnonzero(p_values < contract["cluster_alpha"]).tolist()
    return {"report_type": contract["report_type"], "test": contract["test"],
            "contrast": contract["contrast"], "roi_channels": channels, "window_s": [start, stop],
            "participant_ids": ids, "excluded_participants": excluded,
            "n_participants": len(ids), "amplitude_unit": "uV", "roi_mean_uv": mean,
            "roi_sd_uv": sd, "roi_sem_uv": float(sem), "descriptive_roi_ci95_uv": ci,
            "estimate_direction": "positive" if mean > 0 else "negative" if mean < 0 else "zero",
            "roi_ci_excludes_zero": bool(ci[0] > 0 or ci[1] < 0), "test_target": "cluster",
            "tail": tail, "threshold": float(threshold),
            "cluster_forming_alpha": contract["cluster_forming_alpha"],
            "cluster_alpha": contract["cluster_alpha"],
            "n_permutations_requested": contract["n_permutations_requested"],
            "n_permutations_actual": results["n_permutations_actual"], "seed": contract["seed"],
            "cluster_p_values": p_values.tolist(), "significant_cluster_indices": significant,
            "scalar_roi_inference": "not_performed"}


def render_statement(result):
    """Render only the bounded numerical result section, not a claim verdict."""
    number = lambda value: format(value, ".12g")
    positive, negative = result["contrast"]
    lower, upper = result["descriptive_roi_ci95_uv"]
    start, stop = [number(value*1000) for value in result["window_s"]]
    p_values = ", ".join(number(value) for value in result["cluster_p_values"]) or "none"
    indices = ", ".join(map(str, result["significant_cluster_indices"])) or "none"
    zero = "excludes zero" if result["roi_ci_excludes_zero"] else "includes zero"
    tail = "positive" if result["tail"] == 1 else "negative"
    exclusions = "; ".join(f"{sid}: {reason}" for sid, reason in result["excluded_participants"].items()) or "none"
    return (
        "# Statistical result section\n\n"
        f"Contrast: {positive} minus {negative}. Included participants: {result['n_participants']}. "
        f"Explicit exclusions: {exclusions}. ROI: {', '.join(result['roi_channels'])}. "
        f"Inclusive measurement window: {start} to {stop} ms.\n\n"
        f"The equally weighted participant-mean ROI contrast was {number(result['roi_mean_uv'])} uV "
        f"({result['estimate_direction']}; sample SD {number(result['roi_sd_uv'])} uV; "
        f"SEM {number(result['roi_sem_uv'])} uV, ddof=1). The descriptive two-sided 95% Student t interval "
        f"was [{number(lower)}, {number(upper)}] uV and {zero}.\n\n"
        f"The approved hypothesis test was a {tail}-tailed one-sample spatiotemporal cluster-permutation test "
        f"with forming threshold {number(result['threshold'])}, forming alpha "
        f"{number(result['cluster_forming_alpha'])} and cluster-level alpha {number(result['cluster_alpha'])}. "
        f"Requested permutations: {result['n_permutations_requested']}; actual saved null values: "
        f"{result['n_permutations_actual']}; seed: {result['seed']}. Cluster-corrected p values "
        f"(stored order): {p_values}. Significant cluster indices (zero-based): {indices}.\n\n"
        "The hypothesis-test result concerns clusters. No separate confirmatory test of the full "
        "ROI-window scalar mean was performed in this result section; its interval is descriptive. "
        "Cluster significance does not establish separate significance of every channel or time sample.\n"
    )


def check_report(actual, statement):
    _require(actual == render_statement(statement).encode("utf-8"),
             "actual result section differs from the deterministic UTF-8 rendering")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--arrays", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, help="Check an existing bounded result section instead of writing RESULTS.md.")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    receipt = {"contract": str(args.contract), "results": str(args.results), "arrays": str(args.arrays),
               "scope": "Bounded report/result agreement; no biological-truth, upstream-pipeline or general prose certification."}
    try:
        contract = json.loads(args.contract.read_text(encoding="utf-8-sig"))
        results = json.loads(args.results.read_text(encoding="utf-8-sig"))
        with np.load(args.arrays, allow_pickle=False) as data:
            arrays = {key: data[key] for key in data.files}
        statement = build_statement(contract, results, arrays)
        receipt["time_reference"] = {"input_sfreq": contract["input_sfreq"],
                                     "epoch_time_origin_s": contract["epoch_time_origin_s"],
                                     "window_s": contract["window_s"],
                                     "requirement": "Source metadata independently checked before ROI/window cropping."}
        expected = render_statement(statement)
        (args.output_dir / "RESULT_STATEMENT.json").write_text(json.dumps(statement, indent=2, allow_nan=False)+"\n", encoding="utf-8")
        (args.output_dir / "EXPECTED_RESULTS.md").write_text(expected, encoding="utf-8")
        actual = args.report or args.output_dir / "RESULTS.md"
        if args.report is None:
            actual.write_text(expected, encoding="utf-8")
        check_report(actual.read_bytes(), statement)
        receipt.update(passed=True, report=str(actual))
    except (ReportValidationError, UnsupportedReport) as error:
        receipt.update(passed=False, error_type=type(error).__name__, error=str(error))
    (args.output_dir / "REPORT_CHECK.json").write_text(json.dumps(receipt, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(receipt))
    return int(not receipt["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
