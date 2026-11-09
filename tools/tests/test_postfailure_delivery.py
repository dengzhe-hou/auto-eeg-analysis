"""Observable regressions for order, frequency boundaries, output and review context."""
import json
from pathlib import Path
import runpy
import sys

import mne
import numpy as np
import pytest
from scipy.integrate import trapezoid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from check_analysis_outputs import check_outputs, write_outputs, result_from_report
from run_continuous_plan import run_plan
from prepare_analysis_review import semantic_review_prompt, image_review_prompt, plot_data_context

spectral = runpy.run_path(str(ROOT / "skills/eeg-spectral/scripts/continuous.py"))


def fir():
    return dict(method="fir", fir_design="firwin", fir_window="hamming", phase="zero",
                filter_length="auto", l_trans_bandwidth="auto", h_trans_bandwidth="auto",
                pad="reflect_limited")


@pytest.fixture
def raw():
    x = np.random.default_rng(58).normal(size=(4, 1200)) * 1e-6
    x[0, 195:200] += 10e-6
    return mne.io.RawArray(x, mne.create_info(["F3", "F4", "C3", "C4"], 100., "eeg"), verbose=False)


def gfp_plan(raw):
    return {"analysis_channels": raw.ch_names,
            "operations": [
                {"operation": "average_reference", "parameters": {"projection": False}},
                {"operation": "resample", "parameters": {"sfreq": 50.}},
                {"operation": "filter", "parameters": {**fir(), "l_freq": 1., "h_freq": 20.}},
                {"operation": "crop", "parameters": {"start_s": 2., "stop_s": 8.}}],
            "gfp_peaks": {"sfreq_hz": 50., "time_origin_s": 2., "windows_s": [[2., 5.], [5., 8.]],
                          "tie_rule": "first", "result_fields": ["peak_a", "peak_b"]},
            "evidence_interval_s": [2., 8.],
            "required_results": {"peak_a": "", "peak_b": ""},
            "required_evidence": {"channels": "", "gfp": "", "gfp_times": ""},
            "numeric_tolerance": {"signal": {"rtol": 1e-9, "atol": 1e-15}, "time_atol_s": 1e-9}}


def test_runner_preserves_processing_order_and_exports_actual_interval(raw, tmp_path):
    original = raw.get_data().copy()
    plan = gfp_plan(raw)
    final, checked = run_plan(plan, raw, tmp_path)
    manual = raw.copy().set_eeg_reference("average", projection=False, verbose=False)
    manual.resample(50., verbose=False).filter(1., 20., **fir(), verbose=False)
    expected = manual.get_data(start=100, stop=400).std(axis=0, ddof=0)
    with np.load(tmp_path / "analysis_evidence.npz") as arrays:
        np.testing.assert_allclose(arrays["gfp"], expected, rtol=1e-12, atol=1e-20)
        assert arrays["gfp"].shape == (300,)
        assert arrays["channels"].tolist() == raw.ch_names
        np.testing.assert_array_equal(arrays["gfp_times"], 2 + np.arange(300) / 50.)
    steps = final["analysis_metadata"]["processing_steps"]
    assert [step["operation"] for step in steps] == ["average_reference", "resample", "filter", "crop"]
    assert steps[1]["input_n_samples"] == 1200 and steps[1]["output_n_samples"] == 600
    assert steps[-1]["output_time_origin_s"] == 2.
    assert checked["coverage"]["approved_processing_recomputed"]
    assert json.loads((tmp_path / "FINAL_SUBMISSION.md").read_text(encoding="utf-8-sig")) == final
    np.testing.assert_array_equal(raw.get_data(), original)


def test_checker_rejects_full_buffer_saved_instead_of_requested_gfp(raw, tmp_path):
    plan = gfp_plan(raw)
    final, _ = run_plan(plan, raw, tmp_path)
    with np.load(tmp_path / "analysis_evidence.npz") as archive:
        arrays = {key: archive[key] for key in archive.files}
    arrays["gfp"] = np.tile(arrays["gfp"], 2)
    arrays["gfp_times"] = 2 + np.arange(600) / 50.
    write_outputs(final, arrays, tmp_path)
    checks = check_outputs(plan, tmp_path)
    assert not checks["passed"]
    assert not next(c["passed"] for c in checks["checks"] if c["name"] == "gfp.evidence_samples")


@pytest.mark.parametrize("explanation", [None, "", "   "])
def test_final_json_needs_its_own_explanation(tmp_path, explanation):
    saved = {"status": "computed", "explanation": "Computed from the selected channels.", "value": 1.}
    final = write_outputs(saved, {"channels": ["F3"]}, tmp_path)
    if explanation is None:
        final.pop("explanation")
    else:
        final["explanation"] = explanation
    plan = {"analysis_channels": ["F3"], "required_results": {"value": ""},
            "required_evidence": {"channels": ""}}
    checked = check_outputs(plan, tmp_path, final_result=final)
    assert not checked["passed"]
    assert not next(c["passed"] for c in checked["checks"] if c["name"] == "report_explanation_present")


def test_empty_channel_metadata_is_not_a_successful_delivery(tmp_path):
    write_outputs({"status": "computed", "explanation": "Actual single-channel calculation."},
                  {"channels": []}, tmp_path)
    plan = {"analysis_channels": ["F3"], "required_results": {}, "required_evidence": {"channels": ""}}
    assert not check_outputs(plan, tmp_path)["passed"]


def test_report_parser_does_not_move_prose_into_a_missing_json_field(tmp_path):
    final = 'Measured result.\n```json\n{"status":"computed","value":1}\n```\nExplanation: actual prose.'
    parsed = result_from_report(final)
    assert parsed == {"status": "computed", "value": 1}
    with pytest.raises(ValueError, match="JSON result"):
        result_from_report("No requested JSON object was delivered.")


def test_power_aggregation_is_explicit_and_can_reverse_the_dominant_band():
    f = np.array([1., 2., 3., 4.])
    p = np.array([[900., 900., 100., 100.], [0., 0., 10., 10.]]) * 1e-12
    bands = {"delta": {"band": [1., 2.], "upper_closed": True},
             "alpha": {"band": [3., 4.], "upper_closed": True}}
    absolute = spectral["band_power_summary"](p, f, bands=bands, power_kind="absolute",
        aggregation="mean_channel_power", total_band=None)
    relative = spectral["band_power_summary"](p, f, bands=bands, power_kind="relative",
        aggregation="mean_channel_ratios", total_band={"band": [1., 4.], "upper_closed": True})
    assert absolute["dominant_bands"] == ["delta"]
    assert relative["dominant_bands"] == ["alpha"]
    alpha = trapezoid(p[:, 2:], f[2:], axis=-1)
    total = trapezoid(p, f, axis=-1)
    np.testing.assert_allclose(relative["values"]["alpha"], np.mean(alpha / total))
    with pytest.raises(ValueError, match="aggregation"):
        spectral["band_power_summary"](p, f, bands=bands, power_kind="relative",
            aggregation=None, total_band={"band": [1., 4.], "upper_closed": True})


def test_inclusive_drift_boundary_retains_both_bins_and_wrong_rule_fails():
    f = np.arange(0., 1.25, .25)
    p = np.full((2, len(f)), 2e-12)
    bands = {"drift": {"band": [.1, .5], "upper_closed": True}}
    settings = dict(bands=bands, power_kind="relative", aggregation="mean_channel_ratios",
                    total_band={"band": [.1, 1.], "upper_closed": True})
    correct = spectral["band_power_summary"](p, f, **settings)
    assert correct["selected_frequencies_hz"]["drift"] == [.25, .5]
    np.testing.assert_allclose(correct["values"]["drift"], 1 / 3)
    with pytest.raises(ValueError, match="fewer than two"):
        spectral["band_power_summary"](p, f, **{**settings,
            "bands": {"drift": {"band": [.1, .5], "upper_closed": False}}})


def test_spectral_runner_recomputes_definition_and_rejects_false_null(raw, tmp_path):
    plan = {"analysis_channels": raw.ch_names, "operations": [],
            "welch": {"segment_seconds": 4., "window": "hamming", "overlap_fraction": .5,
                      "n_fft": "n_per_seg", "detrend": "constant", "average": "mean"},
            "band_power": {"bands": {"drift": {"band": [.1, .5], "upper_closed": True}},
                           "power_kind": "relative", "aggregation": "mean_channel_ratios",
                           "total_band": {"band": [.1, 45.], "upper_closed": True},
                           "result_fields": {"drift": "drift_ratio"}, "result_scale": 1.,
                           "classifications": [{"band": "drift", "result_field": "drift_level",
                              "levels": [{"upper_exclusive": .08, "label": "LOW"},
                                         {"upper_exclusive": .25, "label": "MEDIUM"},
                                         {"upper_exclusive": None, "label": "HIGH"}]}]},
            "required_results": {"drift_ratio": "", "drift_level": ""},
            "required_evidence": {"channels": "", "freqs": "", "psd": ""},
            "numeric_tolerance": {"psd": {"rtol": 1e-9, "atol": 1e-24},
                                  "result": {"rtol": 1e-9, "atol": 1e-12}, "frequency_atol_hz": 1e-9}}
    final, checked = run_plan(plan, raw, tmp_path)
    assert checked["coverage"]["band_power_recomputed"]
    assert checked["coverage"]["approved_processing_recomputed"]
    with np.load(tmp_path / "analysis_evidence.npz") as archive:
        evidence = {key: archive[key] for key in archive.files}
    final.update(status="limited_inference", drift_ratio=None, drift_level=None)
    write_outputs(final, evidence, tmp_path)
    assert not check_outputs(plan, tmp_path)["passed"]


def test_hilbert_runner_preserves_branches_and_reports_actual_hemisphere_signs(raw, tmp_path):
    plan = {"analysis_channels": raw.ch_names,
            "required_results": {"alpha_diff": "", "beta_diff": ""},
            "required_evidence": {"channels": "", "wpli_alpha": "", "wpli_beta": ""},
            "numeric_tolerance": {"connectivity": {"rtol": 1e-9, "atol": 1e-12},
                                  "result": {"rtol": 1e-9, "atol": 1e-12}},
            "hilbert_bands": {}, "hemisphere_contrasts": []}
    for label, bounds in [("alpha", (8., 13.)), ("beta", (13., 30.))]:
        plan["hilbert_bands"][label] = {"metric": "wpli", "matrix_key": "wpli_" + label,
            "operations": [{"operation": "crop", "parameters": {"start_s": 1., "stop_s": 7.}},
                           {"operation": "filter", "parameters": {**fir(), "l_freq": bounds[0], "h_freq": bounds[1]}}]}
        plan["hemisphere_contrasts"].append({"matrix_key": "wpli_" + label, "result_field": label + "_diff",
                                          "homologous_pairs": [["F3", "F4"], ["C3", "C4"]]})
    final, checked = run_plan(plan, raw, tmp_path)
    assert checked["coverage"]["hilbert_matrices_recomputed"] == ["alpha", "beta"]
    # The actual frozen independent references store undefined self-wPLI as 0;
    # all distinct-channel edges and hemisphere differences must still match.
    with np.load(tmp_path / "analysis_evidence.npz") as archive:
        evidence = {key: archive[key] for key in archive.files}
    for key in ("wpli_alpha", "wpli_beta"):
        np.fill_diagonal(evidence[key], 0.)
    write_outputs(final, evidence, tmp_path)
    assert check_outputs(plan, tmp_path, raw_input=raw)["passed"]
    for label in ["alpha", "beta"]:
        assert final["band_metadata"][label]["n_samples"] == 600
        assert [step["operation"] for step in final["band_metadata"][label]["processing_steps"]] == ["crop", "filter"]
        value = final[label + "_diff"]
        interpretation = "left higher" if value > 0 else "right higher" if value < 0 else "equal"
        assert f"{value:.12g} ({interpretation})" in final["explanation"]


def test_semantic_context_keeps_correct_interpretation_outside_json():
    contract = {"original_instruction": "Explain whether the hemispheric direction is consistent.",
                "sampling_rate_hz": 200., "input_n_samples": 12000, "analysis_channels": ["F3", "F4"]}
    direct = {"direct_pass": True, "expected_result": {"alpha_diff": -.13, "beta_diff": -.17},
              "reported_result": {"explanation": "Methods only."},
              "first_report_result": {"explanation": "Methods only."}}
    full = '{"explanation":"Methods only."}\nBoth bands are negative; right is higher in both.'
    prompt = semantic_review_prompt(contract, direct, full)
    payload = json.loads(prompt.split("\n", 1)[1])
    assert payload["final_submission"] == full
    assert payload["saved_explanation"] == "Methods only."
    with pytest.raises(ValueError, match="objective"):
        semantic_review_prompt(contract, {**direct, "direct_pass": False}, full)


def test_image_context_covers_channel_outlier_instead_of_only_the_mean():
    p = np.array([[1., 2., 3.], [100., 200., 300.]]) * 1e-12
    context = plot_data_context(np.array([1., 10., 50.]), p, ["F3", "F4"], sample_hz=[10., 50.])
    np.testing.assert_allclose(context["mean_psd"], [101e-12, 151.5e-12])
    np.testing.assert_allclose(context["maximum_channel_psd"], [200e-12, 300e-12])
    prompt = image_review_prompt({"original_instruction": "Plot both channel PSDs."},
                                {"direct_pass": True, "image_path": "actual.png"}, "Saved actual PSD.", context)
    assert json.loads(prompt.split("\n", 1)[1])["plot_data"] == context
