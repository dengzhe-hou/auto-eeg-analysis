"""Save analysis code/configuration and rerun it without an agent.

See docs/REPLAY.md. Commands are argument lists, never shell strings. This is
an execution record, not a check of scientific validity or a model-call replay.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def packages() -> dict[str, str]:
    return dict(sorted(
        (re.sub(r"[-_.]+", "-", dist.metadata["Name"]).lower(), dist.version)
        for dist in importlib.metadata.distributions()
    ))


def read_commands(analysis: Path) -> list[list[str]]:
    commands = json.loads((analysis / "run.json").read_text(encoding="utf-8-sig"))["commands"]
    if not commands or any(
        not isinstance(cmd, list) or not cmd
        or any(not isinstance(arg, str) for arg in cmd)
        for cmd in commands
    ):
        raise ValueError("run.json commands must be a nonempty list of argument lists")
    return commands


def environment_yaml(installed: dict[str, str]) -> str:
    if (Path(sys.prefix) / "conda-meta").is_dir():
        conda = os.environ.get("CONDA_EXE") or shutil.which("conda")
        if not conda:
            raise RuntimeError("Activate Conda before capturing its environment")
        result = subprocess.run(
            [conda, "env", "export", "--prefix", sys.prefix, "--no-builds"],
            check=True, capture_output=True, text=True,
        )
        return "\n".join(
            "name: aea-replay" if line.startswith("name:") else line
            for line in result.stdout.splitlines() if not line.startswith("prefix:")
        ) + "\n"
    # A pip environment still needs an explicit Python version to be rebuilt.
    return ("name: aea-replay\nchannels:\n  - conda-forge\ndependencies:\n"
            f"  - python={platform.python_version()}\n  - pip\n  - pip:\n"
            + "".join(f"      - {name}=={version}\n" for name, version in installed.items()))


def capture(project: Path, data: Path, bundle: Path) -> None:
    project, data, bundle = project.resolve(), data.resolve(), bundle.resolve()
    analysis = project / "analysis"
    read_commands(analysis)
    if not data.exists():
        raise FileNotFoundError(data)
    if bundle == analysis or analysis in bundle.parents:
        raise ValueError("Place the bundle outside the source analysis directory")
    if bundle.exists():
        raise FileExistsError(f"Choose a new bundle directory: {bundle}")
    installed = packages()
    env_yaml = environment_yaml(installed)
    commit = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(
        ["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=no"],
        text=True).splitlines()
    bundle.mkdir(parents=True)
    shutil.copytree(analysis, bundle / "analysis", ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("ANALYSIS_PLAN.md", "DATASET_BRIEF.md", "ENVIRONMENT.json"):
        if (project / name).exists():
            shutil.copy2(project / name, bundle / name)
    (bundle / "environment.yml").write_text(env_yaml, encoding="utf-8")
    (bundle / "requirements.txt").write_text(
        "".join(f"{name}=={version}\n" for name, version in installed.items()), encoding="utf-8")
    write_json(bundle / "capture.json", {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "aea_commit": commit, "aea_modified_files": dirty,
        "python": platform.python_version(), "system": platform.system(),
        "machine": platform.machine(), "packages": installed, "data": str(data),
    })
    print(f"Saved code, configuration and environment: {bundle}")


def run(bundle: Path, out: Path, data: Path | None = None) -> int:
    bundle, out = bundle.resolve(), out.resolve()
    record = json.loads((bundle / "capture.json").read_text(encoding="utf-8-sig"))
    current = packages()
    changed = [f"{name}: expected {version}, found {current.get(name, 'missing')}"
               for name, version in record["packages"].items() if current.get(name) != version]
    if platform.python_version() != record["python"]:
        changed.insert(0, f"Python: expected {record['python']}, found {platform.python_version()}")
    if changed:
        raise RuntimeError("Restore the captured environment before replay:\n" + "\n".join(changed))
    data = data.resolve() if data is not None else Path(record["data"])
    if not data.exists():
        raise FileNotFoundError(f"Data not found: {data}. Pass --data with its current location.")
    analysis = bundle / "analysis"
    commands = read_commands(analysis)
    if out == bundle or out in bundle.parents or bundle in out.parents:
        raise ValueError("Choose an output directory outside the saved bundle")
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"Refusing to overwrite an existing run: {out}")
    out.mkdir(parents=True, exist_ok=True)
    for name in ("ANALYSIS_PLAN.md", "DATASET_BRIEF.md", "ENVIRONMENT.json"):
        if (bundle / name).exists():
            shutil.copy2(bundle / name, out / name)
    execution = {
        "bundle": str(bundle), "data": str(data), "output": str(out),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "system": platform.system(),
        "machine": platform.machine(), "steps": [], "status": "running",
    }
    replacements = {"{python}": sys.executable, "{data}": str(data), "{out}": str(out)}
    write_json(out / "execution.json", execution)
    with (out / "stdout.log").open("w", encoding="utf-8") as log:
        for command in commands:
            argv = []
            for arg in command:
                for token, value in replacements.items():
                    arg = arg.replace(token, value)
                argv.append(arg)
            step = {"argv": argv, "cwd": str(analysis)}
            execution["steps"].append(step)
            try:
                result = subprocess.run(argv, cwd=analysis, stdin=subprocess.DEVNULL,
                                        stdout=log, stderr=subprocess.STDOUT)
            except OSError as error:
                step.update(exit_code=1, error=str(error))
            else:
                step["exit_code"] = result.returncode
            if step["exit_code"]:
                execution["status"] = "failed"
                break
        else:
            execution["status"] = "completed"
    execution["finished_at"] = datetime.now(timezone.utc).isoformat()
    write_json(out / "execution.json", execution)
    print(f"{execution['status']}: {out / 'execution.json'}")
    return 0 if execution["status"] == "completed" else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    save = sub.add_parser("capture", help="snapshot approved analysis/ code and configuration")
    save.add_argument("--project", type=Path, required=True)
    save.add_argument("--data", type=Path, required=True)
    save.add_argument("--bundle", type=Path, required=True)
    execute = sub.add_parser("run", help="execute saved commands without generating code")
    execute.add_argument("--bundle", type=Path, required=True)
    execute.add_argument("--out", type=Path, required=True)
    execute.add_argument("--data", type=Path)
    args = parser.parse_args()
    if args.action == "capture":
        capture(args.project, args.data, args.bundle)
    else:
        raise SystemExit(run(args.bundle, args.out, args.data))


if __name__ == "__main__":
    main()
