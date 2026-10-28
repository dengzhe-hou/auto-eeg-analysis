"""Prepare a study exported by the EEGLAB plugin and open an interactive client.

Preparation reads local EEG headers and writes a researcher-facing brief. It does
not perform EEG analysis or invoke a model. Launching is a separate user action.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

from install_skills import install_skills


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def project_config(project: Path):
    config = read_json(project / "AEA_BRIDGE_CONFIG.json")
    repository = Path(config["repository"]).expanduser().resolve()
    if not (repository / "AGENT_GUIDE.md").is_file():
        raise ValueError("Configure an AEA repository containing AGENT_GUIDE.md")
    if config["client"] not in ("codex", "claude"):
        raise ValueError("Select codex or claude as the coding assistant")
    return config, repository


def imported_header(project: Path):
    import mne

    export = read_json(project / "EEGLAB_EXPORT.json")
    dataset = project / export["input_file"]
    if export["dataset_kind"] == "continuous":
        inst = mne.io.read_raw_eeglab(dataset, preload=False, verbose="ERROR")
        n_epochs, n_samples = 1, inst.n_times
    elif export["dataset_kind"] == "epoched":
        inst = mne.read_epochs_eeglab(dataset, verbose="ERROR")
        n_epochs, n_samples = len(inst), len(inst.times)
    else:
        raise ValueError("Export continuous data or at least two epochs")
    if (len(inst.ch_names) != export["n_channels"]
            or n_samples != export["n_samples_per_epoch"]
            or n_epochs != export["n_epochs"]
            or inst.info["sfreq"] != export["srate"]):
        raise ValueError("MNE import dimensions/rate differ from the EEGLAB export")
    return export, {
        "mne_version": mne.__version__, "dataset_kind": export["dataset_kind"],
        "n_channels": len(inst.ch_names), "n_samples_per_epoch": int(n_samples),
        "n_epochs": int(n_epochs), "sfreq": float(inst.info["sfreq"]), "channel_names": inst.ch_names,
        "reader_channel_types": inst.get_channel_types(),
        "input_file": str(dataset.resolve()), "mne_sample_unit": "V",
        "scope": "Import agreement only; channel identity, processing history and scientific choices need confirmation.",
    }


def request_text(project: Path, repository: Path, config: dict, export: dict):
    recipe = config.get("recipe", "custom")
    task = (f"Use the eeg-recipe skill with {repository / 'recipes' / recipe / 'RECIPE.md'}."
            if recipe != "custom" else "Help the researcher choose relevant AEA skills for their study question.")
    return f"""Work on the EEGLAB-exported EEG study at {project}.
Read {repository / 'AGENT_GUIDE.md'} and the relevant linked skill procedures.
{task}
Read DATASET_BRIEF.md, EEGLAB_EXPORT.json, EEGLAB_IMPORT_CHECK.json,
input/events.json and input/processing_history.txt in the study folder.
The exact exported input is {project / export['input_file']} ({export['dataset_kind']}).
This is a copy of the current EEGLAB dataset; its prior processing is not assumed
to be raw or complete. Preserve existing epochs and ICA metadata as source
information; do not refit ICA, re-filter or invent upstream stages to fit a recipe.
Confirm the study question, observation unit/participant identity, event meanings,
actual channel identities, prior processing and missing scientific choices.
Read an existing ANALYSIS_PLAN.md and reuse its approved choices and permissions.
If no approved plan exists, inspect inputs and draft a plan, then wait for the
researcher's approval before the dependent scientific computations. A recipe or
this launcher does not approve default parameters. Record unresolved decisions
and continue only independent work already authorized by the researcher.
Use the configured Python environment at {sys.executable}; probe it using the
repository's environment instructions before analysis. Keep actual data paths,
parameters, code and checks with this study. Do not change the resource library.
Place the completed HTML report at report-stage/report.html for EEGLAB to open.
"""


def prepare(project: Path):
    config, repository = project_config(project)
    recipe = config.get("recipe", "custom")
    if recipe != "custom" and not (repository / "recipes" / recipe / "RECIPE.md").is_file():
        raise ValueError(f"Recipe not found: {recipe}")
    export, header = imported_header(project)
    install_skills(repository, config["client"])
    write_json(project / "EEGLAB_IMPORT_CHECK.json", header)
    brief = project / "DATASET_BRIEF.md"
    if not brief.exists():
        brief.write_text(f"""# EEGLAB imported study

## Imported facts

- Current dataset copy: `{export['input_file']}`
- Shape: {header['n_channels']} channels, {header['n_samples_per_epoch']} samples per epoch, {header['n_epochs']} epoch(s)
- Sampling rate: {header['sfreq']} Hz
- Dataset kind: {header['dataset_kind']}; original epoch time origin: {export['epoch_tmin_s']} s
- Channel labels: {', '.join(header['channel_names'])}
- EEGLAB export unit: microvolts; MNE read unit: volts
- Sample storage: standard EEGLAB float32 export; source EEG in MATLAB was not changed
- Processing history: `input/processing_history.txt`; prior processing needs confirmation
- Original events: `input/events.json` and the `.set` file; latency is in one-based samples
- Recipe selection: {recipe}; selection is not approval of its parameters

## Researcher choices to resolve

- Study question and hypothesis
- Participant / observation unit (one exported dataset is not automatically one independent participant)
- Paradigm, condition meanings and event mapping
- Actual channel identities and channels eligible for reference/analysis
- Previously applied filtering, reference, ICA/rejection and remaining processing
- Requested measures, contrasts, ROI/time/frequency definitions, statistics and output plan

The import check validates data shape/rate, not those scientific choices.
Keep an existing approved analysis plan; do not infer approval from this export.
""", encoding="utf-8")
    (project / "AEA_REQUEST.md").write_text(request_text(project, repository, config, export), encoding="utf-8")
    write_json(project / "AEA_HANDOFF.json", {
        "state": "ready_for_interactive_planning", "scientific_plan_approved_by_export": False,
        "client": config["client"], "recipe": recipe, "input_file": export["input_file"],
        "request_file": "AEA_REQUEST.md", "report_file": "report-stage/report.html",
        "model_invoked_during_preparation": False,
    })
    return {"project": str(project), "status": "prepared", "next": "Start AEA, then resolve or reuse the study plan."}


def client_command(project: Path):
    config, repository = project_config(project)
    env = os.environ.copy()
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    executable = config.get("client_executable") or config["client"]
    resolved = shutil.which(executable, path=env["PATH"])
    if not resolved:
        raise FileNotFoundError(f"Assistant executable not found: {executable}. Configure its full path in EEGLAB's AEA settings.")
    # Keep the full request in a local file; a short path prompt avoids Windows
    # command-line size limits. No model, budget or permission policy is overridden.
    prompt = f"Read and carry out the study request in {project / 'AEA_REQUEST.md'}."
    if config["client"] == "codex":
        command = [resolved, "--cd", str(repository), "--add-dir", str(project), prompt]
    else:
        command = [resolved, "--add-dir", str(project), "--", prompt]
    return command, repository, env


def session(project: Path):
    command, repository, env = client_command(project)
    return subprocess.call(command, cwd=repository, env=env)


def launch(project: Path):
    if not (project / "AEA_HANDOFF.json").is_file():
        raise ValueError("Prepare the exported study before starting AEA")
    client_command(project)  # Fail here for missing setup, before opening a terminal.
    arguments = [sys.executable, str(Path(__file__).resolve()), "session", "--project", str(project)]
    if sys.platform == "win32":
        process = subprocess.Popen(arguments, creationflags=subprocess.CREATE_NEW_CONSOLE)
    elif sys.platform == "darwin":
        script = project / "start_aea.command"
        script.write_text("#!/bin/bash\nexec " + shlex.join(arguments) + "\n", encoding="utf-8")
        script.chmod(0o755)
        subprocess.run(["open", "-a", "Terminal", str(script)], check=True)
        return {"status": "terminal_open_requested", "project": str(project)}
    else:
        terminal = shutil.which("x-terminal-emulator") or shutil.which("gnome-terminal")
        if not terminal or not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            raise RuntimeError("No desktop terminal is available. Run this in your terminal instead:\n" + shlex.join(arguments))
        separator = "--" if Path(terminal).name == "gnome-terminal" else "-e"
        process = subprocess.Popen([terminal, separator, *arguments])
    return {"status": "terminal_open_requested", "pid": process.pid, "project": str(project)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "launch", "session"))
    parser.add_argument("--project", required=True, type=Path)
    args = parser.parse_args(argv)
    project = args.project.expanduser().resolve()
    try:
        if args.action == "session":
            return session(project)
        result = prepare(project) if args.action == "prepare" else launch(project)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, FileNotFoundError, RuntimeError, ImportError, OSError) as error:
        print(f"AEA: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
