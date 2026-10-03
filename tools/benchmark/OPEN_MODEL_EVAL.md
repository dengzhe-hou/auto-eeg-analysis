# Is certification a property of the spec, or of the model?

**The question.** All prior generation evals used frontier models (Claude, GPT/Codex). If a pinned
specification only yields certified numbers when driven by a frontier model, "certified skills" is a
claim about *models*, not about *specifications* — and it would not transfer to the open-weight models
many labs actually run. So: hand the **same pinned spec** to a much weaker **open-weight** model.

## Setup

**Generator:** `qwen2.5:14b` (open weights, run locally via ollama, **CPU-only inference**, no GPU) —
several capability tiers below Claude/GPT. Given the identical pinned MMN specification used in
[`RECIPE_GENERATION_EVAL.md`](RECIPE_GENERATION_EVAL.md) condition B; asked for code only, no execution.
We executed its script ourselves.

## Result: the science was right, the code did not run

| Capability layer | Claude | GPT/Codex | **Qwen2.5-14B** |
|---|:---:|:---:|:---:|
| Follows every step of the scientific spec | ✅ | ✅ | ✅ |
| Produces **executable** code | ✅ | ✅ | **❌ crashes** |
| Free of **silent data-corruption** bugs | ✅ | ✅ | **❌ latent** |
| Numerical fidelity *(after minimal plumbing fix)* | 0.0005 µV | 0.000 µV | **0.000 µV** |

**As generated, the script crashed** — `np.mean(scalar_list, axis=0)[0]` → `IndexError`. Every
*analysis* step, however, was implemented correctly: channel drop, montage, 0.1–30 Hz filter, 256 Hz
resample, average reference, event decoding (80/70, 180 excluded), epoching, baseline, 100 µV
peak-to-peak rejection, the ≥50/≥150 trial guard, `combine_evoked` difference wave, and the Fz/FCz/Cz
100–250 ms measurement.

We applied a **minimal fix touching only output plumbing** — never analysis logic (3 edits, marked
`[MINFIX]` in `generated_pipelines/C_qwen14b_pipeline_minfix.py`): the scalar-indexing crash, the same
bug in the rounding call, and tracking which subject each value came from. Re-run:

> **Qwen2.5-14B → −0.8399 µV, n = 38, excluded {sub-007, sub-012}** — **identical to the certified
> reference and to the Claude and GPT/Codex generations.**

## Extension: four open-weight models — a failure-mode taxonomy

Same pinned spec, same protocol, three more local models (all CPU, via ollama).

| Model | Ran as generated? | Outcome | Failure mode |
|---|:---:|---|---|
| Claude / GPT-Codex | ✅ | certified (≤0.5 nV) | — |
| **qwen2.5:14b** | ❌ crash | **certified after minimal plumbing fix** (−0.8399, n=38) | scalar-index crash **+ latent silent label misalignment** |
| **qwen2.5:32b** | ✅ ran | ❌ **empty result** — `per_subject: {}`, all 40 subjects in `excluded` | **silent total exclusion** |
| **llama3.1:8b** | ❌ ImportError | ❌ no result | **hallucinated 6 non-existent MNE APIs** (`mne.filtering`, `mne.resample`, `mne.set_eeg_reference`, `mne.events`, `mne.preprocessing.combine_evoked`, `mne.epochs.read_epochs`) |
| **deepseek-r1:14b** | ✅ ran (after extracting code from its chain-of-thought) | ❌ **empty result** | **instruction-following failure** (emitted reasoning instead of code) **+ `sub-0001` four-digit zero-padding** where the data uses `sub-001` → every path missed, exceptions swallowed, all subjects "excluded" |

### The most dangerous failure is not the crash — it is the silent empty result

**Two of four open models produced syntactically valid, non-crashing `result.json` files containing
nothing**: an empty `per_subject` map, every subject listed as "excluded", and `grand_mean_uV = 0.0`.
No traceback, no error log. DeepSeek's root cause is visible in its output — it padded subject IDs to
four digits (`sub-0001`) where the dataset uses three (`sub-001`), so every file path missed, every
exception was caught by its own `try/except`, and the script reported success.

> **A pipeline that crashes is safe. A pipeline that "succeeds" and returns nothing is not.** This
> class is caught trivially by asserting `n_analyzed`, which per-subject certification does implicitly
> (it needs common subjects to compare) but which a grand-mean-only check would not — a mean over an
> empty set is simply reported as 0.

### What this does and does not change

- **Finding 1 stands and is sharpened:** the *specification* carries the scientific content — Qwen-14B,
  three capability tiers below the frontier, reproduced the certified values exactly once its
  output-plumbing bugs were fixed.
- **But capability floors are real and were underestimated at k=1.** With four models, only one open
  model reached the certified numbers at all. Frontier models buy **code-generation reliability**, and
  at this scale that is the binding constraint, not scientific understanding.
- The failure modes are **qualitatively distinct** (crash / silent-empty / hallucinated API /
  instruction-following), so "pass rate" is the wrong summary statistic. A useful evaluation must
  report *which layer* failed.

## Findings

**1. In the retained record, one repaired open-weight program reproduced the certified per-subject values.** A 14B
open-weight model on CPU matched the certified values only after three author-classified output-handling
repairs; the other three open-weight programs failed to execute or produced empty output, so as generated the
open-weight result is 0/4. This pilot supports no certification claim about generation and no estimate of
generator reliability; whether a lab running open weights can obtain certified numbers from the same
specification remains untested. The frontier models bought *code quality*, not *scientific correctness*.

**2. Pinning the spec is necessary but not sufficient.** It fixes *what to compute*; it does not
guarantee the surrounding code is correct. Executability is a separate axis that the spec cannot fix.

**3. Weak models fail in a more dangerous way — silent label corruption.** Qwen's most serious bug was
not the crash:

```python
"per_subject": {f"{sub}": round(value[0], 3)
                for sub, value in zip(range(1, 41), grand_mean_uV)}
```

`grand_mean_uV` contains only the **successfully analysed** subjects, while `range(1,41)` enumerates
**all** subjects. The moment any subject is excluded — and two are — every subsequent value is
attached to the **wrong subject label**. This bug does **not** raise an error. Here it was masked only
because the scalar-indexing crash fired first. Had the model written slightly *better* code, it would
have produced a plausible, silently mislabelled result table.

> **A pipeline that crashes is safe; a pipeline that silently mislabels subjects is not.** Evaluations
> that score generation as pass/fail on execution miss exactly this class of failure. Certification
> against per-subject reference values catches it — a crash-free run with shuffled labels would fail
> the per-subject comparison even though its grand mean might look fine.

## Honest limitations

1. **Four open models, one generation each, one recipe (MMN).** k=1 per model, so each failure mode is
   observed once — whether a given model's crash/empty-result reproduces across samples is untested.
   Given that the MMN spec-precision conclusions flipped repeatedly below k=9, treat the per-model
   outcomes as indicative of *kind*, not of *rate*.
2. **The minimal fix is a judgment call.** We fixed only output plumbing and marked every edit, but
   "minimal" is not a formal criterion; the primary result remains **the code did not run**.
3. **CPU inference may interact with generation quality** (no sampling-parameter tuning was done).
4. The capability table is based on a single generation per model, not a benchmark.
5. **CPU-only inference** for all open models; no sampling-parameter tuning, no repeated draws.
6. The minimal-fix protocol was applied only to Qwen-14B (the one that got far enough to warrant it);
   the other three were not rescued, so their *scientific* fidelity is unmeasured — we know only that
   they failed before producing usable numbers.

## Reproduce
```bash
ollama serve &
ollama run qwen2.5:14b < <pinned-spec-prompt> > raw_output.txt
# strip fences -> pipeline.py, run it, then score:
python tools/benchmark/score_recipe_generation.py --component MMN --gen-dir <dir> --labels C_qwen14b
```
