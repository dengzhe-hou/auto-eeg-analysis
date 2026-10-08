"""The Octave connected-component shim must agree with scipy on random inputs.

The shim (tools/tests/support/octave_shims/spm_bwlabel.m) stands in for SPM's compiled MEX inside
FieldTrip's cluster statistics, so every FieldTrip cluster-certification number passes through it.
Its header has always CLAIMED verification "by tools/tests/test_cluster_cert.py" — but that file
did not exist: the 12/12 check had been run ad hoc and never committed. The acceptance-contract
negotiation for the AEA paper caught the dangling reference; this file discharges it.

Skips when Octave is unavailable (CI has no Octave); runs everywhere the FieldTrip arm can run.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import numpy as np
import pytest

SHIM_DIR = Path(__file__).resolve().parent / "support" / "octave_shims"


def _octave() -> str | None:
    home = os.environ.get("OCTAVE_HOME", str(Path.home() / "miniconda3" / "envs" / "octave"))
    cand = Path(home) / "bin" / "octave-cli"
    if cand.exists():
        return str(cand)
    from shutil import which
    return which("octave-cli")


OCTAVE = _octave()
pytestmark = pytest.mark.skipif(OCTAVE is None, reason="GNU Octave not available")


@pytest.mark.parametrize("seed", range(12))
def test_shim_matches_scipy_label(seed, tmp_path):
    from scipy import ndimage

    rng = np.random.default_rng(seed)
    shp = tuple(int(x) for x in rng.integers(2, 8, size=3))
    bw = (rng.random(shp) > 0.55).astype(int)
    ref_lab, ref_n = ndimage.label(bw, structure=ndimage.generate_binary_structure(3, 1))

    # Column-major flatten so Octave's reshape reconstructs the identical array. Getting this
    # wrong produced 5/8 spurious mismatches in the shim's first ad-hoc verification — the
    # harness, not the labeller, was at fault, which is exactly why the check belongs in a
    # committed test rather than a shell one-liner.
    np.savetxt(tmp_path / "bw.txt", bw.flatten(order="F"), fmt="%d")
    script = tmp_path / "t.m"
    script.write_text(
        f"addpath('{SHIM_DIR}');\n"
        f"v = dlmread('{tmp_path / 'bw.txt'}');\n"
        f"A = reshape(v, {shp[0]}, {shp[1]}, {shp[2]});\n"
        f"[L, N] = spm_bwlabel(A, 6);\n"
        f"printf('%d\\n', N);\n"
        f"f = fopen('{tmp_path / 'lab.txt'}', 'w'); fprintf(f, '%d\\n', L(:)); fclose(f);\n",
        encoding="utf-8",
    )
    r = subprocess.run([OCTAVE, "--no-gui", "--quiet", str(script)],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    got_n = int(r.stdout.strip().splitlines()[-1])
    assert got_n == ref_n, f"component count differs: scipy {ref_n}, shim {got_n}"

    # Same partition, not just the same count: labels may be numbered differently, so compare
    # the grouping of voxels, not the label values.
    got_lab = np.loadtxt(tmp_path / "lab.txt").reshape(shp, order="F").astype(int)
    ref_groups = {frozenset(np.flatnonzero(ref_lab == k)) for k in range(1, ref_n + 1)}
    got_groups = {frozenset(np.flatnonzero(got_lab == k)) for k in range(1, got_n + 1)}
    assert ref_groups == got_groups, "identical counts but different partitions"
