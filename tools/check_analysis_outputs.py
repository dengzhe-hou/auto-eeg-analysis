"""Check public-plan artifact structure and consistency without reference answers."""
import argparse
import json
from pathlib import Path
import re
import runpy
import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def result_from_report(text):
    """Read the actual final report's result object, keeping required fields intact."""
    decoder = json.JSONDecoder()
    for opening in re.finditer(r"\{", text):
        try:
            value, _ = decoder.raw_decode(text[opening.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "status" in value:
            return value
    raise ValueError("Final report lacks a JSON result object with status")


def _helper(skill):
    return runpy.run_path(str(ROOT / "skills" / skill / "scripts/continuous.py"))


def write_outputs(result, evidence, workspace):
    """Save computed values once; return the same JSON object for the final report."""
    def encode(value):
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, np.ndarray):
            return value.tolist()
        raise TypeError(f"Unsupported result value: {type(value).__name__}")
    text = json.dumps(result, default=encode, allow_nan=False, indent=2)
    arrays = {key: np.asarray(value) for key, value in evidence.items()}
    for key, value in arrays.items():
        if value.dtype.hasobject:
            if key == "channels" and all(isinstance(name, str) for name in value.flat):
                arrays[key] = value.astype(str)
            else:
                raise ValueError(f"Evidence {key!r} must be a numeric or string array, not objects")
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "result.json").write_text(text + "\n", encoding="utf-8")
    np.savez(workspace / "analysis_evidence.npz", **arrays)
    return json.loads(text)


def band_power_results(summary, settings):
    """Map approved band summaries to output fields without choosing a method."""
    results = {}
    for band, field in settings.get("result_fields", {}).items():
        results[field] = summary["values"][band] * settings["result_scale"]
    if "dominant_result" in settings:
        if len(summary["dominant_bands"]) != 1:
            raise ValueError("Dominant bands tie; resolve the reporting rule instead of selecting one")
        results[settings["dominant_result"]] = summary["dominant_bands"][0]
    for rule in settings.get("classifications", []):
        value = summary["values"][rule["band"]]
        for level in rule["levels"]:
            if level["upper_exclusive"] is None or value < level["upper_exclusive"]:
                results[rule["result_field"]] = level["label"]
                break
        else:
            raise ValueError("Approved classification levels do not cover the computed value")
    return results


def _numeric_match(actual, expected, tolerance):
    actual, expected = np.asarray(actual), np.asarray(expected)
    return (actual.shape == expected.shape and np.issubdtype(actual.dtype, np.number)
            and np.allclose(actual, expected, rtol=tolerance["rtol"],
                            atol=tolerance["atol"], equal_nan=True))


def _pair_labels(pairs):
    """Normalize the two documented pair representations, preserving rank."""
    if not isinstance(pairs, list):
        return None
    labels = []
    for pair in pairs:
        if isinstance(pair, dict):
            pair = pair.get("channel_pair")
        if not isinstance(pair, list) or len(pair) != 2 or not all(isinstance(name, str) for name in pair):
            return None
        labels.append(sorted(pair))
    return labels


def _evidence_in_si(evidence):
    """Honor explicitly labelled equivalent units; unlabeled arrays use SI."""
    evidence = dict(evidence)
    signal_scales = {"V": 1., "mV": 1e-3, "uV": 1e-6, "µV": 1e-6}
    power_scales = {"V^2/Hz": 1., "uV^2/Hz": 1e-12, "µV^2/Hz": 1e-12}
    variance_scales = {"V^2": 1., "uV^2": 1e-12, "µV^2": 1e-12}
    for keys, unit_key, default_unit, scales in [
        (("processed", "segment", "signal_V", "gfp"), "signal_unit", "V", signal_scales),
        (("psd", "psd_before", "psd_after"), "psd_unit", "V^2/Hz", power_scales),
        (("variance",), "variance_unit", "V^2", variance_scales),
    ]:
        unit = str(evidence.get(unit_key, default_unit))
        if unit not in scales:
            raise ValueError(f"Unsupported declared {unit_key}: {unit}")
        for key in keys:
            if key in evidence:
                evidence[key] = evidence[key] * scales[unit]
    return evidence


def check_outputs(plan, workspace, *, raw_input=None, final_result=None):
    """Check public outputs, optionally recomputing an explicit approved pipeline.

    raw_input is the unchanged MNE input, not a processed buffer. Recalculation
    needs approved operations (plus Welch settings for PSD), or explicit
    hilbert_bands branches, with quantity-specific numeric_tolerance values.
    It uses no benchmark reference outputs and is not independent certification.
    """
    workspace = Path(workspace)
    checks = []
    def add(name, passed):
        checks.append({"name": name, "passed": bool(passed)})
    result = json.loads((workspace / "result.json").read_text(encoding="utf-8-sig"))
    if not isinstance(result, dict):
        raise ValueError("result.json must contain an object")
    status = result.get("status")
    add("status", status in ("computed", "unavailable", "limited_inference"))
    add("explanation", isinstance(result.get("explanation"), str) and bool(result["explanation"].strip()))
    if final_result is not None:
        add("report_explanation_present", isinstance(final_result.get("explanation"), str)
            and bool(final_result["explanation"].strip()))
        for key, value in result.items():
            if key != "explanation":
                add("report_matches_file." + key, key in final_result and final_result[key] == value)
    for key in plan["required_results"]:
        add("result." + key, key in result or status == "unavailable" and key != "status")
    prepared = None
    hilbert_recomputed = []
    if raw_input is not None and status != "unavailable":
        if "operations" not in plan and not plan.get("hilbert_bands"):
            raise ValueError("Recomputation needs approved ordered operations (or hilbert_bands). Translate the approved procedure explicitly; a missing key does not mean no processing")
        if "numeric_tolerance" not in plan:
            raise ValueError("Recomputation needs numeric_tolerance from the approved plan; see docs/PRELOADED_SKILLS.md for the quantity-specific fields")
        if "operations" in plan:
            prepared = _helper("eeg-preprocess")["prepare_continuous"](
                raw_input, analysis_channels=plan["analysis_channels"], operations=plan["operations"])
    if status == "unavailable":
        for key in plan["required_results"]:
            if key not in ("status", "explanation", "file_path"):
                add("unavailable_no_invention." + key, result.get(key) is None)
    elif plan["required_evidence"]:
        with np.load(workspace / "analysis_evidence.npz", allow_pickle=False) as archive:
            evidence = _evidence_in_si({key: archive[key] for key in archive.files})
            names = plan["analysis_channels"]
            for key in plan["required_evidence"]:
                add("evidence." + key, key in evidence)
            if "channels" in evidence:
                add("channel_order", evidence["channels"].astype(str).tolist() == names)
                if "analysis_metadata" in result:
                    metadata = result["analysis_metadata"]
                    add("metadata.channels", metadata.get("channels") == evidence["channels"].astype(str).tolist())
                    add("metadata.n_channels", metadata.get("n_channels") == len(evidence["channels"]))
                    if "n_undirected_pairs" in metadata:
                        add("metadata.n_undirected_pairs", metadata["n_undirected_pairs"] == len(names) * (len(names) - 1) // 2)
                    for label, selected in metadata.get("roi_channels", {}).items():
                        add("metadata.roi." + label, all(name in names for name in selected))
                    if "roi_channels" in plan:
                        add("metadata.approved_rois", metadata.get("roi_channels") == plan["roi_channels"])
            if "freqs" in evidence:
                freqs = evidence["freqs"]
                valid_freqs = freqs.ndim == 1 and len(freqs) > 1 and np.all(np.diff(freqs) > 0)
                add("increasing_frequencies", valid_freqs)
                if "required_frequency_coverage_hz" in plan:
                    low, high = plan["required_frequency_coverage_hz"]
                    add("frequency_coverage", valid_freqs and freqs[0] <= low <= high <= freqs[-1])
                for key in ("psd", "psd_before", "psd_after"):
                    if key in evidence:
                        power = evidence[key]
                        add(key + ".shape", power.shape == (len(names), len(freqs)))
                        add(key + ".finite_nonnegative", np.isfinite(power).all() and np.all(power >= 0))
            for key in ("correlation", "plv", "wpli_alpha", "wpli_beta"):
                if key in evidence:
                    matrix = evidence[key]
                    shape = matrix.shape == (len(names), len(names))
                    add(key + ".shape", shape)
                    if shape:
                        mask = ~np.eye(len(names), dtype=bool)
                        add(key + ".symmetric", np.allclose(matrix[mask], matrix.T[mask], equal_nan=True))
                        limit = 1 + 1e-8
                        add(key + ".range", np.all(np.isnan(matrix[mask]) | (np.abs(matrix[mask]) <= limit)))
                        if key != "correlation":
                            add(key + ".nonnegative", np.all(np.isnan(matrix[mask]) | (matrix[mask] >= -1e-8)))
            if raw_input is not None and plan.get("hilbert_bands"):
                from scipy.signal import hilbert
                preprocessing = _helper("eeg-preprocess")
                connectivity = _helper("eeg-connectivity")
                if "connectivity" not in plan["numeric_tolerance"]:
                    raise ValueError("Hilbert matrix recomputation needs numeric_tolerance.connectivity with the approved dimensionless rtol and atol; a summary-result tolerance does not specify a matrix tolerance")
                tolerance = plan["numeric_tolerance"]["connectivity"]
                for label, branch in plan["hilbert_bands"].items():
                    with preprocessing["prepare_continuous"](
                            raw_input, analysis_channels=names,
                            operations=branch["operations"]) as selected:
                        signal = preprocessing["data_in_volts"](selected)
                        metadata = preprocessing["recording_metadata"](selected)
                    analytic = hilbert(signal, axis=-1)
                    if branch["metric"] == "plv":
                        expected = connectivity["plv_from_analytic"](analytic)
                    elif branch["metric"] == "wpli":
                        expected = connectivity["ordinary_wpli_from_analytic"](analytic)
                    else:
                        raise ValueError("Hilbert recomputation supports approved plv or ordinary wpli")
                    key = branch["matrix_key"]
                    actual = evidence.get(key)
                    shape_matches = actual is not None and actual.shape == expected.shape
                    if branch["metric"] == "wpli" and shape_matches:
                        # Self-wPLI is undefined. A 0/NaN storage placeholder
                        # cannot change any contracted distinct-channel value.
                        distinct = ~np.eye(len(names), dtype=bool)
                        matched = _numeric_match(actual[distinct], expected[distinct], tolerance)
                    else:
                        matched = shape_matches and _numeric_match(actual, expected, tolerance)
                    add("approved_hilbert." + label, matched)
                    if label in result.get("band_metadata", {}):
                        reported = result["band_metadata"][label]
                        for field in ("channels", "n_channels", "n_samples", "sfreq_hz"):
                            add("band_metadata." + label + "." + field,
                                reported.get(field) == metadata[field])
                    hilbert_recomputed.append(label)
            for summary in plan.get("connectivity_summaries", []):
                if summary["pair_scope"] != "undirected_distinct" or summary["ranking"] != "value_desc_label_asc":
                    raise ValueError("This summary check needs the approved undirected scope and value/label ranking")
                values = _helper("eeg-connectivity")["summarize_undirected_connectivity"](
                    evidence[summary["matrix_key"]], names, top_k=summary["top_k"])
                if "mean_result" in summary:
                    key = summary["mean_result"]
                    add("derived." + key, _numeric_match(result.get(key), values["global_mean"],
                        plan["numeric_tolerance"]["result"]))
                if "pairs_result" in summary:
                    key = summary["pairs_result"]
                    add("derived." + key, _pair_labels(result.get(key)) == values["top_pairs"])
            for contrast in plan.get("hemisphere_contrasts", []):
                value = _helper("eeg-connectivity")["hemisphere_difference"](
                    evidence[contrast["matrix_key"]], names,
                    homologous_pairs=contrast["homologous_pairs"])
                key = contrast["result_field"]
                add("derived." + key, _numeric_match(result.get(key), value,
                    plan["numeric_tolerance"]["result"]))
            if "gfp_peaks" in plan:
                settings = dict(plan["gfp_peaks"])
                fields = settings.pop("result_fields")
                if len(fields) != len(settings["windows_s"]):
                    raise ValueError("Each approved GFP window needs a result field")
                values = _helper("eeg-preprocess")["gfp_peak_times"](evidence["gfp"], **settings)
                tolerance = {"rtol": 0., "atol": plan["numeric_tolerance"]["time_atol_s"]}
                for key, peak in zip(fields, values["peak_times_s"]):
                    add("derived." + key, _numeric_match(result.get(key), peak, tolerance))
                if "gfp_times" in evidence:
                    add("derived.gfp_times", _numeric_match(evidence["gfp_times"], values["times_s"], tolerance))
                if prepared is not None:
                    add("gfp_peaks.sfreq", settings["sfreq_hz"] == prepared.info["sfreq"])
                if "evidence_interval_s" in plan:
                    start, stop = plan["evidence_interval_s"]
                    add("gfp.evidence_interval", settings["time_origin_s"] == start and stop > start)
                    expected_samples = round((stop - start) * settings["sfreq_hz"])
                    add("gfp.evidence_samples", evidence["gfp"].shape == (expected_samples,))
            if "processed" in evidence and "variance" in evidence:
                add("variance_matches_processed", np.allclose(
                    evidence["variance"], evidence["processed"].var(axis=-1, ddof=0), rtol=1e-6, atol=1e-24))
            if prepared is not None:
                tolerance = plan["numeric_tolerance"]
                data = _helper("eeg-preprocess")["data_in_volts"](prepared)
                for key in ("processed", "segment", "signal_V"):
                    if key in evidence:
                        add("approved_input." + key, _numeric_match(evidence[key], data, tolerance["signal"]))
                if "gfp" in evidence:
                    add("approved_input.gfp", _numeric_match(evidence["gfp"], data.std(axis=0, ddof=0), tolerance["signal"]))
                if "analysis_metadata" in result:
                    metadata = result["analysis_metadata"]
                    if "n_samples" in metadata:
                        add("metadata.n_samples", metadata["n_samples"] == prepared.n_times)
                    if "sfreq_hz" in metadata:
                        add("metadata.sfreq_hz", metadata["sfreq_hz"] == prepared.info["sfreq"])
                if "psd" in evidence:
                    expected_freqs, expected_psd = _helper("eeg-spectral")["welch_from_plan"](
                        data, prepared.info["sfreq"], plan=plan["welch"])
                    freqs = evidence["freqs"]
                    right = np.clip(np.searchsorted(expected_freqs, freqs), 0, len(expected_freqs) - 1)
                    left = np.maximum(right - 1, 0)
                    indices = np.where(abs(expected_freqs[left] - freqs) < abs(expected_freqs[right] - freqs), left, right)
                    grid = (len(freqs) > 1 and np.allclose(freqs, expected_freqs[indices], rtol=0,
                                                        atol=tolerance["frequency_atol_hz"]))
                    add("approved_psd.frequency_grid", grid)
                    add("approved_psd.values", grid and _numeric_match(
                        evidence["psd"], expected_psd[:, indices], tolerance["psd"]))
            if "band_power" in plan:
                settings = plan["band_power"]
                derived = _helper("eeg-spectral")["band_power_summary"](
                    evidence["psd"], evidence["freqs"],
                    **{key: settings[key] for key in ("bands", "power_kind", "aggregation", "total_band")})
                for key, expected in band_power_results(derived, settings).items():
                    got = result.get(key)
                    if isinstance(expected, str):
                        add("derived." + key, got == expected)
                    else:
                        add("derived." + key, _numeric_match(got, expected, plan["numeric_tolerance"]["result"]))
                if "band_power_definition" in result:
                    add("band_power.definition", result["band_power_definition"] == derived)
            if "personalized_alpha" in plan:
                settings = dict(plan["personalized_alpha"])
                peak_key = settings.pop("mean_peak_result")
                power_key = settings.pop("mean_percent_result")
                derived = _helper("eeg-spectral")["personalized_alpha_power"](
                    evidence["psd"], evidence["freqs"], **settings)
                tolerance = plan["numeric_tolerance"]["result"]
                add("derived." + peak_key, _numeric_match(result.get(peak_key), derived["mean_peak_hz"], tolerance))
                percentage = result.get(power_key)
                if result.get(power_key + "_unit") == "fraction" and isinstance(percentage, (int, float)):
                    percentage *= 100
                add("derived." + power_key, _numeric_match(
                    percentage, 100 * derived["relative_power_per_channel"].mean(), tolerance))
    if "output_filename" in plan and status != "unavailable":
        path = workspace / "file_check" / plan["output_filename"]
        add("requested_file", path.is_file())
        if path.is_file() and path.suffix.lower() == ".edf":
            sfreq = prepared.info["sfreq"] if prepared is not None else plan.get("output_sfreq_hz")
            samples = prepared.n_times if prepared is not None else plan.get("output_n_samples")
            for key, passed in _helper("eeg-preprocess")["check_edf"](
                    path, analysis_channels=plan["analysis_channels"], sfreq=sfreq, n_samples=samples).items():
                add(key, passed)
    return {"passed": all(c["passed"] for c in checks), "checks": checks,
            "scope": "Public-plan checks and selected recomputations; not independent numerical certification.",
            "coverage": {"structure_and_internal_consistency": True,
                      "approved_processing_recomputed": prepared is not None,
                      "hilbert_matrices_recomputed": hilbert_recomputed,
                      "report_values_compared": final_result is not None,
                      "personalized_power_recomputed": "personalized_alpha" in plan and status != "unavailable",
                      "connectivity_summary_recomputed": bool(plan.get("connectivity_summaries")) and status != "unavailable" and bool(plan["required_evidence"]),
                      "hemisphere_contrast_recomputed": bool(plan.get("hemisphere_contrasts")) and status != "unavailable" and bool(plan["required_evidence"]),
                      "gfp_peaks_recomputed": "gfp_peaks" in plan and status != "unavailable" and bool(plan["required_evidence"]),
                      "band_power_recomputed": "band_power" in plan and status != "unavailable" and bool(plan["required_evidence"]),
                      "independent_certification": False}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-input", type=Path, help="Unchanged input for approved operations or Hilbert branches")
    parser.add_argument("--report", type=Path, help="Actual final report containing its JSON result object")
    args = parser.parse_args()
    raw = None
    if args.raw_input:
        import mne
        raw = mne.io.read_raw(args.raw_input, preload=False, verbose=False)
    report = result_from_report(args.report.read_text(encoding="utf-8-sig")) if args.report else None
    try:
        result = check_outputs(json.loads(args.plan.read_text(encoding="utf-8-sig")), args.workspace, raw_input=raw, final_result=report)
    finally:
        if raw is not None:
            raw.close()
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
