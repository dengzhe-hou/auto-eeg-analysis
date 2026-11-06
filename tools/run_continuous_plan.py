"""Execute approved continuous GFP, band-power or Hilbert steps and check delivery."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import runpy
import shutil
import socket
import sys

import mne
import numpy as np
from scipy.signal import hilbert

from check_analysis_outputs import band_power_results, check_outputs, write_outputs
from replay import write_json


ROOT = Path(__file__).resolve().parents[1]


def _compute_plan(plan, original_raw, output_directory, execution):
    """Use resolved settings only; preserve failed artifacts and do not repair a plan.

    operations is ordered, including the final crop if the exported interval is
    narrower than the processing buffer. Input and numeric tolerances come from
    the researcher-approved plan. This shared-helper check is not certification.
    """
    preprocessing = runpy.run_path(str(ROOT / "skills/eeg-preprocess/scripts/continuous.py"))
    spectral = runpy.run_path(str(ROOT / "skills/eeg-spectral/scripts/continuous.py"))
    connectivity = runpy.run_path(str(ROOT / "skills/eeg-connectivity/scripts/continuous.py"))
    result = {"status": "computed"}
    evidence = {}
    descriptions = []

    def stage(name):
        now = datetime.now(timezone.utc).isoformat()
        if execution['steps']:
            execution['steps'][-1].update(status='completed', finished_at=now)
        execution['steps'].append({'name': name, 'status': 'running', 'started_at': now})
        write_json(Path(output_directory) / 'execution.json', execution)

    def prepare(operations):
        history = []
        selected = preprocessing["prepare_continuous"](
            original_raw, analysis_channels=plan["analysis_channels"],
            operations=operations, operation_log=history)
        metadata = preprocessing["recording_metadata"](selected)
        metadata["processing_steps"] = history
        metadata["time_origin_s"] = history[-1]["output_time_origin_s"] if history else 0.0
        evidence["channels"] = metadata["channels"]
        return selected, metadata

    if "hilbert_bands" in plan:
        result["band_metadata"] = {}
        differences = {}
        for label, branch in plan["hilbert_bands"].items():
            stage('prepare:' + label)
            selected, metadata = prepare(branch["operations"])
            stage('compute:' + label)
            with selected:
                signal = preprocessing["data_in_volts"](selected)
            analytic = hilbert(signal, axis=-1)
            if branch["metric"] == "plv":
                matrix = connectivity["plv_from_analytic"](analytic)
            elif branch["metric"] == "wpli":
                matrix = connectivity["ordinary_wpli_from_analytic"](analytic)
            else:
                raise ValueError("Use the approved procedure for this Hilbert estimator")
            evidence[branch["matrix_key"]] = matrix
            if "segment_key" in branch:
                evidence[branch["segment_key"]] = signal
            result["band_metadata"][label] = metadata
            descriptions.append(f"{label}: {branch['metric']}, {metadata['n_channels']} channels, "
                                f"{metadata['n_samples']} samples at {metadata['sfreq_hz']} Hz")
            for summary in plan.get("connectivity_summaries", []):
                if summary["matrix_key"] != branch["matrix_key"]:
                    continue
                if summary["pair_scope"] != "undirected_distinct" or summary["ranking"] != "value_desc_label_asc":
                    raise ValueError("Use the approved connectivity scope and ranking procedure")
                computed = connectivity["summarize_undirected_connectivity"](
                    matrix, metadata["channels"], top_k=summary["top_k"])
                if "mean_result" in summary:
                    result[summary["mean_result"]] = computed["global_mean"]
                if "pairs_result" in summary:
                    result[summary["pairs_result"]] = computed["top_pairs"]
            for contrast in plan.get("hemisphere_contrasts", []):
                if contrast["matrix_key"] != branch["matrix_key"]:
                    continue
                value = connectivity["hemisphere_difference"](
                    matrix, metadata["channels"], homologous_pairs=contrast["homologous_pairs"])
                result[contrast["result_field"]] = value
                differences[label] = value
                side = "left higher" if value > 0 else "right higher" if value < 0 else "equal"
                descriptions.append(f"{label} left-minus-right within-hemisphere mean: {value:.12g} ({side})")
            # Preserve completed bands even if a later approved branch fails.
            write_outputs({**result, 'status': 'incomplete',
                           'explanation': '; '.join(descriptions) + '.'}, evidence, output_directory)
        if len(differences) > 1:
            signs = set(np.sign(value) for value in differences.values())
            pattern = ("all differences are zero" if signs == {0} else
                       "the hemispheric direction is consistent across bands" if len(signs) == 1 else
                       "the hemispheric direction is not the same across all bands")
            descriptions.append(pattern)
    else:
        stage('prepare')
        selected, metadata = prepare(plan["operations"])
        stage('compute')
        with selected:
            data = preprocessing["data_in_volts"](selected)
        result["analysis_metadata"] = metadata
        descriptions.append(f"{metadata['n_channels']} channels, {metadata['n_samples']} output samples "
                            f"at {metadata['sfreq_hz']} Hz; approved operations in recorded order")
        if "gfp_peaks" in plan:
            settings = dict(plan["gfp_peaks"])
            fields = settings.pop("result_fields")
            if metadata["time_origin_s"] != settings["time_origin_s"]:
                raise ValueError("GFP time origin does not match the actually prepared buffer")
            if metadata["sfreq_hz"] != settings["sfreq_hz"]:
                raise ValueError("GFP sampling rate does not match the actually prepared buffer")
            values = preprocessing["gfp_peak_times"](data.std(axis=0, ddof=0), **settings)
            if len(fields) != len(values["peak_times_s"]):
                raise ValueError("Each approved GFP window needs a result field")
            result.update(zip(fields, values["peak_times_s"]))
            evidence.update(gfp=data.std(axis=0, ddof=0), gfp_times=values["times_s"])
            descriptions.append("Population-SD GFP; absolute peak times (s): "
                                + ", ".join(str(value) for value in values["peak_times_s"]))
        elif "welch" in plan:
            freqs, psd = spectral["welch_from_plan"](data, metadata["sfreq_hz"], plan=plan["welch"])
            evidence.update(freqs=freqs, psd=psd)
            if "band_power" in plan:
                settings = plan["band_power"]
                summary = spectral["band_power_summary"](psd, freqs,
                    **{key: settings[key] for key in ("bands", "power_kind", "aggregation", "total_band")})
                result.update(band_power_results(summary, settings))
                result["band_power_definition"] = summary
                descriptions.append(f"{summary['power_kind']} power, {summary['aggregation']}: "
                                    + json.dumps(summary["values"]))
        else:
            raise ValueError("Supply the approved GFP, Welch or Hilbert analysis")
    result["explanation"] = "; ".join(descriptions) + "."
    stage('save_outputs')
    final_result = write_outputs(result, evidence, output_directory)
    stage('check_outputs')
    checked = check_outputs(plan, output_directory, raw_input=original_raw, final_result=final_result)
    output = Path(output_directory)
    (output / "SELF_CHECK.json").write_text(json.dumps(checked, indent=2) + "\n")
    if not checked["passed"]:
        raise ValueError("Delivery check failed; retain SELF_CHECK.json and the actual artifacts")
    stage('write_final_submission')
    (output / "FINAL_SUBMISSION.md").write_text(json.dumps(final_result, indent=2) + "\n")
    return final_result, checked


def run_plan(plan, original_raw, output_directory):
    """Execute once in a new directory, retaining code, progress and failed output."""
    output = Path(output_directory)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Choose a new run directory; existing outputs are preserved: {output}")
    output.mkdir(parents=True, exist_ok=True)
    execution = {
        'status': 'running', 'started_at': datetime.now(timezone.utc).isoformat(),
        'hostname': socket.gethostname(), 'coordinator_pid': os.getpid(), 'steps': [],
        'input_metadata': {
            'channels': list(original_raw.ch_names), 'channel_types': original_raw.get_channel_types(),
            'sfreq_hz': float(original_raw.info['sfreq']), 'n_samples': int(original_raw.n_times),
            'filenames': [str(path) for path in original_raw.filenames if path is not None]},
        'python': sys.version, 'mne': mne.__version__, 'numpy': np.__version__,
        'source_files': ['tools/run_continuous_plan.py', 'tools/check_analysis_outputs.py',
                         'tools/replay.py', 'skills/eeg-preprocess/scripts/continuous.py',
                         'skills/eeg-spectral/scripts/continuous.py',
                         'skills/eeg-connectivity/scripts/continuous.py'],
    }
    write_json(output / 'execution.json', execution)
    try:
        write_json(output / 'APPROVED_PLAN.json', plan)
        for relative in execution['source_files']:
            destination = output / 'executed-source' / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
        final_result, checked = _compute_plan(plan, original_raw, output, execution)
    except (Exception, KeyboardInterrupt) as error:
        execution.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
                         error={'type': type(error).__name__, 'message': str(error)})
        if execution['steps']:
            execution['steps'][-1]['status'] = execution['status']
        raise
    else:
        execution['status'] = 'completed'
        execution['steps'][-1]['status'] = 'completed'
        return final_result, checked
    finally:
        execution['finished_at'] = datetime.now(timezone.utc).isoformat()
        if execution['steps']:
            execution['steps'][-1]['finished_at'] = execution['finished_at']
        write_json(output / 'execution.json', execution)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    with mne.io.read_raw(args.input, preload=False, verbose=False) as original:
        result, _ = run_plan(plan, original, args.output)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
