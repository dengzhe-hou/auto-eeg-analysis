"""Regression gate for the cross-tool numeric benchmark (docs/BENCHMARK.md).

Two layers:

1. test_benchmark_consistency (CI-safe, always runs) — for every benchmarked ERP CORE
   component, load the committed AEA and MNE-BIDS-Pipeline per-subject results and assert the
   agreement still holds (Lin's CCC >= 0.99, per-subject max |delta| <= tolerance). This guards
   the comparator logic (tools/benchmark/compare_mmn.py) and the committed result JSONs from
   silent corruption or a broken edit.

2. test_pipeline_regression_mmn (data-gated, skips without data) — re-run AEA's MMN pipeline on
   2 subjects from raw and assert it reproduces the committed per-subject numbers. Guards the
   recipe's reference implementation (validate_mmn_group.py) — NOT live /eeg-recipe LLM generation
   (that is untested; see docs/BENCHMARK.md §6f). Runs only where ERP CORE MMN is present
   (e.g. locally), skips in vanilla CI — same convention as the recipe data-gated tests.
"""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(rel):
    spec = importlib.util.spec_from_file_location(Path(rel).stem, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_cmp = _load("tools/benchmark/compare_mmn.py")

# name, aea json, gold json, metric key, CCC floor, per-subject max|Δ| tol (µV),
# exact expected common-N, waveform-RMSE-median ceiling (nV)
COMPONENTS = [
    ("MMN",  "tools/validation/mmn_group_results.json",   "tools/benchmark/bidspipe_mmn_results.json",   "mmn_uV",  0.99, 0.10, 38, 20.0),
    ("P3",   "tools/validation/p3_group_results.json",    "tools/benchmark/bidspipe_p3_results.json",    "p3_uV",   0.99, 0.10, 20,  5.0),
    ("N170", "tools/validation/n170_erpcore_results.json","tools/benchmark/bidspipe_n170_results.json",  "n170_uV", 0.99, 0.10, 20, 40.0),
    ("ERN",  "tools/validation/ern_erpcore_results.json", "tools/benchmark/bidspipe_ern_results.json",   "ern_uV",  0.99, 0.10, 14, 50.0),
    ("N400", "tools/validation/n400_erpcore_results.json","tools/benchmark/bidspipe_n400_results.json",  "n400_uV", 0.99, 0.10, 20, 25.0),
]


@pytest.mark.parametrize("name,aea_p,gold_p,key,ccc_min,maxabs,exp_n,wave_max", COMPONENTS)
def test_benchmark_consistency(name, aea_p, gold_p, key, ccc_min, maxabs, exp_n, wave_max):
    """AEA and the gold pipeline still agree on the committed scalar results (exact N)."""
    aea_f, gold_f = ROOT / aea_p, ROOT / gold_p
    if not (aea_f.exists() and gold_f.exists()):
        pytest.skip(f"{name}: committed results not present")
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
    wf = ROOT / f"tools/benchmark/{name}_WAVEFORM_RESULT.json"
    if not wf.exists():
        pytest.skip(f"{name}: waveform result not present")
    med = json.load(open(wf, encoding="utf-8-sig"))["waveform_rmse_allch_nV"]["median"]
    assert med <= wave_max, f"{name}: waveform RMSE median {med} nV > {wave_max} nV (regressed)"


def test_pipeline_regression_mmn():
    """Re-run AEA's MMN pipeline on 2 subjects; must reproduce the committed per-subject µV."""
    # the validation loader uses pandas, which is not a core mne dependency
    pytest.importorskip("pandas")
    data = Path.home() / "mne_data" / "MNE-erpcoremmn2021-data"
    committed = ROOT / "tools/validation/mmn_group_results.json"
    if not data.exists() or not committed.exists():
        pytest.skip("ERP CORE MMN data or committed results not present")
    vm = _load("tools/validation/validate_mmn_group.py")
    per = {p["subject"]: p for p in json.load(open(committed, encoding="utf-8-sig"))["per_subject"]}
    checked = 0
    for sub in ("sub-001", "sub-002"):
        if sub not in per:
            continue
        _, mmn_uV, ndev, nstd = vm.subject_mmn(sub)
        assert abs(round(mmn_uV, 3) - per[sub]["mmn_uV"]) <= 0.001, \
            f"{sub}: recomputed {mmn_uV:.3f} != committed {per[sub]['mmn_uV']}"
        assert ndev == per[sub]["n_dev"], f"{sub}: n_dev {ndev} != {per[sub]['n_dev']}"
        checked += 1
    assert checked >= 1, "no MMN subjects available to check"
