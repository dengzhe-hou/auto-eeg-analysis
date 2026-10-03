# Specification precision → accuracy vs reproducibility

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


**What this adds over [`RECIPE_GENERATION_EVAL.md`](RECIPE_GENERATION_EVAL.md).** That eval showed a
*pinned* spec yields certified numbers and a *loose* spec diverges. Two gaps remained: (i) no
**baseline** — is the recipe better than no recipe at all? (ii) too few generations to separate
*accuracy* from *reproducibility*. This runs three levels of specification precision with repeated
independent generations at each.

## Design

Blind agents (forbidden from reading `tools/`) each wrote an MMN pipeline **from scratch**; they wrote
code only and **we executed every script in one identical environment**, removing execution-side
variation. Three levels:

| Level | What the agent got |
|---|---|
| **L0 — no recipe** (baseline) | only the scientific goal ("compute the MMN") + a dataset brief. No protocol. |
| **L1 — recipe as written** | `recipes/mmn-oddball/RECIPE.md` prose, optional steps left to judgment |
| **L2 — pinned spec** | every number-moving step fixed (no ICA/RANSAC, resample 256, 100 µV p2p, window convention) |

Scored per-subject against the gold-verified reference (certified against MNE-BIDS-Pipeline):
**−0.840 µV, n = 38**.

## Results

| Level | k | grand mean | within-level SD | error vs certified |
|---|:---:|:---:|:---:|:---:|
| **L0** no recipe — *mastoid-reference subgroup* | 7 | −1.735 µV | 0.124 | **0.895 µV** |
| **L0** no recipe — *average-reference subgroup* | 2 | −0.717 µV | 0.025 | 0.123 µV |
| **L1** recipe as written | **12** | −0.824 µV | **0.005** | 0.016 µV |
| **L2** pinned spec | 3 (+Qwen) | −0.840 µV | 0.0002 | **0.000 µV** |

> **L0 must be reported stratified, not pooled.** Its error distribution is **bimodal**, driven by a
> single binary choice: 7 of 9 generations independently picked a **P9/P10 mastoid-style reference**
> (error 0.9 µV), 2 picked **average reference** (error 0.12 µV). Pooling them into one mean±SD
> misrepresents the distribution — the baseline is not "noisy", it is **bistable**.

| Gain | accuracy | within-level SD |
|---|---|---|
| L0 → L1 (give it the recipe) | **56×** (0.895 → 0.016 µV) | 25× (0.124 → 0.005) |
| L1 → L2 (pin every number) | → exact | 25× (0.005 → 0.0002) |

## Findings

**1. The recipe buys accuracy — 56× over no recipe.** Error falls from **0.895 µV** (L0's majority
mastoid subgroup) to **0.016 µV**. This is the **baseline comparison** a reviewer asks for: the skill
corpus demonstrably beats a bare LLM on identical data.

**2. The recipe's real work is collapsing a bistable choice space.** Without a protocol the model
faces a handful of unspecified forks and **commits hard to one branch**: 7/9 generations chose a
mastoid-style reference, 2/9 average reference — each subgroup internally tight (SD 0.12 / 0.03) but
**1.02 µV apart**. The baseline is not noisy, it is **bistable**. The recipe removes the fork: all
**12** L1 generations independently chose the same implementation family (RANSAC + 256 Hz + no ICA +
100 µV peak-to-peak), giving SD **0.005 µV**.

**3. Prose still leaves a reproducibility floor that only numerical pinning removes.** L1's SD of
0.005 µV is 25× tighter than L0's, but L2 is a further 25× tighter (0.0002 µV) and exactly correct.
Residual L1 spread traces to implementation details the prose never fixed — `pyprep` vs `autoreject`
RANSAC selecting different bad channels, and the 100/250 ms window-edge convention at 256 Hz.

> **A methodology document written for humans gets you to the right answer and stops the model from
> flip-flopping between incompatible analyses. It does not make the pipeline numerically reproducible.
> That requires pinning every step that moves a number.**

**4. Aggregate statistics mask per-subject irreproducibility.** Grand means are far more stable than
the per-subject values beneath them (at L1, run-to-run grand-mean spread is ~0.02 µV while individual
subjects move by up to ~0.5 µV). A group-level result can look perfectly replicable while the
per-subject values are not — which is exactly where the science lives for individual-differences work,
biomarkers, and clinical use. **Checking that a group mean replicates does not establish that a
pipeline is reproducible.**

**5. The baseline's error is "different", not "wrong".** The majority L0 subgroup chose a **P9/P10
mastoid-style reference** — if anything the *more canonical* choice for MMN in the literature — which
roughly doubles the amplitude and accounts for essentially all of its error. So certification means
**"faithful to this specification"**, not **"scientifically optimal"**. A corpus can be perfectly
certified and still encode a defensible-but-unconventional choice. (See
[`OPEN_MODEL_EVAL.md`](OPEN_MODEL_EVAL.md) for the companion result that certification is a property
of the *specification*, not of the model.)

## Honest limitations

1. **k = 9 (L0) / 12 (L1) / 3+1 (L2), one recipe (MMN), one generator family** for L0/L1 (L2 also
   spans P3, N170, GPT/Codex and an open-weight model). Better than the initial pilot but still below
   the scale an ML venue expects.
2. **This limitation bit us repeatedly — three times.** At k=3 we concluded the recipe bought *no*
   reproducibility; at k=4 that became a 4× gain; at k=5 the claim "all L0 runs chose mastoid" broke;
   at k=6 the L0 error turned out to be **bimodal**, invalidating any pooled mean. Every increase in k
   changed a headline. This is itself the most transferable methodological result here: **evaluations
   of LLM-generated analyses need k well beyond the 3–5 that feels sufficient**, and must check for
   multimodality before reporting mean±SD.
3. **Three discrete levels, not a continuum.** "Specification precision" has no natural scalar metric;
   these are three concrete conditions, not a dose-response curve.
4. **Blindness is prompt-enforced**, not sandbox-enforced (the L0/L1 divergence argues against copying).
5. **The L0 subgroup split is 7:2** — the average-reference arm has only k=2, so its subgroup statistics
   are weak; the *existence* of bimodality is solid, the *ratio* is not well estimated.
6. The certified reference is itself a *specification*, not ground truth about the brain (finding 5).

## Reproduce
```bash
# score any set of generations against the certified per-subject values
python tools/benchmark/score_recipe_generation.py --component MMN \
  --gen-dir <dir> --labels L0_1 L0_2 L0_3 L0_4 L0_5 L0_6 L0_7 L0_8 L0_9 \
                          L1_3 L1_4 L1_5 L1_6 L1_7 L1_8 L1_9 L1_10 L1_11 L1_12
```
