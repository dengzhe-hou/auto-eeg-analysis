"""Report conformance checks must reject concrete result/statement mistakes.

Synthetic retained outputs isolate the renderer contract. They are not EEG
effect-validation experiments and do not test the permutation algorithm.
"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
from scipy import stats

pytest.importorskip("jsonschema", reason="Optional structured-report validator; present in the pinned environment")

TOOL = Path(__file__).resolve().parents[1] / "render_statistical_report.py"
SPEC = importlib.util.spec_from_file_location("render_statistical_report", TOOL)
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)


@pytest.fixture
def inputs():
    # Participant amplitudes have analytic mean .25 uV and sample SD 2 uV.
    amplitudes = np.array([-3., -2., -1., 0., 0., 1., 2., 3.]) + .25
    data = np.broadcast_to(amplitudes[:, None, None], (8, 3, 2)).copy() * 1e-6
    negative = np.full_like(data, .4e-6)
    ids = [f"p{i}" for i in range(8)]
    sem = 2 / np.sqrt(8)
    ci = [.25 - stats.t.ppf(.975, 7) * sem, .25 + stats.t.ppf(.975, 7) * sem]
    contract = {
        "report_type": "one_sample_erp_cluster", "observation_unit": "participant",
        "test": "spatio_temporal_cluster_1samp_test", "summary": "arithmetic_mean",
        "descriptive_ci": {"method": "student_t", "level": .95, "sidedness": "two-sided"},
        "cohort": ids + ["excluded"], "contrast": ["condition_a", "condition_b"],
        "roi_channels": ["Fz", "Cz"], "window_s": [.3, .5], "input_unit": "V",
        "input_sfreq": 10., "epoch_time_origin_s": -.2,
        "tail": 1, "cluster_forming_alpha": .05, "cluster_alpha": .05,
        "n_permutations_requested": 128, "seed": 7,
    }
    results = {
        "test_target": "cluster", "contrast": contract["contrast"],
        "roi_channels": contract["roi_channels"], "window_s": contract["window_s"],
        "input_unit": "V", "amplitude_unit": "uV", "tail": 1,
        "cluster_forming_alpha": .05, "cluster_alpha": .05,
        "threshold": float(stats.t.ppf(.95, 7)), "n_permutations_requested": 128,
        "n_permutations_actual": 128, "seed": 7, "participant_ids": ids,
        "excluded_participants": {"excluded": "Below the approved retained-trial minimum"},
        "roi_mean_uv": .25, "roi_sd_uv": 2., "roi_sem_uv": sem,
        "roi_ci95_uv": ci, "cluster_p_values": [1/128],
    }
    arrays = {"data": data, "positive": data+negative, "negative": negative,
              "participant_ids": np.asarray(ids), "times": np.array([.3, .4, .5]),
              "ch_names": np.asarray(contract["roi_channels"]),
              "contrast": np.asarray(contract["contrast"]), "unit": np.asarray("V"),
              "cluster_p": np.array([1/128]), "H0": np.linspace(-3, 3, 128)}
    return contract, results, arrays


def test_descriptive_interval_can_cross_zero_with_a_significant_cluster(inputs):
    statement = report.build_statement(*inputs)
    assert statement["roi_mean_uv"] == pytest.approx(.25)
    assert statement["roi_sd_uv"] == pytest.approx(2.)
    assert statement["roi_ci_excludes_zero"] is False
    assert statement["significant_cluster_indices"] == [0]
    assert statement["scalar_roi_inference"] == "not_performed"
    report.check_report(report.render_statement(statement).encode("utf-8"), statement)


def test_rejects_cluster_probability_presented_as_scalar_inference(inputs):
    contract, results, arrays = inputs
    results["test_target"] = "scalar_roi_mean"
    with pytest.raises(report.ReportValidationError):
        report.build_statement(contract, results, arrays)


@pytest.mark.parametrize("mutation", ["label", "scale"])
def test_rejects_wrong_unit_label_or_coherent_but_rescaled_summary(inputs, mutation):
    contract, results, arrays = inputs
    if mutation == "label":
        results["amplitude_unit"] = "V"
    else:
        for key in ["roi_mean_uv", "roi_sd_uv", "roi_sem_uv"]:
            results[key] *= 1e6
        results["roi_ci95_uv"] = [value*1e6 for value in results["roi_ci95_uv"]]
    with pytest.raises(report.ReportValidationError):
        report.build_statement(contract, results, arrays)


def test_rejects_reversed_difference_even_if_result_numbers_are_changed_together(inputs):
    contract, results, arrays = inputs
    arrays["data"] = -arrays["data"]
    results["roi_mean_uv"] *= -1
    results["roi_ci95_uv"] = [-value for value in results["roi_ci95_uv"]][::-1]
    with pytest.raises(report.ReportValidationError):
        report.build_statement(contract, results, arrays)


def test_extra_free_text_in_checked_section_is_not_accepted(inputs):
    statement = report.build_statement(*inputs)
    actual = report.render_statement(statement).encode("utf-8")
    actual += b"\nThe full scalar ROI mean is significant because its cluster is significant.\n"
    with pytest.raises(report.ReportValidationError):
        report.check_report(actual, statement)


def test_rejects_shortened_window_even_when_all_recorded_summaries_still_agree(inputs):
    contract, results, arrays = inputs
    # Every time sample has the same value in this fixture, so all means, SDs,
    # SEMs, intervals and cluster records still agree after this truncation.
    for key in ["data", "positive", "negative"]:
        arrays[key] = arrays[key][:, 1:, :]
    arrays["times"] = arrays["times"][1:]
    with pytest.raises(report.ReportValidationError):
        report.build_statement(contract, results, arrays)


@pytest.mark.parametrize("change", [{"summary": "trimmed_mean"}, {"tail": 0},
                                    {"test": "ttest_ind"},
                                    {"descriptive_ci": {"method": "bootstrap", "level": .95, "sidedness": "two-sided"}}])
def test_unsupported_approved_methods_fail_without_substitution(inputs, change):
    contract, results, arrays = inputs
    contract.update(change)
    with pytest.raises(report.UnsupportedReport):
        report.build_statement(contract, results, arrays)


def test_zero_clusters_and_empty_null_are_reportable_without_inventing_significance(inputs):
    contract, results, arrays = inputs
    arrays["cluster_p"], arrays["H0"] = np.array([]), np.array([])
    results["cluster_p_values"], results["n_permutations_actual"] = [], 0
    statement = report.build_statement(contract, results, arrays)
    assert statement["cluster_p_values"] == []
    assert statement["significant_cluster_indices"] == []
    assert statement["n_permutations_actual"] == 0
    report.check_report(report.render_statement(statement).encode(), statement)


def test_cli_writes_receipt_and_detects_changed_exported_section(inputs, tmp_path):
    contract, results, arrays = inputs
    (tmp_path / "contract.json").write_text(json.dumps(contract), encoding="utf-8")
    (tmp_path / "results.json").write_text(json.dumps(results), encoding="utf-8")
    np.savez(tmp_path / "arrays.npz", **arrays)
    command = [sys.executable, str(TOOL), "--contract", str(tmp_path / "contract.json"),
               "--results", str(tmp_path / "results.json"), "--arrays", str(tmp_path / "arrays.npz")]
    good = subprocess.run(command + ["--output-dir", str(tmp_path / "good")], capture_output=True, text=True)
    assert good.returncode == 0, good.stderr + good.stdout
    assert json.loads((tmp_path / "good/REPORT_CHECK.json").read_text(encoding="utf-8-sig"))["passed"] is True
    wrong = tmp_path / "wrong.md"
    wrong.write_bytes((tmp_path / "good/RESULTS.md").read_bytes() + b"\nAn unsupported extra inference.\n")
    bad = subprocess.run(command + ["--report", str(wrong), "--output-dir", str(tmp_path / "bad")], capture_output=True, text=True)
    assert bad.returncode == 1
    receipt = json.loads((tmp_path / "bad/REPORT_CHECK.json").read_text(encoding="utf-8-sig"))
    assert receipt["passed"] is False and receipt["error_type"] == "ReportValidationError"
