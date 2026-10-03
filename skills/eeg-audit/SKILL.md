---
name: eeg-audit
description: "Cross-model audit: hand the analysis plan, stats outputs, figures, and FINDINGS to an external LLM (Codex CLI, gpt-6-astra, max effort) for an INDEPENDENT verdict on whether claims are evidence-supported. Catches retro-fitting of the plan, mis-reported p-values, color-scale cherry-picking, and figure↔text inconsistencies. Mandatory before declaring the pipeline complete. Use when user says 'audit', 'verify claims', 'check my pipeline', or after all analysis stages complete."
argument-hint: "[project-dir] [— reviewer: codex-cli|codex|llm-chat] [— round: 1|2] [— focus: stats|figures|cobidas]"
allowed-tools: Bash(*), Read, Write, Grep, Glob, mcp__codex__codex, mcp__codex__codex-reply
---

# eeg-audit: independent claim verification

## Context: $ARGUMENTS

## Why this skill is non-optional

The same model that produced an analysis cannot impartially grade it — there's a documented confirmation bias even when the reviewer is a fresh context. This skill runs an **external LLM** (Codex CLI, gpt-6-astra, max effort by default) with **no prior session context** to re-check:

1. Every numeric claim in `report-stage/REPORT.md` traces to a value in `stats-stage/*.json`.
2. `ANALYSIS_PLAN.md` was frozen *before* `stats-stage/` files were written (mtime check).
3. No claim's reported direction silently flipped between plan and findings.
4. Reported p-values come with their permutation count, seed, threshold, and tail.
5. Figures don't use `jet`, asymmetric color limits on diff plots, or de-saturation that hides significance.
6. Exploratory observations are clearly labeled in the report.
7. Backend and software version information are disclosed.

## Constants

- **REVIEWER_BACKEND = `codex-cli`** (a fresh `codex exec` process, gpt-6-astra, max effort, read-only sandbox). Use `codex` only for an already configured Codex MCP connection, or `llm-chat` for a configured OpenAI-compatible proxy. Record the actual transport; do not silently substitute a model.
- **MAX_REVIEW_ROUNDS = `2`** — initial + one rebuttal/refinement.
- **VERDICT_VALUES = `pass | pass-with-caveats | revise | fail`** — per claim AND global.
- **OUTPUT_DIR = `audit-stage/`** — Create if missing.

## Required Inputs

Before running, these must exist:

1. `ANALYSIS_PLAN.md` — the frozen analysis plan.
2. `stats-stage/*.json` — per-claim statistical results.
3. `FINDINGS.md` — narrative findings.
4. `report-stage/REPORT.md` — the manuscript/report draft.
5. `figure-stage/CAPTIONS.md` — figure captions (if figures were generated).
6. `*/BACKEND_RESOLUTION.md` — backend resolution logs from each stage.

Optional but checked if present:
- `DATASET_BRIEF.md`, `erp-stage/component_measures.csv`, `figure-stage/*.png`.

## Phase A — Bundle

Collect all audit-relevant files into a structured bundle:

```
audit_bundle = {
    "plan": ANALYSIS_PLAN.md (full text),
    "stats": {claim_id: stats-stage/<claim_id>_cluster_perm.json for each},
    "findings": FINDINGS.md,
    "report": report-stage/REPORT.md,
    "captions": figure-stage/CAPTIONS.md,
    "backend_logs": [*/BACKEND_RESOLUTION.md],
    "dataset": DATASET_BRIEF.md,
    "erp_measures": erp-stage/component_measures.csv (if exists),
}
```

## Phase B — mtime verification (MACHINE CHECK, not LLM)

This is a deterministic check. Do NOT delegate to the LLM reviewer.

```bash
# Get ANALYSIS_PLAN mtime
plan_mtime=$(stat -c %Y ANALYSIS_PLAN.md)

# Check every stats-stage JSON
for f in stats-stage/*_cluster_perm.json; do
    file_mtime=$(stat -c %Y "$f")
    if [ "$plan_mtime" -gt "$file_mtime" ]; then
        echo "CRITICAL: ANALYSIS_PLAN.md was modified AFTER $f was written."
        echo "  Plan mtime: $(stat -c %y ANALYSIS_PLAN.md)"
        echo "  File mtime: $(stat -c %y $f)"
        echo "  This suggests post-hoc plan editing. Flagging as FAIL."
    fi
done

# Also check ERP measures
for f in erp-stage/component_measures.csv; do
    file_mtime=$(stat -c %Y "$f")
    if [ "$plan_mtime" -gt "$file_mtime" ]; then
        echo "WARNING: ANALYSIS_PLAN.md was modified after ERP measurements."
    fi
done
```

Write result to `audit-stage/MTIME_CHECK.json`:
```json
{
  "plan_mtime": "2026-05-20T14:32:00",
  "stats_files": [
    {"file": "C1_cluster_perm.json", "mtime": "2026-05-20T15:01:00", "plan_before_stats": true}
  ],
  "mtime_verdict": "pass"
}
```

If any file fails the mtime check, set `mtime_verdict: "fail"` and include it as a critical finding in the audit. **Do not proceed to the LLM review if the mtime check fails** — surface immediately to the user.

## Phase C — Hand off to Codex MCP reviewer

### Structured prompt template

Send the following structured prompt to the Codex MCP reviewer. The reviewer has NO prior context.

```
You are an independent EEG methods reviewer. You have been given the analysis plan, statistical results, findings, report text, and figure captions from an EEG study. Your job is to verify that every claim is evidence-supported and that the methodology is sound.

## Your audit checklist

For EACH claim row in the ANALYSIS_PLAN:

### 1. Numeric traceability
- Does the p-value in FINDINGS/REPORT match the p-value in stats-stage JSON?
- Does the effect size in FINDINGS/REPORT match the stats JSON?
- Does the number of permutations match?
- Does the seed match?
- Is the tail (one-sided vs two-sided) consistent between plan, stats, and report?

### 2. Direction consistency
- Does the direction of the effect in FINDINGS match the hypothesized direction in the plan?
- If the effect was in the OPPOSITE direction, is this clearly stated as "does not support"?
- Was the tail silently flipped between plan and execution?

### 3. Window and ROI consistency
- Do the channels/ROI in the stats JSON match the plan?
- Does the time window in the stats JSON match the plan?
- Were any channels or time points added/removed post-hoc?

### 4. Statistical methodology
- Was the cluster-forming threshold justified (not arbitrary)?
- Was the adjacency matrix reported (Delaunay, distance, template)?
- Was the bandpass filter appropriate for the time window of interest?
  (e.g., aggressive high-pass >0.5 Hz can distort slow ERPs like P3b, N400)
- Were multiple comparisons handled if there are >1 claims?
- Was an effect size reported (Cohen's d, eta-squared, etc.)?
- Was the number of permutations sufficient (>=1000, ideally 5000)?

### 5. ICA and preprocessing transparency
- Were ICA component rejection decisions documented?
- Was the number of rejected components reported per subject?
- Was channel interpolation documented (which channels, how many)?

### 6. Channel/time-window selection
- Does channel selection appear data-driven (i.e., chosen from grand average)?
- If so, flag as circular analysis (Luck & Gaspelin 2017).
- Were time windows pre-registered or literature-based?

### 7. Post-hoc exclusion
- Were any subjects excluded after seeing results?
- If so, was exclusion pre-registered with objective criteria?
- Were exclusion rates reported?

### 8. Exploratory vs confirmatory
- Are exploratory analyses clearly labeled?
- Are there findings in the report that are NOT in the analysis plan?

### 9. Figure quality (if figure files provided)
- Colormap: does any figure use `jet`? (Flag — perceptually non-uniform, misleading)
- Color scale: are difference plots symmetric around zero? (Asymmetric scales exaggerate one direction)
- Scale bars: do topoplots have color bar labels with units (µV or t-value)?
- Time axis: is the time axis labeled with stimulus onset marked?
- Waveform plots: are SEM/CI bands shown? Is the baseline period visible?

### 10. COBIDAS-MEEG compliance (Pernet et al. 2020)
Verify the methods section reports:
- [ ] Statistical test used and its implementation (software + version)
- [ ] Number of permutations and RNG seed
- [ ] Cluster-forming threshold and derivation
- [ ] Channel adjacency definition
- [ ] Alpha level and multiple-comparisons correction
- [ ] Effect size metric and formula
- [ ] Tail and justification
- [ ] Filtering parameters (bandpass, notch, filter type, order)
- [ ] Re-referencing scheme
- [ ] Epoch duration and baseline correction
- [ ] Artifact rejection criteria and rejection rates
- [ ] ICA method and component rejection criteria

### 11. Microstate analysis (only if the study reports EEG microstates)
- Were maps clustered from a SINGLE GLOBAL/GROUP template (concatenated across subjects), not fit per-recording? Per-recording (individual) template fitting has the LOWEST test-retest reliability (Khanna et al. 2014, Cronbach alpha ~0.52) — flag it. Global maps give alpha > 0.8.
- Number of clean data per recording: was it >= ~180 s (and at minimum ~120 s)? Khanna 2014 used ~128 s (range 80-204 s). Flag recordings with < ~120 s of post-preprocessing clean data as unreliable.
- Channel count: >= 20 EEG channels with full-head coverage and a montage? Core features (duration, occurrence, coverage) are recoverable down to 19/8 channels (alpha 0.87-0.91), but microstates C and D are slightly less consistent at low density — flag reduced C/D reliability if < ~30 channels.
- Reference: was the average reference applied before clustering? (Required — microstate topographies are reference-dependent.)
- Bad channels: were they interpolated/removed before clustering (none left in)?
- Number of maps K and GEV: for the canonical K=4, is reported global explained variance in the ~65-78% range (Khanna 2014; cf. eeg-microstate which warns below 0.60)? GEV far below ~0.60 suggests too few maps or noisy data; GEV implausibly high may indicate overfitting/too many maps.
- Polarity: was polarity ignored (spontaneous/resting microstates are polarity-invariant)?
- GFP-peak fitting: were template maps clustered on GFP peaks (not all time points)? Fitting on all samples inflates GEV and yields unstable maps.

### 12. Source localization (only if the study reports source estimates)
- Reference: was EEG common-average referenced BEFORE the forward model? This is a hard requirement — a non-average reference biases the EEG forward solution. FAIL source claims that lack an average reference.
- Co-registration: was a real head<->MRI transform used? For the fsaverage template path, the bundled `trans='fsaverage'` transform with a standard montage is acceptable (~5-10 mm localization error — document and downgrade to ROI/lobar claims). FAIL only if source localization ran with an *unintended* identity trans on a non-template setup, an unset/zero montage, or no trans at all.
- Was the co-registration fit visually verified (`mne.viz.plot_alignment(..., surfaces='head-dense')`) so sensors sit on the scalp, not floating above or sunk below it?
- Head model & electrodes: if a TEMPLATE BEM (fsaverage / standard_bem) with TEMPLATE electrode positions (standard_1020/1005) and no individual MRI / no digitized electrodes were used, are spatial claims restricted to coarse ROI / lobar / network level? Flag any voxel-precise or millimetre-precise peak claim as overstated.
- Channel density: is the montage >= ~32 channels (ideally 64-256)? Low-density (< 32 ch) montages give poor depth and spatial resolution — downgrade fine-grained localization claims.
- Inverse method & params: is the inverse operator (MNE/dSPM/sLORETA/eLORETA/beamformer), noise covariance source, depth weighting, and loose/orientation constraint reported?

## Output format

Return a JSON object:
{
  "claims": [
    {
      "claim_id": "C1",
      "claim_text": "...",
      "verdict": "pass | pass-with-caveats | revise | fail",
      "issues": [
        {"severity": "critical | major | minor", "category": "...", "description": "..."}
      ]
    }
  ],
  "figure_issues": [
    {"figure": "fig1.png", "issue": "...", "severity": "major | minor"}
  ],
  "cobidas_missing": ["list of missing COBIDAS items"],
  "microstate_issues": [
    {"check": "template_strategy | min_duration | channel_count | average_reference | gev_range", "severity": "critical | major | minor", "description": "..."}
  ],
  "source_localization_issues": [
    {"check": "average_reference | coregistration | template_bem_overclaim | channel_density | inverse_params", "severity": "critical | major | minor", "description": "..."}
  ],
  "global_verdict": "pass | pass-with-caveats | revise | fail",
  "summary": "1-3 sentence summary",
  "action_items": [
    {"priority": 1, "action": "...", "affects": ["C1", "report"]}
  ]
}
```

### Invocation pattern

**Default: Codex CLI.** Install and sign in to Codex CLI using the
[reviewer setup in Getting started](../../docs/GETTING_STARTED.md#configure-the-reviewer).
This route works from either a Codex or Claude Code analysis session; it does not
require an MCP server.

1. Save the complete Phase C reviewer prompt and Phase A audit bundle to
   `<project-dir>/audit-stage/REVIEW_PROMPT.md`. Include the Phase B machine-check
   result. This file supplies the review context; do not pass the analysis agent's
   conversation or ask the reviewer to invoke `eeg-audit` recursively.
2. Run a new process from the repository root with the following arguments,
   replacing the study path. Do not use `resume` for the initial independent review.

```bash
codex exec -m gpt-6-astra -c 'model_reasoning_effort="max"' --sandbox read-only --json -o projects/my-study/audit-stage/REVIEW_RESPONSE.md "Read projects/my-study/audit-stage/REVIEW_PROMPT.md and perform only that read-only review. Return the requested audit JSON. Do not edit files or launch another reviewer." < /dev/null
```

3. Launch with stdin closed (`< /dev/null` in Bash, or `stdin=subprocess.DEVNULL`
   when launching through Python on any platform). Save stdout to
   `audit-stage/reviewer.events.jsonl` and stderr to `audit-stage/reviewer.stderr.log`.
   If running in the background, save the actual process PID to
   `audit-stage/reviewer.pid`, keep the supervising process alive, wait for it, and
   save its exit code to `audit-stage/reviewer.exit`. Manage that process by PID.
4. Require exit code 0, a nonempty response, and valid JSON matching the requested
   verdict fields before Phase D. Authentication, model-access, or execution errors
   mean the audit is incomplete; report the error and retain the logs. Do not turn
   an unavailable reviewer into a passing verdict. Record the thread ID from the
   event stream and the selected model/effort with the audit output.

**Existing MCP connection (`reviewer: codex`).** If the client already exposes
these tools, send the same prompt and bundle with the configured model, effort,
and read-only sandbox:

```text
mcp__codex__codex(prompt=structured_prompt + audit_bundle_text)
mcp__codex__codex-reply(thread_id=...)
```

The CLI route above is the setup path for a fresh installation. An existing
`llm-chat` route requires its own configured endpoint and credentials.

## Phase D — Parse verdict and write outputs

### `audit-stage/AUDIT.json`

The raw JSON verdict from the reviewer, augmented with:
```json
{
  "audit_round": 1,
  "reviewer_backend": "codex-cli (gpt-6-astra, max effort)",
  "mtime_check": "pass",
  "reviewer_verdict": { ... },
  "timestamp": "2026-05-22T10:00:00Z"
}
```

### `audit-stage/AUDIT.md`

Human-readable audit report:

```markdown
# EEG Pipeline Audit — Round 1
**Date**: 2026-05-22
**Reviewer**: Codex CLI (gpt-6-astra, max effort; record actual transport)
**Global verdict**: pass-with-caveats

## mtime check
- ANALYSIS_PLAN.md: 2026-05-20T14:32:00
- All stats files written after plan: YES

## Per-claim verdicts

### C1: [claim text]
- Verdict: **pass**
- Issues: none

### C2: [claim text]
- Verdict: **pass-with-caveats**
- Issues:
  - [major] Effect size not reported in methods section
  - [minor] Peak latency used instead of fractional area latency

## Figure issues
- fig1.png: [minor] Missing color bar units

## COBIDAS-MEEG compliance
- Missing: effect size formula, ICA component rejection criteria

## Action items (priority order)
1. Add Cohen's d formula to methods section [affects: report]
2. Add ICA rejection summary table [affects: report, supplementary]
3. Add µV label to fig1 color bar [affects: fig1]
```

### Verdict-to-action routing

| Global verdict | Action |
|---|---|
| `pass` | Pipeline complete. Proceed to submission prep. |
| `pass-with-caveats` | Surface caveats to user. Pipeline can proceed if user acknowledges. |
| `revise` | Surface specific fixes. User or re-run of analysis stages must address them. **This skill does NOT auto-edit results.** |
| `fail` | **Stop the pipeline.** Critical integrity issue (e.g., mtime violation, direction flip, p-value mismatch). Must be resolved before any further steps. |

## Phase E — Re-audit protocol (Round 2)

If the user fixes issues and requests a re-audit (`— round: 2`):

1. **Re-run mtime check** — the plan should still predate all stats files. If the user edited the plan to match results, this is a new mtime violation.
2. **Diff the bundle** — compare the current bundle against `audit-stage/AUDIT_ROUND1_BUNDLE.md` (saved during round 1). Identify what changed.
3. **Send to Codex** with an augmented prompt:
   ```
   This is a RE-AUDIT (round 2). The previous audit found the following issues:
   [paste round 1 action items]

   The following files were modified since round 1:
   [diff summary]

   Verify that:
   1. Each action item from round 1 has been addressed.
   2. No NEW issues were introduced by the fixes.
   3. The fixes did not alter any statistical results (re-check all p-values).
   ```
4. **Write** `audit-stage/AUDIT_ROUND2.json` and `audit-stage/AUDIT_ROUND2.md`.
5. If round 2 verdict is still `revise` or `fail`, **do not auto-trigger round 3**. Surface to user with explanation.

### What changes between audit rounds

| Aspect | Round 1 | Round 2 |
|---|---|---|
| Prompt | Full audit checklist | Focused on round 1 action items + regression check |
| mtime check | Initial check | Re-check + verify no plan edits |
| Bundle | Full | Full + diff from round 1 |
| Expected outcome | Identify all issues | Verify fixes, catch regressions |
| Max rounds | 2 (configurable) | No auto-round-3 |

## Common EEG reviewer concerns (distilled from real peer reviews)

These are the most frequent methodological criticisms in EEG paper reviews. The audit explicitly checks for each:

### Statistical concerns
1. **Cluster-forming threshold not justified** — "Why alpha=0.05 for cluster formation? This is arbitrary." Reviewers expect justification (e.g., based on df) or use of TFCE which avoids threshold selection.
2. **Adjacency matrix not reported** — "How were channel neighbors defined?" Must state: Delaunay triangulation, distance-based (radius in mm), or template-based.
3. **Multiple comparisons not handled** — Running 5 claims at alpha=0.05 without correction. Even if each uses cluster permutation (which controls FWER within a test), testing multiple claims inflates the overall false positive rate.
4. **Effect size not reported** — "No effect size is reported, making it impossible to judge practical significance." Cohen's d or partial eta-squared is expected.
5. **Post-hoc exclusion not pre-registered** — "3 subjects were excluded for 'excessive artifacts' but no objective criterion is stated."

### Preprocessing concerns
6. **Bandpass too aggressive for time window** — A 1 Hz high-pass filter distorts ERP components slower than ~200 ms (P3, N400, LPP). Tanner et al. (2015) showed 0.1 Hz is safer for slow ERPs.
7. **ICA decisions not transparent** — "How were artifactual components identified? How many were rejected per subject?" Reviewers expect: method (manual, ICLabel, MARA), number rejected (mean +/- SD), criteria.
8. **Channel selection appears data-driven** — "The ROI appears to be chosen from the grand average topomap." This is circular (Luck & Gaspelin 2017).

### Reporting concerns
9. **Trial counts not reported per condition per subject** — Essential for judging ERP quality.
10. **Baseline correction window not stated** — Must report: window (e.g., -200 to 0 ms), method (subtractive).
11. **Filter settings incomplete** — Must report: passband, filter type (FIR/IIR), order/transition bandwidth, causal vs zero-phase.

### Figure concerns
12. **Jet colormap** — Perceptually non-uniform; creates artificial boundaries. Use `RdBu_r`, `viridis`, or `coolwarm`.
13. **Asymmetric color scales on difference topoplots** — e.g., -2 to +5 µV exaggerates the positive direction. Always use symmetric limits (e.g., -3 to +3).
14. **Missing scale bars** — Topoplots without color bar labels, or waveform plots without µV scale.
15. **No baseline period shown** — ERP waveform plots should show the pre-stimulus baseline.

## COBIDAS-MEEG checklist (Pernet et al. 2020, Nature Neuroscience)

The audit verifies these items are reported in the methods section. Each item is tagged as present, absent, or partial:

### Data acquisition
- [ ] EEG system (manufacturer, model)
- [ ] Number of channels and montage
- [ ] Sampling rate
- [ ] Online reference and ground
- [ ] Impedance threshold

### Preprocessing
- [ ] Offline re-reference scheme
- [ ] Filter type, passband, order/transition bandwidth
- [ ] Notch filter (if applied)
- [ ] Downsampling (if applied, with anti-aliasing filter)
- [ ] Epoch duration and event-locking
- [ ] Baseline correction window and method
- [ ] Artifact rejection method and criteria
- [ ] Artifact rejection rates (mean, range)
- [ ] ICA method, number of components removed (mean, range), identification criteria
- [ ] Channel interpolation (method, number per subject)
- [ ] Trial counts per condition per subject (mean, range)

### Analysis
- [ ] Statistical test and software (name + version)
- [ ] Number of permutations and RNG seed
- [ ] Cluster-forming threshold and derivation
- [ ] Channel adjacency matrix definition
- [ ] Alpha level and tail justification
- [ ] Multiple-comparisons correction (if multiple claims)
- [ ] Effect size metric and formula
- [ ] Time window and ROI with justification (literature or pre-registration)

## Domain knowledge (audit-relevant, with citations)

- **Microstate template strategy drives reliability.** A single GLOBAL/group template (maps clustered from data concatenated across subjects/recordings) yields high test-retest reliability (mean Cronbach alpha > 0.8, SEM ~10% of the mean), whereas fitting maps per individual recording is the LEAST reliable strategy (alpha ~0.52). Audit should prefer group/global templates and flag per-recording fitting. (Khanna et al. 2014, *Neurosci Biobehav Rev*, "Microstates in resting-state EEG: current status and future directions".)
- **Microstate data requirements.** Resting-state, full-head montage with >= 20 electrodes, average reference, no bad channels (interpolate/remove first), and >= ~3 min (warn below ~2 min) of clean post-preprocessing data. Khanna 2014 used ~128 s (range 80-204 s). Core features (duration, occurrence, coverage) are reliably recovered down to 19 and even 8 channels (alpha 0.87-0.91), but microstates C and D are slightly less consistent than A and B at low density. (Khanna et al. 2014.)
- **Microstate K=4 GEV range.** Four canonical maps explain ~65-78% of global field power variance (GEV) in healthy resting EEG; ~70% is typical. Values far below this floor indicate too few maps or noisy data (the eeg-microstate skill warns below 0.60). (Khanna et al. 2014; cf. Murray et al. 2008, *Brain Topogr*, for the GEV definition.)
- **Average reference is mandatory for EEG source localization.** A non-average reference biases the EEG forward model; common-average referencing before computing the leadfield is a hard methodological gate, not a stylistic choice. (Michel & Brunet 2019, *Front Neurol*, "EEG source imaging: a practical review of the analysis steps.")
- **Co-registration is a fitted, verified step — not an unintended identity transform.** Sensor positions must be aligned to the head/MRI via fiducials then refined (MNE: `Coregistration.fit_fiducials()` then `fit_icp()`, or the bundled `trans='fsaverage'` for the template head). Template-electrode fits are imperfect (electrodes sink below or float above the scalp) and must be eyeballed with `mne.viz.plot_alignment(..., surfaces='head-dense')`. An *unintended* identity trans on a non-template setup or an unset montage means co-registration never happened — but the documented `trans='fsaverage'` template path is legitimate (introduces ~5-10 mm error; restrict to ROI/lobar claims). (Michel & Brunet 2019; MNE coregistration docs; cf. eeg-source.)
- **Template-BEM EEG source results are approximate.** Template BEM (fsaverage/standard_bem) + template electrodes (standard_1020/1005) with no individual MRI and no digitized electrodes support only coarse ROI/lobar/network-level localization, never voxel-precise peaks; conductivity and geometry errors are large for EEG. Higher electrode density (64-256) and digitized positions + individual MRI are required for finer spatial claims; low-density (< 32 ch) montages give poor depth/spatial resolution. (Michel & Brunet 2019.)

## Forbidden behaviors

- Do not let the same Claude session that produced the analysis act as the reviewer. Always invoke an external LLM.
- Do not edit any file in `stats-stage/`, `erp-stage/`, `epoch-stage/`, or `figure-stage/` based on the audit. The audit produces a verdict; the user (or a re-run of the analysis with corrected plan) produces the fix.
- Do not auto-trigger round 3 if round 2 still fails. Surface to user.
- Do not mark a claim as `pass` if the mtime check failed for that claim's stats file.
- Do not skip the mtime check — it is the single most important integrity safeguard.
- Never mark a source-localization claim `pass` if the EEG was not common-average referenced before the forward model, or if it ran with an unset montage / an *unintended* identity trans on a non-template setup. These are integrity-level failures, not caveats. (The bundled `trans='fsaverage'` transform with a standard montage is the documented template path — acceptable, but downgrade to ROI/lobar claims.)
- Never let a source-localization study built on a template BEM + template electrode positions (no individual MRI, no digitized electrodes) report voxel- or millimetre-precise peaks. Downgrade such claims to coarse ROI/lobar/network level.
- Never mark a microstate study `pass` if maps were fit per-recording (individual) rather than from a single global/group template — flag the reliability concern (Khanna et al. 2014, alpha ~0.52) regardless of the reported result.

## Failure Modes

| Symptom | Action |
|---|---|
| ANALYSIS_PLAN missing | Stop. Cannot audit without the plan. |
| stats-stage/ empty | Stop. Nothing to audit. |
| mtime violation detected | Flag as FAIL. Surface immediately — do not proceed to LLM review. |
| Codex MCP unavailable | Fall back to `llm-chat` if configured. Otherwise stop and report. |
| Reviewer returns malformed JSON | Parse what is possible. Log the raw response. Ask for re-review if critical fields missing. |
| Round 2 introduces new issues | Report new issues alongside unresolved ones. Do not auto-fix. |
| Report text mentions results not in any stats JSON | Flag as "unreported analysis" — may be exploratory results not labeled as such. |
| Source results present but no average reference applied | Flag as FAIL — biased forward model. Do not pass source claims. |
| Source localization ran with an unintended identity trans (non-template) or unset montage | Flag as FAIL — no valid sensor-to-head mapping. Co-registration was never done. (The bundled `trans='fsaverage'` + standard montage is the legitimate template path, not a violation.) |
| Source study uses template BEM + template electrodes, claims voxel-precise peaks | Downgrade to ROI/lobar/network level; flag overstated spatial precision. |
| Low channel count (< 32) for source localization | Flag — poor depth/spatial resolution; downgrade fine-grained claims. |
| Microstate maps fit per-recording instead of group/global template | Flag low test-retest reliability (Khanna et al. 2014, alpha ~0.52); recommend group/global template. |
| Microstate recording < ~120 s clean, or < 20 channels, or no average reference | Flag as unreliable precondition violation; warn results may not replicate. |
| K=4 microstate GEV reported far below ~0.60 (or implausibly high) | Flag — too few/noisy maps (low) or overfitting/too many maps (high); expected ~65-78% (Khanna 2014). |

## Cross-references

- Inputs: `ANALYSIS_PLAN.md`, `stats-stage/*.json`, `FINDINGS.md`, `report-stage/REPORT.md`, `figure-stage/CAPTIONS.md`, `*/BACKEND_RESOLUTION.md`, `DATASET_BRIEF.md`, `erp-stage/component_measures.csv`
- Outputs: `audit-stage/AUDIT.md`, `audit-stage/AUDIT.json`, `audit-stage/MTIME_CHECK.json`, `audit-stage/AUDIT_ROUND1_BUNDLE.md`
- Next: If `pass` or `pass-with-caveats` → pipeline complete, proceed to submission. If `revise` → user fixes, then `/eeg-audit — round: 2`. If `fail` → pipeline halted.
