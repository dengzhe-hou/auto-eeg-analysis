# External use test

AEA is public. Three external Windows rounds are recorded below; a maintainer
pre-flight is recorded separately. The remaining evidence to collect is an
unfamiliar researcher using their own EEG data, then rerunning the saved analysis
on their machine. Automated checks and maintainer runs do not substitute for that
record. No completed own-data case has been recorded here yet.

## Run the test

1. Follow [Getting started](GETTING_STARTED.md) from a fresh checkout on the
   tester's machine. Record the exact Git commit, operating system, agent client
   and model. Note prior AEA experience, cached data, and any maintainer assistance.
   Use an existing raw-data location; copying or publishing the EEG is unnecessary.
2. In the activated analysis environment, run the deployment report below. Read
   all three sections. A clean report establishes that the environment probe,
   backend resolver and available tests passed, not that an EEG study is complete.
   A missing prerequisite or failed stage returns nonzero; keep the report anyway.
3. Choose a recipe matching the tester's actual paradigm, or use the custom MNE
   workflow. Fill the dataset brief with event meanings, channels, subject design
   and the scientific question. Approve the analysis plan before execution. Ask
   the agent to preserve the runnable code and configuration in `analysis/`, using
   the command manifest described in [Saved runs](REPLAY.md). Keep the first run's
   logs, trial counts, numerical outputs, figures, methods text and audit outcome.
4. Capture the program that produced the first analysis, then replay it into a
   separate empty output directory with the same data and configuration. Compare
   the replay with the **original first analysis**, not merely with another
   replay. Do not ask the model to regenerate the program between runs. Before
   replaying, name the scientific outputs, units and numerical tolerances to
   compare. Record the observed differences; timestamps and log paths are not
   scientific outputs.
5. Complete the [feedback template](EXTERNAL_USE_REPORT_TEMPLATE.md). Return the
   report, saved code/configuration, environment record, execution logs and the
   shareable numerical comparison. Keep raw EEG local. Record failures, unclear
   instructions and help received; a blocked attempt is useful evidence too.

Deployment report, from the repository root:

```bash
bash tools/env/deploy_report.sh
```

On native Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File tools/env/deploy_report.ps1
```

The report is `AEA_DEPLOY_REPORT.md`; it redacts home paths. Inspect files before
sharing. If PowerShell refuses a browser-downloaded archive, unblock the extracted
scripts with `Get-ChildItem -Recurse | Unblock-File` from that archive's directory.

Example capture and replay commands, after `analysis/run.json` and its programs
are ready; replace the project and raw-data paths:

```bash
python tools/replay.py capture --project projects/my-study --data /path/to/raw --bundle projects/my-study/runs/run-001
python tools/replay.py run --bundle projects/my-study/runs/run-001 --out projects/my-study/runs/replay-1
```

The bundle contains the saved `analysis/`, `environment.yml`, `requirements.txt`
and `capture.json`. Each replay writes `execution.json` and `stdout.log` alongside
the program's outputs. A new process tests replayability; recreating the captured
environment is a separate step documented in [Saved runs](REPLAY.md).

## Record the outcome

A complete case needs a real tester's own-data analysis and a successful replay,
with the replay's chosen outputs compared against the original analysis. Report deployment, analysis, report/audit and
replay outcomes separately. A scientifically null effect is a valid analysis
result; a skipped required stage is incomplete. Do not infer numerical
certification or population-wide usability from one case.

The maintainer appends each returned case here with its date, commit, provenance,
failures and artifact locations. Label maintainer or agent rehearsals explicitly.
Keep original failures when fixes are followed by another run.

## Historical deployment context

The original archive test needed Python with `mne`, `numpy`, `scipy` and `pytest`.
Its observed result was **62 passed, 9 skipped**: ERP CORE (1), MNE sample data (7),
and an absent optional package (1). These counts are historical. Current skips
depend on installed packages and cached datasets; list them rather than treating
a fixed pass count as the acceptance condition. The MNE sample download requires
explicit `AEA_FETCH_DATA=1`; reuse an existing cache first.

The original probe record reports four executions under Windows PowerShell 5.1;
it records no PowerShell 7 execution. The tester invitation asked for the report,
unclear instructions, elapsed time and any additional installation needed.

### Historical Windows launch notes

Everything else in this document assumes the script *runs*. Two Windows conditions stop it before
its first line executes, and they are the only known way to make this whole mechanism fail
**silently** — the tester gets a refusal from Windows, not an `AEA_DEPLOY_REPORT.md`, so the
"a failure is still a result" contract is broken exactly when it matters:

1. **Execution policy.** The default on Windows client editions is `Restricted`, under which
   `powershell -File some.ps1` is refused outright ("running scripts is disabled on this system").
   Passing `-ExecutionPolicy Bypass` overrides it for that single invocation only and writes
   nothing to the machine's configuration — which is why the instructions above use it rather
   than asking anyone to run `Set-ExecutionPolicy`.
2. **Mark of the Web.** An archive that arrives by email, chat, or a browser download carries a
   `Zone.Identifier` stream. Files extracted from it inherit "came from the internet", and
   PowerShell refuses those even under `RemoteSigned` — the setting many people have already
   relaxed to. `Unblock-File` clears it.

Neither reproduces on a developer box: a machine that has ever run a local script is usually
already at `RemoteSigned` or looser, and a locally-built tarball has no MOTW. The first external
Windows tester ran with `Process = Bypass` inherited from its shell, so four green runs there
said nothing about either condition. Both were found by inspection afterwards, not by a run.

---

## Historical results

These are the original pre-public-release runs. Commit IDs and test counts below
describe those snapshots, not the current public release.

### Run 1 — Windows, 2026-07-29 (commit `bd1b6a6`)

**Verdict: FAIL — `2 failed, 79 passed, 2 skipped`, plus a `CommandNotFoundException`.**
Which is to say: the test worked. Three defects, none reproducible on the developer's Linux box,
all three on this very path.

| # | defect | who it broke |
|---|---|---|
| 1 | `deploy_report.ps1` hardcoded `pwsh`; Windows ships only `powershell.exe` (5.1) | every stock Windows box — and the report blamed `check_env.ps1`, which was fine |
| 2 | `resolve_backend.py` wrote its report with no `encoding=`, so cp1252 met `←`/`—`/`µ` | every Windows user, at step 2 |
| 3 | a bare `"bash"` resolves to `System32\bash.exe`, the WSL launcher | Windows testers, as a red FAIL about *their* machine |

All three are one shape: **a name that exists is not the thing you meant** — the same trap as the
Microsoft Store `python3` stub, two layers down. Fixed in PR #34, with guards generalized past the
instance: the encoding check is parametrised over every `tools/*.py` and caught **97** call sites
where the reporter could see one.

The reporter also raised two hypotheses and disproved them before reporting (no UTF-8 BOM in the
`.sh`; `resolve_backend.py` imports only the stdlib). Recording that here because "I checked and
there was nothing" is a real contribution and usually goes unwritten.

**What this run does not yet tell us.** It was run by someone who had already read the code, on a
machine that already had the datasets cached. Nobody has yet followed the instructions cold, and
nobody has analysed their own EEG.

### Run 2 — same Windows machine, commit `84afc02`

Re-run to verify Run 1's fixes. **They held** — no `CommandNotFoundException`, `132 passed / 0
failed`, `check_env.ps1` invoked correctly under 5.1. Then the chain broke one link further along.

| # | defect |
|---|---|
| 4 | **UTF-8 BOM.** PowerShell 5.1 *always* writes UTF-8 with a BOM, so `check_env.ps1`'s output starts `EF BB BF`, and `resolve_backend.py` read it with `encoding="utf-8"`. That `encoding=` came from the previous round's own 97-site sweep: pinning `"utf-8"` is right for **writing** and wrong for **reading** anything another tool produced. 40 read sites moved to `utf-8-sig`. |
| 5 | **Redaction leaked a real username** through the JSON-escaped form (`C:\\Users\\name`) while matching only the literal. CJK was *not* the cause; the escape shape was. |
| 6 | **A crash labelled "a legitimate outcome."** The report printed *"Resolver declined. That is a legitimate outcome"* directly above a Python traceback. |

Defect 4 carries the round's real lesson, and it is the reporter's phrasing: **this defect was
*unlocked* by fixing the `pwsh` hardcode.** Before that, step 1 produced no file, so step 2 never
saw a BOM. Fixing one link exposes the next — which is an argument for re-running the external test
after every round rather than declaring victory.

Defect 6 is the most important one that broke nothing: it is this project's own
silent-degradation failure mode, appearing one layer up, inside the instrument built to catch it.

Fixed in PR #35.

### Run 3 — same Windows machine, commit `d3428e0`

All of Run 2's fixes verified: section 2 PASS, `BACKEND_RESOLUTION.md` written with every special
character intact (**0 U+FFFD**), and **0 hits on five independent searches** for the username —
including the escaped form that leaked in Run 2.

The reporter noted one small thing: a Python docstring inside a PowerShell function (a string
*expression* there, not a comment). Sweeping for that *class* found only that instance — **but
checking it surfaced something worse sitting next to it.**

| # | defect |
|---|---|
| 7 | **`Assert-NoLeak` was defined and never called.** The claim "the script self-checks its redaction before you send it" was vapour. The reporter's *"no WARNING line"* was consistent with both "redaction worked" and "the check never ran"; it was the latter. What actually established the redaction works is their five independent searches — which they ran because, in their words, they did not want to rely on my check to validate my check. **That instinct was right for a reason neither of us knew at the time.** The bash script had no self-check at all, and the test asserted `"Assert-NoLeak" in ps`, which a dead definition satisfies. |

Fixed in PR #36.

### Run 4 — pre-flight before sending to a second tester, commit `8765f25`

Not an external run: the maintainer re-ran the tester's exact command in a venv containing only
mne/numpy/scipy/pytest. **The self-check added in Run 3 fired on its first real use — and it was
right.**

| # | defect |
|---|---|
| 8 | `(chosen as : $PY)` echoed the interpreter path into the report **without passing through `redact()`** — and `AEA_PYTHON` is an absolute path *in our own instructions*, so the one variable most likely to carry a username was the one not redacted. |

Fixed in PR #37 by moving redaction to the report's **exit** rather than applying it per line.

---

## The pattern these runs keep producing

Three of the eight defects are the same shape, and the second Windows reporter named it best:

> **在出口收口比在每个调用点记得加更难漏** — a chokepoint is harder to miss than discipline.

- redaction applied *per echo* → one line forgot (defect 8)
- `Assert-NoLeak` *defined* but not *called* → the guarantee was never exercised (defect 7)
- one `.ps1` ASCII-ised, the one it *calls* left alone → half a fix (Run 2's opener)

Each was correct only for as long as every future edit remembered. The fixes that stuck were the
ones that removed the need to remember: pipe the whole block through `redact`, assert the call site
and not the definition, parametrise the guard over *every* file of that type rather than naming one.

## Tally after three external rounds

**8 defects in total: 7 from three external Windows rounds and 1 from the maintainer's
Linux pre-flight.** The most instructive one
(defect 7) was not Windows-specific at all — it was broken on both platforms, and it took someone
who refused to trust the maintainer's own check to expose it.

**What these historical runs did not establish.** The external tester had already read the
code and had the datasets cached. These records do not document an unfamiliar user following
the instructions from scratch or completing an analysis of their own EEG. The current protocol
above asks for both and keeps incomplete attempts in the record.
