"""Guard the committed certified result files against accidental overwrite.

Each `validate_*_group.py` defaults `--out` to the committed certified JSON — which is what makes
re-certification a one-liner, and also what makes the first thing a new user tries destructive:

    python tools/validation/validate_mmn_group.py --subjects 3

silently replaces a 38-subject certified baseline with a 3-subject smoke run. `tools/tests/
test_benchmark.py` then fails on the exact-N assertion, but only *after* the baseline is gone, and
a user who had already committed would have shipped a corrupted reference.

This was found by a cold-start deployment test in a fresh clone, not by the test suite.

The rule: writing to the certified path is allowed only when the run reproduces the same number of
subjects the committed file records. Any other N needs an explicit `--out` elsewhere, or `--force`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def guard_certified_output(out: str | Path, default_out: str | Path, n_new: int,
                           force: bool = False) -> None:
    """Exit with a message rather than overwrite a certified baseline with a different N.

    Parameters
    ----------
    out
        Where this run was asked to write.
    default_out
        The script's default — i.e. the committed certified file.
    n_new
        Number of subjects this run actually analysed.
    force
        Set by ``--force``; re-certification after a deliberate change.
    """
    out, default_out = Path(out), Path(default_out)
    if force or out.resolve() != default_out.resolve() or not out.exists():
        return

    try:
        n_old = int(json.loads(out.read_text(encoding="utf-8-sig"))["n_subjects"])
    except Exception:            # noqa: BLE001 — an unreadable baseline is not worth protecting
        return

    if n_old == n_new:
        return

    print(
        f"\nREFUSING to overwrite the certified baseline {out}.\n"
        f"  committed: n_subjects = {n_old}\n"
        f"  this run:  n_subjects = {n_new}\n\n"
        f"That file is the reference tools/tests/test_benchmark.py checks against, so replacing it\n"
        f"with a partial run silently invalidates the certification.\n\n"
        f"  - exploring?      re-run with --out /tmp/my_run.json\n"
        f"  - re-certifying?  re-run the FULL configuration, or pass --force if the change in N\n"
        f"                    is intended (and say so in the commit message).\n",
        file=sys.stderr,
    )
    raise SystemExit(3)
