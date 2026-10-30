"""Recorded-result checks and optional replay on the public EDF subset."""

import importlib.util
import json
import os
from pathlib import Path

import numpy as np
import pytest
from sklearn.metrics import balanced_accuracy_score


RECIPE = Path(__file__).resolve().parents[1]
REFERENCE = RECIPE / "validation" / "results"


def records(directory):
    return [json.loads((directory / f"S{s:03d}.json").read_text()) for s in range(1, 6)]


def test_recorded_scores_and_run_separation():
    for result in records(REFERENCE):
        identities = [(p["run"], p["event_sample"]) for p in result["predictions"]]
        assert len(identities) == len(set(identities))
        for fold in result["folds"]:
            assert fold["held_out_run"] not in fold["train_runs"]
            assert set(fold["train_runs"]) | {fold["held_out_run"]} == {4, 8, 12}
            held = [p for p in result["predictions"] if p["run"] == fold["held_out_run"]]
            score = balanced_accuracy_score([p["label"] for p in held], [p["prediction"] for p in held])
            assert score == pytest.approx(fold["balanced_accuracy"], abs=1e-12)
            assert len(held) == fold["test_n"]
            assert fold["manual_feature_max_error"] < 1e-10


@pytest.fixture(scope="module")
def public_replay(tmp_path_factory):
    location = os.environ.get("AEA_EEGBCI_MOTOR_IMAGERY")
    if location is None:
        pytest.skip("Set AEA_EEGBCI_MOTOR_IMAGERY to the downloaded fifteen-file EDF directory.")
    data = Path(location)
    spec = importlib.util.spec_from_file_location("motor_imagery_recipe", RECIPE / "analysis" / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.mne.set_log_level("ERROR")
    output = tmp_path_factory.mktemp("motor_imagery_replay")
    results = [module.evaluate_subject(data, s) for s in module.CONFIG["subjects"]]
    for result in results:
        (output / f"S{result['subject']:03d}.json").write_text(json.dumps(result, indent=2) + "\n")
    return results


def test_public_data_prediction_regression(public_replay):
    for expected, actual in zip(records(REFERENCE), public_replay, strict=True):
        assert actual["records"] == expected["records"]
        for old, new in zip(expected["predictions"], actual["predictions"], strict=True):
            assert {k: v for k, v in old.items() if k != "right_probability"} == {
                k: v for k, v in new.items() if k != "right_probability"}
            assert new["right_probability"] == pytest.approx(old["right_probability"], abs=1e-6, rel=0)


def test_csp_fit_never_receives_held_out_trials(monkeypatch):
    spec = importlib.util.spec_from_file_location("motor_imagery_recipe", RECIPE / "analysis" / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rng = np.random.default_rng(20261030)
    synthetic = {run: (rng.normal(size=(8, 6, 161)), np.tile([0, 1], 4),
                       np.arange(8), {"run": run}) for run in [4, 8, 12]}
    monkeypatch.setattr(module, "load_run", lambda data, subject, run: synthetic[run])
    actual_fit = module.CSP.fit
    fitted = []

    def record_fit(self, x, y):
        fitted.append(x.copy())
        return actual_fit(self, x, y)

    monkeypatch.setattr(module.CSP, "fit", record_fit)
    module.evaluate_subject(Path("unused"), 1)
    for held, training in zip([4, 8, 12], fitted, strict=True):
        expected = np.concatenate([synthetic[run][0] for run in [4, 8, 12] if run != held])
        np.testing.assert_array_equal(training, expected)
