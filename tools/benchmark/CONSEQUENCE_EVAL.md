# Does the numerical divergence change the science?

> **Reconstructability note (2026-09-13, from external review).** The per-subject amplitude vectors
> of the generated programs were not committed (only scored summaries were) — with one exception:
> MMN B1 in `RECIPE_GENERATION_RESULT.json` embeds its 38 subject values, and its scores recompute
> (max|Δ| 0.00049 µV, 38/38 within tolerance); its program is still absent. The original programs
> of the seven pinned-specification generations are not in `generated_pipelines/`. The 24-run
> enumeration below is MMN-specific. The
> Spearman sequence, the per-generation significance verdicts, and the 56× grand-mean ratio
> reported below therefore **cannot be recomputed from committed data** and are not used in the
> paper. What remains is the enumeration (9 L0 + 12 L1 + 3 L2 = 24 frontier generations, not the
> 23 tabulated in CONSEQUENCE_EVAL.md) and, per generation, the *retained scoring summaries* —
> max|Δ|, within-tolerance count, Pearson r, grand-mean direction (24/24 negative). These are
> readable scores, not independently recomputable evidence, and the paper labels them so.
> Cohort completeness: L0_6 analysed 34 of 38 subjects and was recorded PASS under the old scorer
> rule; the scorer now requires the full cohort for PASS and the manifest flags this record
> (`tools/benchmark/reports/run_manifest.json: partial_cohort_runs`).


The benchmarks report agreement in **microvolts**, with a ±0.10 µV tolerance that we chose. A reviewer's
fair objection: *that threshold is not tied to any scientific consequence.* This grounds it — for every
generation in the spec-precision eval, we ask what actually changes.

## 1. Group-level conclusion: never flips

Single-sample t-test on each generation's per-subject values (is the MMN significantly negative?):

| Level | k | verdict |
|---|:---:|---|
| certified reference | — | significant negative, t=−7.87, p=2.0e-09 |
| **L0** no recipe | 10 | **10/10 significant negative** (p from 1.0e-12 to 4.7e-09) |
| **L1** recipe as written | 10 | **10/10 significant negative** |
| **L2** pinned spec | 3 | **3/3 significant negative** |

**All 23 generations reach the same group-level scientific conclusion as the certified pipeline** —
including the no-recipe baseline whose grand mean is off by 0.9 µV. A robust group effect is robust to
everything we varied.

> **This tempers the alarm.** For a well-powered group contrast, LLM analysis variability did **not**
> threaten the headline claim. Any framing that implies "unspecified pipelines produce wrong
> conclusions" would be overclaiming on this evidence.

## 2. Per-subject ranking: this is what degrades

Spearman ρ of each generation's per-subject values against the certified values:

| Level | k | mean ρ | worst ρ |
|---|:---:|:---:|:---:|
| **L0** no recipe | 10 | **0.894** | **0.727** |
| **L1** recipe as written | 10 | 0.992 | 0.981 |
| **L2** pinned spec | 3 | **1.000** | 1.000 |

Without a protocol, the rank ordering of subjects degrades to ρ≈0.73 in the worst case. That is
precisely the quantity that individual-differences research, biomarker development, and clinical
application depend on.

> **So the ±0.10 µV tolerance cannot be justified by "it prevents wrong conclusions" — it never had to.
> It is justified by protecting per-subject values and their rank order.** State the claim that way.

## 3. Why per-subject certification is not redundant with group-level checks

A concrete demonstration. Take the certified per-subject values and **shuffle the subject labels**
(same multiset of values, wrong assignment) — the exact failure mode latent in the open-weight model's
generated code (`zip(range(1,41), only_successful_subjects)`):

| check | original | after label shuffle | detects it? |
|---|---:|---:|---|
| grand mean | −0.8398 µV | −0.8398 µV | ❌ bit-identical |
| one-sample t | −7.87 | −7.87 | ❌ bit-identical |
| p value | 2.0e-09 | 2.0e-09 | ❌ bit-identical |
| SD / effect size | 0.6578 | 0.6578 | ❌ bit-identical |
| **per-subject max \|Δ\|** | 0.0000 µV | **2.3080 µV** | ✅ |
| **Spearman ρ** | 1.000 | **0.119** | ✅ |

**Every group-level statistic is invariant to label permutation by construction.** A pipeline whose
subject labels are scrambled passes every group-level sanity check ever run on it. Only per-subject
comparison against a reference detects it — which is what the certification protocol does.

## Honest limitations
1. **One component (MMN), one robust effect.** A large, reliable group effect is the *easy* case for
   conclusion-stability. A marginal effect (p≈0.05) could well flip; that is untested and is the
   obvious next experiment.
2. Conclusion-stability tested only for the *group* contrast, not for the second-level cluster test.
3. Rank correlation is one operationalisation of per-subject fidelity; ICC or Bland–Altman would add.
4. The label-shuffle demonstration is a constructed illustration, not an observed failure — though the
   bug that would produce it *was* observed in generated code (see `OPEN_MODEL_EVAL.md`).
