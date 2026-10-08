"""Tests for backend resolution (tools/env/resolve_backend.py + backends.json).

The point of the resolver is that it makes three refusals impossible to skip. These tests hold it
to them, because each corresponds to a failure that actually happened in this project:

  1. Silent degradation — a stage that "works" on a backend nobody chose.
  2. Silent substitution — reproducing certified numbers on a backend they were not certified on.
  3. Unmeasured equivalence — describing two toolboxes as interchangeable without a benchmark.

Plus a consistency check: every requirement named in backends.json must be a field the environment
probe actually emits, or the resolver would silently consider every backend unavailable.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENV_DIR = ROOT / "tools" / "env"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "certification" / "benchmark"
sys.path.insert(0, str(ENV_DIR))

from resolve_backend import ResolutionError, resolve  # noqa: E402

REGISTRY = json.loads((ENV_DIR / "backends.json").read_text(encoding="utf-8-sig"))


def env_with(**avail: bool) -> dict:
    """Minimal ENVIRONMENT.json with the named requirement paths present or absent."""
    return {
        "schema_version": "3",
        "probed_at": "2026-07-29T00:00:00Z",
        "python_packages": {"mne": {"available": avail.get("mne", True), "pip": "mne"}},
        "matlab_engine": {"available": avail.get("engine", True), "engine": "octave"},
        "eeglab": {"available": avail.get("eeglab", True), "hint": "set EEGLAB_PATH"},
        "fieldtrip": {"available": avail.get("fieldtrip", True), "hint": "set FIELDTRIP_PATH"},
    }


def test_mne_is_preferred_when_available():
    res = resolve("erp.preprocess_average", env_with(), REGISTRY)
    assert res["chosen"] == "mne"
    assert res["is_reference"] is True


def test_falls_through_to_next_available_backend():
    res = resolve("erp.preprocess_average", env_with(mne=False), REGISTRY)
    assert res["chosen"] == "eeglab"
    res = resolve("erp.preprocess_average", env_with(mne=False, eeglab=False), REGISTRY)
    assert res["chosen"] == "fieldtrip"


def test_prefer_overrides_order_but_still_requires_availability():
    assert resolve("erp.preprocess_average", env_with(), REGISTRY,
                   prefer="fieldtrip")["chosen"] == "fieldtrip"
    # preferring an unavailable backend falls back rather than pretending
    assert resolve("erp.preprocess_average", env_with(fieldtrip=False), REGISTRY,
                   prefer="fieldtrip")["chosen"] == "mne"


def test_matlab_engine_gates_both_matlab_backends():
    """EEGLAB and FieldTrip both need an engine; without one only MNE survives."""
    with pytest.raises(ResolutionError):
        resolve("erp.preprocess_average", env_with(mne=False, engine=False), REGISTRY)


# --- refusal 1: never degrade silently ---------------------------------------------------------

def test_no_backend_available_raises_and_names_what_is_missing():
    with pytest.raises(ResolutionError) as e:
        resolve("erp.preprocess_average",
                env_with(mne=False, eeglab=False, fieldtrip=False), REGISTRY)
    msg = str(e.value)
    for expected in ("mne", "eeglab", "fieldtrip", "EEGLAB_PATH"):
        assert expected in msg, f"resolution error should tell the user about {expected}: {msg}"


def test_unknown_capability_raises():
    with pytest.raises(ResolutionError):
        resolve("does.not.exist", env_with(), REGISTRY)


# --- refusal 2: never switch silently away from a certified reference --------------------------

def test_certified_reference_blocks_substitution():
    with pytest.raises(ResolutionError) as e:
        resolve("erp.preprocess_average", env_with(mne=False), REGISTRY,
                certified_reference="mne")
    msg = str(e.value)
    assert "refusing" in msg
    assert "0.233" in msg, "the refusal must quote the measured divergence, not just object"


def test_certified_reference_allows_explicit_override_and_records_it():
    res = resolve("erp.preprocess_average", env_with(mne=False), REGISTRY,
                  certified_reference="mne", allow_uncertified=True)
    assert res["chosen"] == "eeglab"
    assert res["uncertified_override"], "an accepted override must be recorded, not forgotten"


def test_certified_reference_is_a_no_op_when_it_is_what_gets_chosen():
    res = resolve("erp.preprocess_average", env_with(), REGISTRY, certified_reference="mne")
    assert res["chosen"] == "mne" and res["uncertified_override"] is None


# --- refusal 3: never claim unmeasured equivalence ---------------------------------------------

def test_unmeasured_agreement_is_reported_as_unmeasured():
    # Deliberately NOT stats.cluster_permutation any more: that agreement has since been measured
    # (tools/benchmark/CLUSTER_CERT.md), and this test correctly failed when it was. Pointed at
    # ica.label instead, which is still declared measured:false. If that one is ever measured too,
    # this test should be repointed again rather than relaxed -- the rule it guards is that a
    # report must not imply an equivalence nobody established.
    from resolve_backend import render_markdown
    res = resolve("ica.label", env_with(mne=False), REGISTRY, prefer="eeglab")
    md = render_markdown(res, env_with())
    assert "Not measured" in md
    assert "Do not describe this backend's output as equivalent" in md


def test_measured_agreement_reports_the_numbers_and_the_caveat():
    from resolve_backend import render_markdown
    res = resolve("erp.preprocess_average", env_with(), REGISTRY, prefer="eeglab")
    md = render_markdown(res, env_with())
    assert "0.233" in md and "0.9953" in md
    assert "not** per-subject-identical" in md


def test_measured_cluster_backend_renders_its_own_metrics():
    """The FieldTrip cluster backend is measured, but with cluster metrics, not ERP-amplitude ones.

    Found by the Round-1 reviewer: resolving stats.cluster_permutation to FieldTrip and rendering
    the report raised KeyError('worst_max_abs_diff_uV'). The documented user path was broken for
    the one backend the registry had just upgraded to measured:true.
    """
    from resolve_backend import render_markdown
    res = resolve("stats.cluster_permutation", env_with(mne=False), REGISTRY, prefer="fieldtrip")
    md = render_markdown(res, env_with())
    assert "clusters identical when threshold pinned" in md
    assert "Not measured" not in md


# --- registry integrity -------------------------------------------------------------------------

def test_every_requirement_is_emitted_by_the_probe():
    """A typo'd requirement path makes a backend permanently 'unavailable' and nothing complains."""
    probe = (ENV_DIR / "check_env.sh").read_text(encoding="utf-8-sig")
    for name, spec in REGISTRY["backends"].items():
        for req in spec["requires"]:
            top = req.split(".")[0]
            assert re.search(rf'"{re.escape(top)}"\s*:', probe), (
                f"backend {name!r} requires {req!r} but check_env.sh never emits a "
                f"top-level {top!r} field"
            )


def test_every_candidate_has_an_agreement_entry():
    for cap_name, cap in REGISTRY["capabilities"].items():
        for b in cap["candidates"]:
            assert b in REGISTRY["backends"], f"{cap_name}: unknown backend {b!r}"
            ag = cap.get("agreement", {}).get(b)
            assert ag is not None, f"{cap_name}/{b}: no agreement entry"
            assert "measured" in ag, f"{cap_name}/{b}: must state measured true or false"
            if not ag["measured"]:
                assert ag.get("reason"), f"{cap_name}/{b}: unmeasured agreement needs a reason"


def test_every_capability_pins_at_least_one_convention():
    """A capability with candidates but no pins would let a backend switch change numbers silently."""
    for cap_name, cap in REGISTRY["capabilities"].items():
        if len(cap["candidates"]) > 1:
            assert cap.get("pin"), f"{cap_name}: multiple backends but nothing pinned"
            for p in cap["pin"]:
                for field in ("id", "question", "consequence"):
                    assert p.get(field), f"{cap_name}/{p.get('id')}: missing {field}"


def test_measured_numbers_match_the_benchmark_results():
    """backends.json must not drift from the benchmark output it cites."""
    rows = json.loads((FIXTURES / "CROSS_TOOLBOX_RESULT.json").read_text(encoding="utf-8-sig"))
    div = json.loads((FIXTURES / "CROSS_TOOLBOX_DIVERGENCE.json").read_text(encoding="utf-8-sig"))
    toolbox = {(d["component"], d["source"].split("/")[-1]): d["toolbox"] for d in div}
    label = {"eeglab": "EEGLAB/Octave", "fieldtrip": "FieldTrip/Octave"}

    ag = REGISTRY["capabilities"]["erp.preprocess_average"]["agreement"]
    for backend in ("eeglab", "fieldtrip"):
        sel = [
            r for r in rows
            if toolbox.get((r["component"], r["source"])) == label[backend]
            and "df0.1" not in r["source"] and "cutmatch" not in r["source"]
            and r["reject_mode"] != "abs"
        ]
        assert len(sel) == ag[backend]["n_components"]
        assert max(r["max_abs_diff_uV"] for r in sel) == pytest.approx(
            ag[backend]["worst_max_abs_diff_uV"], abs=1e-4)
        assert min(r["ccc"] for r in sel) == pytest.approx(ag[backend]["min_ccc"], abs=1e-4)
        assert all(r["same_conclusion"] for r in sel)


# --- the CLI actually runs -----------------------------------------------------------------------

def test_cli_writes_a_report_and_exits_nonzero_when_blocked(tmp_path):
    env_file = tmp_path / "ENVIRONMENT.json"
    env_file.write_text(json.dumps(env_with()), encoding="utf-8")
    out = tmp_path / "BACKEND_RESOLUTION.md"
    r = subprocess.run(
        [sys.executable, str(ENV_DIR / "resolve_backend.py"),
         "--capability", "erp.preprocess_average", "--env", str(env_file), "--out", str(out)],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert out.exists() and "Backend resolution" in out.read_text(encoding="utf-8-sig")

    env_file.write_text(json.dumps(env_with(mne=False, eeglab=False, fieldtrip=False)), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(ENV_DIR / "resolve_backend.py"),
         "--capability", "erp.preprocess_average", "--env", str(env_file)],
        capture_output=True, text=True)
    assert r.returncode == 1 and "no backend available" in r.stderr
