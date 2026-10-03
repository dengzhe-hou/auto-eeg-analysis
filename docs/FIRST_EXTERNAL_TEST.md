# First external test — what to send, and what to ask back

AEA's binding gap is that **nobody outside this machine has ever run it**. The
[cold-start test](DEPLOYABILITY.md) checked the precondition (a clean clone works *here*); this
closes the remaining half by asking one person on one other machine.

The design constraint is that a tester's time is the scarce resource. So: **one file to receive,
one command to run, one file to send back.** No install, no data download, no account needed.

---

## What you send

**1. The code.** The repo is private, so pick whichever is less friction for them:

```bash
# a) a self-contained archive of the current commit — no GitHub account needed
git archive --format=tar.gz --prefix=aea/ -o /tmp/aea.tar.gz HEAD
```

or add them as a collaborator on the repo if they already have GitHub.

**2. This message.** Copy it as-is:

> Hi — I've built an EEG analysis tool and I need to find out whether it works on a machine that
> isn't mine. It's never been run anywhere else, so anything that breaks is genuinely useful to me.
>
> It takes about 5 minutes and needs nothing installed beyond Python with `mne`, `numpy`, `scipy`
> and `pytest`. It doesn't download any data, doesn't touch your files, and doesn't upload anything
> — it just writes one text file that you send back to me.
>
> ```bash
> tar xzf aea.tar.gz && cd aea
> bash tools/env/deploy_report.sh
> ```
>
> On Windows: `powershell -ExecutionPolicy Bypass -File tools\env\deploy_report.ps1`
>
> (`-ExecutionPolicy Bypass` affects only this one invocation and changes nothing on your system.
> If Windows still refuses because the archive came from the internet, run
> `Get-ChildItem -Recurse | Unblock-File` inside the extracted folder first.)
>
> That writes `AEA_DEPLOY_REPORT.md`. Home paths in it are already redacted to `~` — have a look
> before you send it, it's short and plain text.
>
> **What I'd like back:**
> 1. `AEA_DEPLOY_REPORT.md`
> 2. Whether anything surprised you or was unclear — including in these instructions
> 3. Roughly how long it took, and whether you had to install anything
>
> **If it fails, please send the report anyway.** A failure is the result I'm actually looking for.

---

## The one failure mode that produces no report at all

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

## What comes back, and what each outcome means

The report has three sections and a verdict.

| section | what a failure there tells you |
|---|---|
| **1. Environment probe** | `check_env.sh`/`.ps1` broke on a real machine, or emitted invalid JSON. Every skill reads that file first, so this is a hard stop. `check_env.ps1` has now run four times on real Windows under PowerShell 5.1; it has **never** run under PowerShell 7, which takes a different branch. |
| **2. Backend resolution** | The resolver crashed, or declined when it should have resolved. "Declined" is not a failure: it refuses rather than degrading silently, and the report shows what was missing. |
| **3. Test suite** | The interesting one. Skips are expected without the large datasets; **failures** mean something depends on this developer's machine in a way the cold-start test could not see. |

**What "clean" looks like: zero failures and zero errors.** Do not compare the *counts* — the
number of skips depends on which optional packages the tester happens to have, so a fixed number
would generate false alarms. On a pristine unpacked archive with no datasets and no optional
extras, the observed result was:

```
62 passed, 9 skipped
```

with the skips being the ERP CORE data gate (1), the MNE sample dataset gate (7, each naming
`AEA_FETCH_DATA=1` as the opt-in), and one absent optional package (`pactools`). A machine with
more of the optional stack installed will show more passes and fewer skips; that is fine. The
signal is `failed` and `error`, both of which must be 0.

### What each answer buys

- **Everything passes** → external adoption goes from 0 to 1 *as a runnable artefact*. Not adoption
  in the sense that matters (nobody has analysed their own data with it), but it is the first
  evidence the project works off this machine.
- **The probe or resolver fails** → a portability defect, exactly what this is for. Fix, and ask
  the same person to re-run — a second data point from the same machine is cheap.
- **The instructions confused them** → also a finding, and one no test can produce. Question 2 in
  the message exists for this.

## What this still does not establish

Getting a green report back is **not** adoption. It proves the code runs somewhere else. It does
not prove anyone can analyse *their own* EEG with it, which needs a tester with their own dataset
and a real question — a much larger ask, and the right one to make only after this smaller one
comes back clean.

Record whatever comes back — including a non-reply — in this file. A tester who never got around
to it is itself information about the friction.

## Results

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

**8 defects, none reproducible on the developer's Linux machine.** The most instructive one
(defect 7) was not Windows-specific at all — it was broken on both platforms, and it took someone
who refused to trust the maintainer's own check to expose it.

**What is still not established.** Every run so far was performed by someone who had read the code,
on a machine with the datasets already cached. Nobody has followed the instructions cold, and
nobody has analysed their own EEG. Those remain the two open questions, in that order.
