# eeg-audit — first empirical evaluation (seeded-defect detection)

**The gap:** AEA's two "killer" features (the auto COBIDAS methods text and the hostile-Reviewer-2
`eeg-audit`) had **zero empirical evaluation** — a methods-venue blocker flagged by the cross-model
review. This is a first, objective evaluation of the **`eeg-audit` reviewer's detection capability**.

## Design

9 short ERP "Methods & Results" summaries: **1 clean control (C0) + 8 each carrying exactly one
known EEG methodological defect** (mapped to the `eeg-audit` SKILL.md checklist; see `CASES.md`,
ground truth in `KEY.json`). Each case was handed to a **blind auditor** — given only the checklist
and one case, unaware a defect was seeded — which wrote a Reviewer-2 memo. Scored for:
- **Recall** — did the memo flag the seeded defect?
- **Specificity** — did the memo avoid fabricating a critical flaw on the clean control?

## Result

| Case | Seeded defect | Detected | Severity | Verdict |
|------|---------------|:--------:|----------|---------|
| C0 | *(clean control)* | ✓ passed | none critical | pass-with-caveats |
| C1 | circular analysis / double-dipping | ✓ | CRITICAL | revise |
| C2 | no multiple-comparisons correction | ✓ | CRITICAL | fail |
| C3 | post-hoc outcome-based exclusion | ✓ | CRITICAL | fail |
| C4 | 1.0 Hz high-pass distorting a slow N400 | ✓ | CRITICAL | revise |
| C5 | no baseline correction | ✓ | MAJOR (top) | revise |
| C6 | underspecified cluster test | ✓ | CRITICAL | revise |
| C7 | rejection rates omitted + unequal N | ✓ | CRITICAL | revise |
| C8 | EEG reference never reported | ✓ | CRITICAL | revise |

- **Recall = 8/8 (100%)** — every seeded defect flagged, 7/8 as CRITICAL (C5 top-ranked MAJOR).
- **Specificity** — the clean control C0 was **not** failed (pass-with-caveats); the auditor stated
  "I found no critical flaw" and raised only reporting-completeness items. No manufactured critical flaw.
- Each auditor also explicitly credited the sound aspects (filter/baseline/pre-registration) rather than
  over-flagging — a good sign it isn't reflexively hostile.

## GPT/Codex-backend confirmation (2026-07-12) — the shipped-feature test

The production `eeg-audit` feature uses **GPT/Codex** as the reviewer (a *different* model grades the
work). Re-running the same 9 cases on that backend — **relabeled and shuffled** (so "clean" was not
obvious) and audited in one neutral-framed pass — reproduced the Claude result exactly:

- **Recall = 8/8** (GPT flagged every seeded defect: circular→fail, no-MC→fail, post-hoc-exclusion→fail,
  1 Hz-HP→fail, no-baseline→revise, underspecified-cluster→revise, rejection/imbalance→fail, no-reference→revise).
- **Specificity ✓** — the clean control, hidden among 8 flawed submissions, was rated **"sound — no
  critical flaw."** No over-flagging despite the adversarial batch.

So both a blind Claude auditor and the shipped GPT backend achieve 8/8 recall + clean-control specificity.

## Honest limitations (do not overread this)

1. **Two backends confirmed; design difference in the GPT run.** The blind-Claude run was one auditor
   per case; the GPT run presented all 9 relabeled/shuffled cases in one call (neutral framing). It did
   not over-flag (the clean case passed), but this is a batched, not strictly per-case-blind, confirmation.
2. **Textbook defects, N=9.** Self-constructed, one canonical defect per case — relatively detectable.
   Real submissions carry subtler and compound problems.
3. **Single-rater scoring** against an explicit key (the author); judgments are transparent (each
   memo's flagging line is quoted in `RESULTS.json`).
4. **Text summaries, not the full bundle.** The real `eeg-audit` ingests `ANALYSIS_PLAN` + stats JSON +
   figures + a deterministic mtime check; this evaluates the *checklist-detection reasoning* only.
5. **One clean control** — a larger clean set would better bound the false-positive/over-flagging rate.

**Takeaway:** this moves the reviewer feature from *zero* evaluation to a quantified result confirmed
on **both** backends — **8/8 seeded-defect recall + clean-control specificity**, for a blind Claude
auditor *and* the shipped GPT/Codex backend. It does not yet cover subtle/compound defects or
comparison against real reviewer comments.

## Reproduce
Cases + key are in `CASES.md` / `KEY.json`; re-run by handing each case + the `skills/eeg-audit`
checklist to an auditor (blind), scoring flags against `KEY.json`. For the shipped feature, use the
Codex backend as the auditor.
