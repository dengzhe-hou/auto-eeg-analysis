"""Exercise saved-code replay, relocation and failure reporting using real processes."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

SPEC = importlib.util.spec_from_file_location("aea_replay", Path(__file__).parents[1] / "replay.py")
replay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(replay)


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
