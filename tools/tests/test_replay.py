"""Exercise saved-code replay, relocation and failure reporting using real processes."""
import importlib.util
import json
from pathlib import Path
import shlex
import sys

import pytest

SPEC = importlib.util.spec_from_file_location("aea_replay", Path(__file__).parents[1] / "replay.py")
replay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(replay)

RECEIPT_SPEC = importlib.util.spec_from_file_location("aea_receipt", Path(__file__).parents[1] / "gen_receipt.py")
receipt = importlib.util.module_from_spec(RECEIPT_SPEC)
RECEIPT_SPEC.loader.exec_module(receipt)


@pytest.fixture
def study(tmp_path, monkeypatch):
    project = tmp_path / "study with spaces"
    analysis = project / "analysis"
    analysis.mkdir(parents=True)
    data = tmp_path / "raw data"
    data.mkdir()
    (data / "values.json").write_text('[1, 2, 3]', encoding="utf-8")
    (analysis / "config.json").write_text('{"scale": 2}', encoding="utf-8")
    (analysis / "pipeline.py").write_text(
        "import json, pathlib, sys\n"
        "data, out = map(pathlib.Path, sys.argv[1:])\n"
        "values = json.loads((data / 'values.json').read_text())\n"
        "scale = json.loads(pathlib.Path('config.json').read_text())['scale']\n"
        "(out / 'result.json').write_text(json.dumps(sum(values) * scale))\n",
        encoding="utf-8",
    )
    (analysis / "run.json").write_text(json.dumps({"commands": [
        ["{python}", "pipeline.py", "{data}", "{out}"]]}), encoding="utf-8")
    monkeypatch.setattr(replay, "environment_yaml", lambda _: "name: test\n")
    bundle = project / "runs" / "one"
    replay.capture(project, data, bundle)
    return project, data, bundle


def test_saved_code_replays_after_source_changes_and_data_moves(study, tmp_path):
    project, data, bundle = study
    (project / "analysis" / "pipeline.py").write_text("raise RuntimeError('changed')", encoding="utf-8")
    moved = tmp_path / "relocated data"
    data.rename(moved)
    for name in ("first", "repeat"):
        out = tmp_path / name
        assert replay.run(bundle, out, moved) == 0
        assert json.loads((out / "result.json").read_text(encoding="utf-8-sig")) == 12
        assert json.loads((out / "execution.json").read_text(encoding="utf-8-sig"))["status"] == "completed"


def test_failed_program_stops_later_commands_and_records_exit(study, tmp_path):
    _, _, bundle = study
    commands = {"commands": [["{python}", "-c", "import sys; sys.exit(7)"],
                             ["{python}", "-c", "raise Exception('must not execute')"]]}
    (bundle / "analysis" / "run.json").write_text(json.dumps(commands), encoding="utf-8")
    out = tmp_path / "failed"
    assert replay.run(bundle, out) == 1
    record = json.loads((out / "execution.json").read_text(encoding="utf-8-sig"))
    assert record["status"] == "failed"
    assert len(record["steps"]) == 1
    assert record["steps"][0]["exit_code"] == 7


def test_environment_mismatch_stops_before_execution(study, tmp_path, monkeypatch):
    _, _, bundle = study
    monkeypatch.setattr(replay, "packages", lambda: {})
    with pytest.raises(RuntimeError, match="Restore the captured environment"):
        replay.run(bundle, tmp_path / "mismatch")
    assert not (tmp_path / "mismatch").exists()


def test_existing_outputs_and_bundles_are_preserved(study, tmp_path):
    project, data, bundle = study
    with pytest.raises(FileExistsError):
        replay.capture(project, data, bundle)
    out = tmp_path / "existing"
    out.mkdir()
    (out / "result.json").write_text("42", encoding="utf-8")
    with pytest.raises(FileExistsError):
        replay.run(bundle, out)
    assert (out / "result.json").read_text(encoding="utf-8-sig") == "42"


def test_receipt_rejects_missing_reproduction_source(tmp_path, monkeypatch, capsys):
    project = tmp_path / "study"
    monkeypatch.setattr(sys, "argv", ["gen_receipt.py", "--project", str(project)])
    with pytest.raises(SystemExit) as error:
        receipt.main()
    assert error.value.code == 2
    assert "--reproduce --bundle is required" in capsys.readouterr().err
    assert not project.exists()


@pytest.mark.parametrize("source", ["reproduce", "bundle"])
def test_receipt_records_explicit_reproduction_source(study, monkeypatch, source):
    project, _, bundle = study
    command = "python analysis/pipeline.py --condition 'auditory left'\npython analysis/report.py"
    value = command if source == "reproduce" else str(bundle)
    monkeypatch.setattr(sys, "argv", ["gen_receipt.py", "--project", str(project), f"--{source}", value])
    monkeypatch.setattr(receipt, "pkg_version", lambda _: "test")
    receipt.main()
    result = (project / "report-stage" / "REPRO_RECEIPT.md").read_text(encoding="utf-8-sig")
    if source == "reproduce":
        assert f"\n{command}\n```" in result
        assert "tools/env/requirements-optional.txt" in result
    else:
        assert "python tools/replay.py run --bundle " + shlex.quote(str(bundle)) in result
        saved = json.loads((bundle / "capture.json").read_text(encoding="utf-8-sig"))
        assert f"# Captured AEA commit: {saved['aea_commit']}" in result
    assert "tools/run_case_study.py" not in result
