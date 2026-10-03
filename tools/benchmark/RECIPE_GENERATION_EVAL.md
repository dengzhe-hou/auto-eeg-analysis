# §6f — Does the *generated* pipeline reproduce the certified numbers?

> **Superseded (2026-09-13/14, external review).** The conclusion below — that a pinned specification
> makes LLM-generated code "numerically certified" — is withdrawn as a certification claim. The
> generated programs were not retained and, except MMN B1 (`RECIPE_GENERATION_RESULT.json`, which
> embeds its 38 subject values and recomputes), neither were the per-subject vectors; the 7/7 figure
> is a set of *retained scoring summaries*, readable but not independently recomputable. It is
> reported in the paper as a historical pilot, `eeg-recipe` is classified L0, and the certification
> claim rests on the cross-toolbox reference-implementation results. The observations that survive:
> the recipe-as-written divergence (0.245 µV) and the open-weight result (0/4 as generated).


**The gap this closes.** Every benchmark in `docs/BENCHMARK.md` compares a **hand-written reference
implementation** of a recipe spec (`tools/validation/validate_*_group.py`) against MNE-BIDS-Pipeline.
That certifies the *spec's reference implementation* — not the thing AEA actually sells: **an LLM
reading `RECIPE.md` and generating the pipeline**. A reviewer's one-line objection ("you certified
hand-written code, not the skill") was, until now, correct.

## Protocol

**9 blind generations in total** (see the Extension section for the full matrix). Each agent wrote a
complete pipeline **from scratch** and ran it on real ERP CORE data, given only the recipe spec + a
dataset brief, and explicitly **forbidden from reading `tools/`** (no reference implementation, no
result files). Round 1 — MMN, two conditions × two independent generations:

| Condition | What the agent got | What it tests |
|---|---|---|
| **A** (A1, A2) | the recipe spec as written — agent chooses the optional steps (ICA? RANSAC? resample rate?) | **spec sufficiency** |
| **B** (B1, B2) | the pinned *harmonized-minimal* config (no ICA / no RANSAC / resample 256) | **code-generation correctness** |

Scored per-subject against the committed, gold-verified values (`mmn_group_results.json`, itself
certified against MNE-BIDS-Pipeline), tolerance ±0.10 µV — the same gate CI enforces.
Scorer: `tools/benchmark/score_recipe_generation.py`; raw: `RECIPE_GENERATION_RESULT.json`.

## Results

| Gen | n analyzed | grand mean | max \|Δ\| vs certified | within ±0.1 µV | r | Verdict |
|-----|:---:|:---:|:---:|:---:|:---:|:---:|
| **B1** | 38 | −0.8399 µV | **0.0005 µV** | **38/38** | **1.000** | ✅ **PASS** |
| **B2** | 38 | −0.8399 µV | **0.0005 µV** | **38/38** | **1.000** | ✅ **PASS** |
| A1 | 40 | −0.8222 µV | 0.245 µV | 30/38 | 0.992 | ❌ fail |
| A2 | 40 | −0.8222 µV | 0.245 µV | 30/38 | 0.992 | ❌ fail |

*(certified reference: −0.840 µV, n = 38)*

**Generation-to-generation reproducibility:** B1 vs B2 **bit-identical**; A1 vs A2 agree to
< 0.0001 µV. Two independent LLM generations of the same spec produce the *same numbers*.

## Extension: 3 components × 2 generator backends (2026-07-12)

Finding ① was then tested for generality — does "pinned spec → certified" hold beyond MMN, and
beyond one generator family? Same blind protocol, condition B (pinned spec):

| Component | Backend | Gen | n | max \|Δ\| vs certified | within ±0.1 µV | Verdict |
|---|---|:---:|:---:|:---:|:---:|:---:|
| MMN | Claude | B1 | 38 | 0.0005 µV | 38/38 | ✅ |
| MMN | Claude | B2 | 38 | 0.0005 µV | 38/38 | ✅ |
| **MMN** | **GPT/Codex** | **B1** | 38 | **0.000 µV** | **38/38** | ✅ |
| P3 | Claude | B1 | 20 | 0.000 µV | 20/20 | ✅ |
| P3 | Claude | B2 | 20 | 0.000 µV | 20/20 | ✅ |
| N170 | Claude | B1 | 20 | 0.0005 µV | 20/20 | ✅ |
| N170 | Claude | B2 | 20 | 0.0005 µV | 20/20 | ✅ |

**7/7 pass.** Run-to-run: P3 **bit-identical**, MMN bit-identical, N170 agree to 0.0001 µV.

**Cross-backend.** The GPT/Codex generation is a stronger test of independence: Codex ran in a
**read-only sandbox and never executed anything** — it wrote the script blind from the spec, and *we*
executed it **unmodified**. It reproduced the certified values exactly (0.000 µV, same 38 subjects,
same 2 exclusions). So the certification is not an artifact of one model family.

**Across-component generality.** The three specs differ meaningfully — MMN uses 100 µV peak-to-peak
rejection while P3/N170 use `reject=None`; N170 filters 0.1–**40** Hz vs 0.1–30; ROIs, windows and
event-decoding rules all differ (P3's target rule is `tens == units`; N170's is face 1–40 vs car 41–80).
Every generation decoded its events correctly and hit the certified numbers.

## Three findings

**1. (Superseded — see the notice at the top.) Given a pinned spec, the seven recorded generations hit the certified numbers — across components and backends.**
**7/7 blind generations** (MMN, P3, N170 × Claude, plus MMN × GPT/Codex) landed **≤0.5 nV** from values
independently verified against MNE-BIDS-Pipeline, **every subject** inside the CI tolerance, selecting the
*identical* excluded subjects. **This closes the "you certified hand-written code, not the skill"
objection** — for a pinned spec, the skill itself is certified, and not by one model family's quirk.

**2. LLM code generation is reproducible, not stochastic-at-the-numbers.** Independent runs agreed
bit-for-bit (B) or to sub-nanovolt (A). Numerical non-determinism of the *generator* is not the
failure mode.

**3. The failure mode is the SPEC, not the generator — and it is systematic.** Condition A missed by
0.245 µV **and both generations missed identically**. Root cause, independently diagnosed by both
agents: the recipe **mandates RANSAC bad-channel interpolation**, which the certified pipeline never
ran. Consequences:
- RANSAC rescued the two subjects the certified run excludes → **n = 40 vs 38** (the *sample* changed,
  not just the number).
- A2's own sensitivity check: disabling RANSAC yields **−0.8399 µV** — i.e. exactly the certified
  value. The entire divergence is attributable to that one under-specified step.
- Both agents also flagged an unspecified **window-edge convention** (at 256 Hz, 100 ms falls between
  samples: 0.0977 vs 0.1016 s). They happened to choose alike; the recipe does not pin it.

> **The lesson for skill corpora generally:** a methodology skill is only numerically reproducible if
> its spec pins every step that moves a number — including which steps are *not* run. Prose that reads
> unambiguously to a human ("Bad channels: RANSAC → interpolate") is not a numerical specification.

## Repo bug this found (fixed)

`recipes/mmn-oddball/RECIPE.md` prescribed RANSAC while its own "Validated results" were produced
*without* it — recipe text and certified result were out of sync. Fixed by pinning the certified
configuration in the recipe (see the recipe's Pipeline §1 note).

## Honest limitations

1. **Three recipes, 9 generations, two generator backends** (Claude ×8, GPT/Codex ×1). Broader
   backend coverage (open-weight models) and the remaining recipes are untested. Condition A
   (spec-as-written) was run only for MMN — whether other recipes are equally under-specified is unknown.
2. **Blindness was prompt-enforced, not sandbox-enforced** — agents were forbidden from reading
   `tools/` and each reported compliance; not mechanically guaranteed. (The A-condition divergence is
   itself evidence they did not copy the reference implementation.)
3. **Condition B pins the pipeline heavily** — it tests code generation, not analysis judgment. The
   realistic setting is A, and A is where the interesting failure lives.
4. The dataset brief supplied dataset-specific facts (event codes, channel names) that in a real run
   would come from AEA's `auto-brief` stage; that stage was not itself under test.

## Reproduce
Give a blind agent the recipe spec + dataset brief (see the prompts recorded in this eval), have it
write and run a pipeline, then:
```bash
python tools/benchmark/score_recipe_generation.py --gen-dir <dir> --labels A1 A2 B1 B2
```
