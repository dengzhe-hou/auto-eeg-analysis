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
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, value: dict) -> None:
    # Status readers must see a complete record while commands are running.
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def process_running(pid: int) -> bool:
    """Query a recorded PID without signalling or stopping it."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            error = ctypes.get_last_error()
            if error == 87:  # The recorded process no longer exists.
                return False
            raise ctypes.WinError(error)
        try:
            code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                raise ctypes.WinError(ctypes.get_last_error())
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def inspect_run(out: Path) -> dict:
    """Read progress and query local PIDs. Never resume or repeat a command."""
    execution = json.loads((out / "execution.json").read_text(encoding="utf-8-sig"))
    local = execution.get("hostname") == socket.gethostname()
    active = next((step for step in reversed(execution["steps"])
                   if step.get("status") == "running"), None)
    return {
        "recorded_status": execution["status"],
        "recorded_hostname": execution.get("hostname"),
        "process_check": "local_pids" if local else "not_checked_on_another_or_unrecorded_host",
        "coordinator_running": (process_running(execution["coordinator_pid"])
                                if local and execution.get("coordinator_pid") else None),
        "active_step": active,
        "child_running": (process_running(active["pid"])
                          if local and active and active.get("pid") else None),
        "scope": "Recorded command PIDs only; not a scientific check or authorization to retry.",
    }


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
        "machine": platform.machine(), "hostname": socket.gethostname(),
        "coordinator_pid": os.getpid(), "steps": [], "status": "running",
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
            step = {"argv": argv, "cwd": str(analysis), "status": "starting",
                    "started_at": datetime.now(timezone.utc).isoformat()}
            execution["steps"].append(step)
            write_json(out / "execution.json", execution)
            log.write(json.dumps({"step": len(execution["steps"]), **step}) + "\n")
            log.flush()
            try:
                child = subprocess.Popen(argv, cwd=analysis, stdin=subprocess.DEVNULL,
                                         stdout=log, stderr=subprocess.STDOUT)
            except OSError as error:
                step.update(exit_code=1, error=str(error))
            else:
                step.update(pid=child.pid, status="running")
                write_json(out / "execution.json", execution)
                try:
                    step["exit_code"] = child.wait()
                except KeyboardInterrupt:
                    execution["status"] = "interrupted"
                    step["exit_code"] = child.poll()
                    if step["exit_code"] is not None:
                        step["status"] = "exited"
                    write_json(out / "execution.json", execution)
                    raise
            step.update(status="failed" if step["exit_code"] else "completed",
                        finished_at=datetime.now(timezone.utc).isoformat())
            write_json(out / "execution.json", execution)
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
    status = sub.add_parser("status", help="inspect saved progress and local process status without retrying")
    status.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "capture":
        capture(args.project, args.data, args.bundle)
    elif args.action == "run":
        raise SystemExit(run(args.bundle, args.out, args.data))
    else:
        print(json.dumps(inspect_run(args.out), indent=2))


if __name__ == "__main__":
    main()
