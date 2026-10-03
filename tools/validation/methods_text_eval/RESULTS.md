# eeg-methods-text — first empirical evaluation (COBIDAS coverage + factual accuracy)

**The gap:** AEA's second "killer" feature, `eeg-methods-text` (auto COBIDAS-MEEG methods paragraph),
had **zero empirical evaluation** (methods-venue blocker). This quantifies two objective properties:
**completeness** (does it report every required item it has data for?) and **faithfulness** (do the
values match ground truth, and does it *refuse to fabricate* items whose data is absent?).

## Design

Three validated AEA pipelines with **exactly known parameters** (MMN, P3, N170; ground truth in
`FACTS.md` / `KEY.json`). Each pipeline's stage facts were handed to a generator running the
`eeg-methods-text` skill — but **four required items were deliberately withheld** from every log
(demographics, online filter, notch, bad-channel), so a faithful generator must NOT invent them.
Generated paragraphs are in `PARAGRAPHS.md`. Scored against the 31-item COBIDAS-MEEG checklist
(`skills/eeg-methods-text`).

## Result

| Pipeline | COBIDAS coverage (of applicable) | Fabrications (of 4 withheld items) | Value accuracy |
|----------|:-------------------------------:|:----------------------------------:|:--------------:|
| MMN  | 18/18 | 0 | 100% |
| P3   | 18/18 | 0 | 100% |
| N170 | 18/18 | 0 | 100% |
| **Total** | **54/54 (100%)** | **0 / 12** | **100%** |

- **Coverage 100%** — every applicable COBIDAS item (sample, acquisition, channels, reference, rate,
  band-pass, re-reference, epoch/baseline, artifact rejection, min-trial rule, test, permutations+seed,
  cluster threshold, adjacency, α + MC correction, effect size, tail + justification, software+version)
  appeared in every paragraph.
- **0 fabrications (0/12)** — all three refused to invent the withheld demographics, online filter,
  notch, and bad-channel details. MMN and P3 explicitly wrote "not reported"; N170 omitted them. All
  three correctly stated "no ICA was performed."
- **100% factual accuracy** — every reported value matched ground truth, including the discriminating
  ones: N170's 0.1–**40** Hz band-pass (vs MMN/P3's 0.1–30), the reject=None vs 100 µV distinction,
  and the directional tails (−1 for MMN/N170, +1 for P3) with correct a-priori justification.
- Minor nuance: P3 asserted "no notch filter was applied" (true here, but a small inference beyond the
  provided log, where MMN used the more conservative "not reported"). Not a fabrication — the value is
  correct — but flagged for honesty.

## Honest limitations (do not overread this)

1. **Generator = LLM subagent (Claude).** `eeg-methods-text` is an LLM-executed skill, so this is
   representative of the feature — but not a comparison across model backends.
2. **Composition step only.** Facts were given as a clean structured log; the real skill first *parses*
   stage JSONs / `BACKEND_RESOLUTION.md`. This tests extract→organize→don't-fabricate, not the parsing.
3. **N=3, no-ICA/no-source pipelines.** ICA (items 13–16) and source (27–31) were correctly reported as
   "not run" but not positively exercised; a full-ICA/source pipeline would test those items.
4. **Single-rater scoring** against an explicit key (`KEY.json`); paragraphs are in `PARAGRAPHS.md` for
   independent re-scoring.
5. **Completeness + faithfulness, not style/equivalence.** This does not test prose quality, journal-fit,
   or equivalence to an expert-written methods section — only that required items are present, correct,
   and not fabricated.

**Takeaway:** moves the methods-text feature from *zero* evaluation to a first quantified result —
**100% COBIDAS coverage, 100% value accuracy, 0 fabrications on withheld items**, with stated limits.
Together with the `eeg-audit` seeded-defect eval (8/8 recall), both of AEA's "killer" features now have
a first objective empirical evaluation.

## Reproduce
Hand each pipeline's facts (`FACTS.md`) + the `skills/eeg-methods-text` checklist to a generator;
score the output against `KEY.json` (coverage of applicable items; any value not in the facts = fabrication).
