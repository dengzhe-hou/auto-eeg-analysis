"""Exercise report verdicts when an earlier stage fails but pytest passes."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("failure", ["none", "missing", "probe", "resolver", "declined", "tests"])
def test_report_verdict_includes_all_stages(tmp_path, failure):
    """The real reporter must not turn a failed probe or resolver into PASS."""
    windows = sys.platform == "win32"
    shell = shutil.which("powershell" if windows else "bash")
    if shell is None:
        pytest.skip("the platform's report shell is unavailable")
    suffix = "ps1" if windows else "sh"
    env_dir = tmp_path / "tools" / "env"
    env_dir.mkdir(parents=True)
    reporter = env_dir / f"deploy_report.{suffix}"
    shutil.copyfile(ROOT / "tools" / "env" / reporter.name, reporter)
    # Only the dependencies are stubbed. The report script, stage execution,
    # exit handling, and final verdict all run unchanged.
    probe_python = env_dir / "probe.py"
    probe_python.write_text(
        "import os, sys\nfrom pathlib import Path\n"
        "Path(sys.argv[1]).write_text('{}', encoding='utf-8')\n"
        "sys.exit(2 if os.environ['AEA_TEST_FAILURE'] == 'probe' else 0)\n",
        encoding="utf-8",
    )
    if windows:
        probe_source = (
            'param([string]$Out)\n'
            '& $env:AEA_PYTHON (Join-Path $PSScriptRoot "probe.py") $Out\n'
            'exit $LASTEXITCODE\n'
        )
    else:
        probe_source = '"$AEA_PYTHON" tools/env/probe.py "$1"\n'
    (env_dir / f"check_env.{suffix}").write_text(probe_source, encoding="utf-8")
    (env_dir / "resolve_backend.py").write_text(
        "import os, sys\nfrom pathlib import Path\n"
        "failure = os.environ['AEA_TEST_FAILURE']\n"
        "if failure == 'resolver':\n    raise RuntimeError('test resolver crash')\n"
        "if failure == 'declined':\n    print('ERROR: no backend available')\n    sys.exit(1)\n"
        "Path(sys.argv[sys.argv.index('--out') + 1]).write_text(\n"
        "    '## Candidates considered\\n\\nMNE\\n## End\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    for module in ("mne", "numpy", "scipy"):
        (stubs / f"{module}.py").write_text("", encoding="utf-8")
    if failure == "missing":
        (stubs / "mne.py").write_text("raise ImportError('test missing MNE')\n", encoding="utf-8")
    (stubs / "pytest.py").write_text(
        "import os, sys\n"
        "if __name__ == '__main__':\n"
        "    failed = os.environ['AEA_TEST_FAILURE'] == 'tests'\n"
        "    print('1 failed' if failed else '1 passed')\n"
        "    sys.exit(1 if failed else 0)\n",
        encoding="utf-8",
    )
    env = dict(os.environ, AEA_PYTHON=sys.executable, AEA_TEST_FAILURE=failure,
               PYTHONPATH=str(stubs))
    command = [shell]
    if windows:
        command += ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]
    run = subprocess.run(command + [str(reporter)], cwd=tmp_path, env=env,
                         capture_output=True, text=True, timeout=30)
    report = (tmp_path / "AEA_DEPLOY_REPORT.md").read_text(encoding="utf-8-sig")
    if failure == "missing":
        assert run.returncode == 2, run.stdout + run.stderr
        assert "BLOCKED" in report and "**mne**" in report
        assert "**PASS**" not in report
        return
    verdict = report.split("## Verdict", 1)[1]
    assert (run.returncode == 0) == (failure == "none"), run.stdout + run.stderr
    assert ("**PASS**" in verdict) == (failure == "none"), report
    assert ("**NOT READY**" in verdict) == (failure != "none"), report
    if failure == "resolver":
        assert "**CRASH**" in report
    if failure == "declined":
        assert "**Resolver declined.**" in report
