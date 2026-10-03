"""The generation scorer must not call an incomplete cohort a PASS.

Found by the Round-1 reviewer: under the old rule a generation that analysed 34 of the 38
reference subjects, and agreed on those 34, was recorded PASS: true (SPECLEVEL L0_6). Agreement on
the retained intersection is a different claim from reproduction of the intended analysis.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "benchmark"))


@pytest.fixture
def ref():
    return {f"sub-{i:03d}": -0.8 + 0.01 * i for i in range(1, 39)}


def _score(ref, gen, tmp_path):
    import score_recipe_generation as sg
    p = tmp_path / "gen" / "X" / "result.json"; p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"per_subject": gen, "grand_mean_uV": sum(gen.values()) / len(gen)}),
                 encoding="utf-8")
    return sg.score(p, ref)


def test_partial_cohort_is_not_a_pass_even_when_numbers_agree(ref, tmp_path):
    gen = {k: v for k, v in list(ref.items())[:34]}          # 34 of 38, all exact
    r = _score(ref, gen, tmp_path)
    assert r["numerical_agreement_on_common"] is True
    assert r["cohort_complete"] is False and len(r["missing_subjects"]) == 4
    assert r["PASS"] is False


def test_full_cohort_with_agreement_passes(ref, tmp_path):
    r = _score(ref, dict(ref), tmp_path)
    assert r["cohort_complete"] is True and r["PASS"] is True
    assert r["grand_mean_gen_on_common_uV"] == pytest.approx(r["grand_mean_ref_on_common_uV"])


def test_committed_manifest_flags_the_partial_cohort_record():
    """The committed summaries predate the rule; the manifest must say which records it affects."""
    m = json.loads((ROOT / "tools" / "benchmark" / "reports" / "run_manifest.json").read_text(encoding="utf-8-sig"))
    assert "L0_6" in m["partial_cohort_runs"]
    # 19 records analysed 39-40 subjects (no reference exclusions): covered the reference cohort
    # but did not match it. Both notions must be recorded, separately.
    assert "L0_1" in m["cohort_mismatch_runs"] and "L0_1" not in m["partial_cohort_runs"]
    assert len(m["cohort_mismatch_runs"]) >= 19
