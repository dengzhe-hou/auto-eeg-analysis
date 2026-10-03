"""Both threshold modes of the MNE cluster-certification script must run on a saved input.

Round-2 review found the default branch crashing with UnboundLocalError (a careless replace had
turned `effective_threshold = float(signed)` into a self-assignment) while every documented run had
used `--threshold auto`. A branch nobody runs is a branch that rots; this exercises both, with a
handful of permutations, on the smallest committed input.
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "tools" / "benchmark" / "cluster_cert" / "cluster_input_N170.mat"
pytest.importorskip("mne")
pytestmark = pytest.mark.skipif(not INPUT.exists(), reason="cluster input not present")


@pytest.mark.parametrize("mode,expected_abs", [("two-sided-0.975", 2.093), ("auto", 1.729)])
def test_threshold_modes_run_and_record_the_threshold(mode, expected_abs, tmp_path):
    out = tmp_path / "res.json"
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "benchmark" / "cluster_cert_mne.py"),
                        "--input", str(INPUT), "--tail", "-1", "--threshold", mode,
                        "--n-permutations", "8", "--out", str(out),
                        "--tmin", "0.1328125", "--tmax", "0.19921875"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-800:]
    res = json.loads(out.read_text(encoding="utf-8-sig"))
    assert res["threshold_mode"] == mode
    assert abs(abs(res["threshold_value"]) - expected_abs) < 0.001      # df 19
    assert res["threshold_value"] < 0                                    # tail -1
    assert res["n_times_used"] == 18                                     # the window, not the epoch
