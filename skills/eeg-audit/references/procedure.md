## Why this skill is non-optional

The same model that produced an analysis cannot impartially grade it — there's a documented confirmation bias even when the reviewer is a fresh context. This skill runs an **external LLM** through the approved configured connection with **no prior session context** to re-check:

1. Every numeric claim in `report-stage/REPORT.md` traces to a value in `stats-stage/*.json`.
2. The run used the approved plan, supported by the existing approved snapshot and approval/execution records. Missing evidence is reported as unverified, not inferred from file timestamps.
3. No claim's reported direction silently flipped between plan and findings.
4. Reported p-values come with their permutation count, seed, threshold, and tail.
5. Figures don't use `jet`, asymmetric color limits on diff plots, or de-saturation that hides significance.
6. Exploratory observations are clearly labeled in the report.
7. Backend and software version information are disclosed.

## Continuous delivery checks

Use the same approved ordered operations for execution and source-data checks.
The public `check_outputs` checker recomputes only the quantities named in its
`coverage`. For GFP/PSD require the corresponding processing checks when full
verification is requested; for Hilbert matrices inspect the actual band labels
in `hilbert_matrices_recomputed`. An empty list or
`approved_processing_recomputed=false` records absent coverage, even if the
structural `passed` result is true. These shared-helper checks are not independent
numerical certification. Do not turn a missing key or a tool error into a claimed
scientific limitation, or omit a required check because another check passed.

Check the actual final report JSON using `--report`, including its explanation,
and use real selected channel names and the requested saved interval. Recompute
band summaries only under explicit absolute/relative and aggregation choices;
do not reinterpret an ambiguous plan to improve a score.

For semantic/image review use the
[complete context builder](../../../tools/prepare_analysis_review.py). It retains
the saved explanation, final JSON and complete final message, while numeric
values remain the direct checker's responsibility. Retain disputed verdicts and
their actual context; preparing corrected context does not regrade a frozen run.

## Constants

- **REVIEWER_BACKEND** — read the already approved connection/model from the resolved run settings or existing explicit session authorization; record it before launch. Supported transports are `codex-cli`, existing `codex` MCP and configured `llm-chat`. No selected target or missing access means an incomplete review, not permission to substitute another model. See [run settings](../../../docs/RUN_SETTINGS.md).
- **MAX_REVIEW_ROUNDS = `2`** — initial + one rebuttal/refinement.
- **VERDICT_VALUES = `pass | pass-with-caveats | revise | fail`** — per claim AND global.
- **OUTPUT_DIR = `audit-stage/`** — Create if missing.

## Phase A — Bundle

Collect all audit-relevant files into a structured bundle:

```
audit_bundle = {
    "plan": ANALYSIS_PLAN.md (full text),
    "approval_sources": existing approved snapshot and approval/run records (if retained),
    "stats": {claim_id: stats-stage/<claim_id>_cluster_perm.json for each},
    "findings": FINDINGS.md,
    "report": report-stage/REPORT.md,
    "captions": figure-stage/CAPTIONS.md,
    "backend_logs": [*/BACKEND_RESOLUTION.md],
    "dataset": DATASET_BRIEF.md,
    "erp_measures": erp-stage/component_measures.csv (if exists),
}
```

## Phase B — Plan provenance and consistency (direct check)

Compare the run's plan to the already retained approved snapshot and inspect
the actual approval and run-start records. A directory name, a drafted plan,
or an earlier filesystem timestamp is not an approval. Do not create evidence
retroactively just to pass this check.

Use [the direct comparison tool](../../../tools/check_plan_provenance.py) with
the existing evidence paths and timestamps extracted from those records:

```bash
python tools/check_plan_provenance.py --plan <run-dir>/ANALYSIS_PLAN.md --approved-plan <existing-approved-snapshot> --approval-record <existing-approval-record> --analysis-record <existing-run-record> --approved-at <recorded-approval-time-with-timezone> --analysis-started-at <recorded-start-time-with-timezone> --out <run-dir>/audit-stage/PLAN_PROVENANCE.json
```

The tool compares contents directly and checks the supplied time ordering; it
does not authenticate records or determine whether a user actually approved
their contents. Retain and inspect those sources. Optional `--outputs` paths
add mtime observations, using Python on Linux, Windows and macOS. There is no
GNU `stat` requirement and mtime does not determine the status.

- `consistent`: supplied snapshot matches and recorded approval precedes the
  analysis, with the evidence paths retained. Report the limited scope of this
  consistency check alongside the actual approval evidence.
- `unverified`: an approved snapshot, approval/run record or recorded time is
  missing. Omit absent arguments rather than inventing values. Continue the
  independent numerical/report checks; do not describe plan freezing as verified.
- `needs_review`: the supplied plan differs or the recorded approval is later.
  Inspect the actual content/history. A discrepancy needs explanation, not an
  automatic misconduct finding. A genuine unapproved scientific change remains
  a substantive finding once established.

Copying an unchanged plan can update its mtime. Conversely, an early mtime does
not prove approval. Include `PLAN_PROVENANCE.json` and the sources in the review
bundle; never stop numerical checks solely because of mtime order.

## Phase C — Hand off to the configured reviewer

### Structured prompt template

Send the following structured prompt through the approved reviewer connection.
The reviewer has no prior analysis-session context. Resolve `reviewer` from the
saved run controls and check only the selected transport before launching:

```python
from pathlib import Path
import runpy
select_reviewer = runpy.run_path(str(Path(AEA_ROOT) / "tools/run_settings.py"))["select_reviewer"]
reviewer = select_reviewer(run_controls, available_transports=detected_transports)
```

`detected_transports` contains connections the client actually found. Availability
alone does not establish authorization, authentication or successful review;
retain the configured model and actual execution/response checks below.

```
You are an independent EEG methods reviewer. You have been given the analysis plan, statistical results, findings, report text, and figure captions from an EEG study. Your job is to verify that every claim is evidence-supported and that the methodology is sound.

## Your audit checklist

For EACH claim row in the ANALYSIS_PLAN:

Read the direct plan-consistency result and its source records. Record absent
approval evidence as unverified. Do not infer approval or post-hoc plan editing
from mtime, and do not treat the comparison tool as authentication. Numerical
matches must be checked directly; use review for interpretation and context.

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

**Selected Codex CLI route.** Install and sign in to Codex CLI using the
[reviewer setup in Getting started](../../../docs/GETTING_STARTED.md#configure-the-reviewer).
This route works from either a Codex or Claude Code analysis session; it does not
require an MCP server. Use this route when it is the approved selection. The
command below illustrates the previously documented model/effort; substitute
the actual approved settings, not a newly chosen model. The run-settings loader
does not establish access or execute this command.

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

Use the setup for the actually selected route. A selected `llm-chat` connection
uses its configured endpoint and credentials and does not require Codex CLI.

## Phase D — Parse verdict and write outputs

### `audit-stage/AUDIT.json`

The raw JSON verdict from the reviewer, augmented with:
```json
{
  "audit_round": 1,
  "reviewer_backend": "actual selected transport, model and effort",
  "plan_provenance": "consistent | unverified | needs_review",
  "reviewer_verdict": { ... },
  "timestamp": "2026-05-22T10:00:00Z"
}
```

### `audit-stage/AUDIT.md`

Human-readable audit report:

```markdown
# EEG Pipeline Audit — Round 1
**Date**: 2026-05-22
**Reviewer**: [actual selected transport, model and effort]
**Global verdict**: pass-with-caveats

## Plan provenance
- Approved snapshot and approval/run records: [actual paths]
- Direct consistency status: [consistent / unverified / needs_review]
- Scope and unresolved evidence: [actual findings; mtime alone is insufficient]

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
| `fail` | **Stop the affected pipeline.** An established critical issue (e.g., an unapproved scientific change, direction flip or p-value mismatch) must be resolved. A timestamp discrepancy alone does not establish such an issue. |

## Phase E — Re-audit protocol (Round 2)

If the user fixes issues and requests a re-audit (`— round: 2`):

1. **Re-check plan provenance** — compare the actual plan/content and approval/run records. Identify approved amendments versus unexplained changes; copied-file mtime is not proof of a new violation.
2. **Diff the bundle** — compare the current bundle against `audit-stage/AUDIT_ROUND1_BUNDLE.md` (saved during round 1). Identify what changed.
3. **Send to the same approved reviewer connection/model** with an augmented prompt:
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
| Plan provenance | Compare existing approval/run evidence | Compare content changes and amendment records; no timestamp-only verdict |
| Bundle | Full | Full + diff from round 1 |
| Expected outcome | Identify all issues | Verify fixes, catch regressions |
| Max rounds | 2 (configurable) | No auto-round-3 |

## Failure Modes

| Symptom | Action |
|---|---|
| ANALYSIS_PLAN missing | Stop. Cannot audit without the plan. |
| stats-stage/ empty | Stop. Nothing to audit. |
| Plan mtime is later than output mtime | Record the observation and inspect existing approval/run evidence; copying can cause it. Continue independent checks and do not infer misconduct from this alone. |
| Approval evidence missing or plan differs | Report unverified/needs_review with actual sources; inspect content and amendments. Do not fabricate an approval or mark the freezing claim verified. |
| Selected reviewer transport unavailable | Keep the review incomplete, preserve the error and identify the selected connection/model. Do not switch automatically. An unavailable unselected Codex MCP does not block a selected CLI or llm-chat connection. |
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
