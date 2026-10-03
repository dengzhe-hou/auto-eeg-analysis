# Cold-start deployability

Historical record from before the first external Windows run on **2026-07-29**;
the original cold-start run date was not recorded. Counts and platform limitations
below describe that snapshot. See [the current external-use protocol and recorded
Windows results](FIRST_EXTERNAL_TEST.md) for subsequent evidence.

**The question.** "External adoption = 0" is AEA's binding gap and cannot be closed from inside the
project. What *can* be checked from inside is its **precondition**: if AEA does not work from a
clean clone, it certainly will not work for anyone else.

So: clone the repo into a different folder — from local git, so only *committed* content comes
across and anything uncommitted-but-load-bearing shows up — and try to use it.

## What this proves, and what it does not

| ✅ proves | ❌ does not prove |
|---|---|
| the repo is self-contained: nothing gitignored is load-bearing | that it works on **another machine** |
| no code depends on paths tied to one checkout | that it works on **another OS** (the Windows probe is untested) |
| the test suite passes from a clean clone | that it works for **another person** |
| the environment probe and backend resolver work with no prior state | that it works on **other data** — the clone shares `$HOME`, so ERP CORE was already downloaded |

The last row is the important caveat: this is a *deployability* test, not a portability test.

## Findings

The suite passed from the clean clone (62 tests at the time), so the interesting results are the
two defects it found that the suite could not — because the suite runs in the developer's own
checkout, where the missing things happen to be present.

### 1. A new user's first exploratory command destroyed the certified baseline

```bash
python tools/validation/validate_mmn_group.py --subjects 3
```

Every `validate_*_group.py` defaults `--out` to the committed certified JSON — which is what makes
re-certification a one-liner, and also what made this destructive. The 38-subject baseline was
silently replaced by a 3-subject smoke run.

`tools/tests/test_benchmark.py` **did** catch it, on the exact-N assertion:

```
AssertionError: MMN: 3 common subjects, expected exactly 38
```

But only *after* the reference was gone — and a user who had already committed would have shipped
a corrupted baseline, with the certification silently invalidated.

**Fixed:** `tools/validation/_certified_output.py` refuses to overwrite the certified path when the
run's N differs from the committed N, and points at the two legitimate ways forward:

```
REFUSING to overwrite the certified baseline tools/validation/mmn_group_results.json.
  committed: n_subjects = 38
  this run:  n_subjects = 3
  - exploring?      re-run with --out /tmp/my_run.json
  - re-certifying?  re-run the FULL configuration, or pass --force ...
```

Wired into all five validation scripts. Exit code 3.

### 2. The documented reproduce command could not run from a fresh clone

`CROSS_TOOLBOX_EVAL.md` tells readers to reproduce the cross-toolbox result with
`erpcore_eeglab.m` and `erpcore_fieldtrip.m`. Both hardcoded this developer's paths — and
FieldTrip's default pointed *inside a gitignored directory*, so the path did not exist in any
clone at all.

**Fixed:** both scripts now read `AEA_DATA_ROOT` (default `$HOME/mne_data`), `EEGLAB_DIR` /
`EEGLAB_PATH` and `FT_DIR` / `FIELDTRIP_PATH`, and error with an actionable message rather than
silently finding nothing. The reproduce block documents all four variables.

Zero `/home/<user>/` paths remain in any executable source outside reference artefacts.

### 3. Confirmed working from the clean clone

- **Environment probe** ran with no prior `ENVIRONMENT.json` and produced valid JSON.
- **Backend resolver** correctly reported EEGLAB and FieldTrip as **unavailable** (no
  `EEGLAB_PATH`, no engine on PATH) with actionable hints, and resolved to `mne`.
- **A real certified analysis reproduced digit-for-digit** from the clone:
  sub-001 −0.724 µV, sub-002 −1.559, sub-003 −0.091 — identical to the committed values.

## Regression tests

`tools/tests/test_deployability.py` (8 tests) locks all of this in:

- no `/home/<user>/` paths in executable sources
- every validation script guards its certified default, has a `--force` escape hatch, and guards
  *before* writing
- the guard blocks a partial run, allows a matching one, allows `--force`, allows a different
  `--out`
- the environment probe emits valid JSON in a bare environment

Final state: **70 passed, 1 skipped from a fresh clone.**

## Reproduce

```bash
git clone /path/to/auto-eeg-analysis /tmp/aea-cold-start && cd /tmp/aea-cold-start
bash tools/env/check_env.sh
python tools/env/resolve_backend.py --capability erp.preprocess_average --out /tmp/BR.md
python -m pytest tools/tests/ -q
```
