"""Numerical regression checks against retained cross-tool certification fixtures.

The saved per-subject amplitudes and waveform summaries provide deterministic
reference checks. Raw-data paper reproduction runs remain local and separate.
"""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

TESTS = Path(__file__).resolve().parent
FIXTURES = TESTS / "fixtures" / "certification"


def _load(rel):
    spec = importlib.util.spec_from_file_location(Path(rel).stem, TESTS / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_cmp = _load("support/compare_mmn.py")

# name, aea json, gold json, metric key, CCC floor, per-subject max|Δ| tol (µV),
# exact expected common-N, waveform-RMSE-median ceiling (nV)
COMPONENTS = [
    ("MMN",  "validation/mmn_group_results.json",   "benchmark/bidspipe_mmn_results.json",   "mmn_uV",  0.99, 0.10, 38, 20.0),
    ("P3",   "validation/p3_group_results.json",    "benchmark/bidspipe_p3_results.json",    "p3_uV",   0.99, 0.10, 20,  5.0),
    ("N170", "validation/n170_erpcore_results.json","benchmark/bidspipe_n170_results.json",  "n170_uV", 0.99, 0.10, 20, 40.0),
    ("ERN",  "validation/ern_erpcore_results.json", "benchmark/bidspipe_ern_results.json",   "ern_uV",  0.99, 0.10, 14, 50.0),
    ("N400", "validation/n400_erpcore_results.json","benchmark/bidspipe_n400_results.json",  "n400_uV", 0.99, 0.10, 20, 25.0),
]


@pytest.mark.parametrize("name,aea_p,gold_p,key,ccc_min,maxabs,exp_n,wave_max", COMPONENTS)
def test_benchmark_consistency(name, aea_p, gold_p, key, ccc_min, maxabs, exp_n, wave_max):
    """AEA and the gold pipeline still agree on the committed scalar results (exact N)."""
    aea_f, gold_f = FIXTURES / aea_p, FIXTURES / gold_p
    aea = {p["subject"]: p for p in json.load(open(aea_f, encoding="utf-8-sig"))["per_subject"]}
    gold = {p["subject"]: p for p in json.load(open(gold_f, encoding="utf-8-sig"))["per_subject"]}
    subs = sorted(set(aea) & set(gold))
    assert len(subs) == exp_n, f"{name}: {len(subs)} common subjects, expected exactly {exp_n}"
    a = np.array([aea[s][key] for s in subs])
    g = np.array([gold[s][key] for s in subs])
    ccc = _cmp.lin_ccc(a, g)
    max_abs = float(np.abs(a - g).max())
    assert ccc >= ccc_min, f"{name}: CCC {ccc:.4f} < {ccc_min} (benchmark regressed)"
    assert max_abs <= maxabs, f"{name}: max|Δ| {max_abs:.3f} > {maxabs} µV (benchmark regressed)"


@pytest.mark.parametrize("name,aea_p,gold_p,key,ccc_min,maxabs,exp_n,wave_max", COMPONENTS)
def test_waveform_consistency(name, aea_p, gold_p, key, ccc_min, maxabs, exp_n, wave_max):
    """Full-waveform RMSE (all channels x all samples) stays below its committed bound."""
    wf = FIXTURES / f"benchmark/{name}_WAVEFORM_RESULT.json"
    med = json.load(open(wf, encoding="utf-8-sig"))["waveform_rmse_allch_nV"]["median"]
    assert med <= wave_max, f"{name}: waveform RMSE median {med} nV > {wave_max} nV (regressed)"
