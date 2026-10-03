---
name: eeg-recipe
description: "Run a published EEG analysis recipe end-to-end on user data. Validates data shape against recipe requirements, instantiates ANALYSIS_PLAN.md from the recipe, runs the full pipeline (preprocess → ICA → epoch → ERP/TFR → stats → figure → report → audit), and emits citation.bib for the source paper. THE flagship skill that makes recipes possible. Use when the user says \"run recipe X\", \"reproduce paper Y\", \"apply N170 recipe to my data\", or names a recipe slug."
argument-hint: "[recipe-slug] --data [project-dir] [— marker-map: target=1,standard=2] [— skip-audit] [— version: v0.2]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Skill
---

# eeg-recipe: run a published EEG analysis recipe

The flagship skill. Takes a recipe slug + a data directory, produces a paper-ready figure + COBIDAS-compliant methods text + reproducibility receipt.

## Context: $ARGUMENTS

## Constants

- **RECIPES_DIR = `recipes/`** (relative to repo root).
- **AUTO_PROCEED = `false`** — pause after data-shape validation; user must confirm before pipeline runs.
- **SKIP_AUDIT = `false`** — audit runs by default; override only for quick exploration.
- **RECIPE_VERSION_FILE = `<project-dir>/RECIPE_VERSION.json`** — tracks recipe version history.

## Phases

### A. Recipe lookup + validation

1. Resolve the recipe slug to `recipes/<slug>/RECIPE.md`. If missing, list available recipes and ask the user.
2. Parse `RECIPE.md`'s YAML frontmatter. **Required metadata**, matching `recipes/_template/RECIPE.md`:
   ```yaml
   ---
   recipe: <slug>
   version: "0.1.0"                # a leading v is also accepted
   paradigm: <human-readable paradigm description>
   status: <experimental|validated|canonical>
   references:
     - "<Author et al. (Year). Title. Journal.>"
   contributors:
     - "<Contributor name>"
   license: CC-BY-4.0
   ---
   ```
3. **Validate YAML frontmatter**:
   - All required fields present. If any missing, stop and report which fields need to be added.
   - `version` follows semantic versioning, with an optional leading `v` (e.g., `0.1.0`, `v0.1.1`). Preserve the declared spelling in run records.
   - `status` is one of: `experimental`, `validated`, `canonical`. Do not change a recipe's status when running it.
   - `paradigm` is a description, not an enum used to select the pipeline.
   - `references` is a non-empty list.
4. **Read data requirements** from the frontmatter, where present, and the `What this recipe needs` section. Fields such as `min_channels`, `min_sfreq`, `min_trials_per_condition`, `min_duration_s`, and `required_markers` are structured summaries, not mandatory keys in every recipe. The body supplies channel names, condition-specific minima, required versus optional markers, and continuous-recording requirements. Preserve these distinctions; a recommended sample size is not a required minimum. If the two sources conflict, report the conflict and resolve it with the user before analysis; do not choose new scientific settings silently.
5. **Verify validation dataset** (optional for running on user data):
   - If `validation_dataset` is specified, check it exists (as a path or a known dataset name).
   - If it does not exist, warn: "Recipe validation dataset not found. Results cannot be compared against reference."
   - If it exists, note it for Phase F (figure comparison).
6. Print the recipe's plain-language description and its data requirements.

### B. Auto-brief + data-shape validation

1. Read user-provided `--data <project-dir>`.
2. If `DATASET_BRIEF.md` does not exist AND `raw/` directory exists:
   - Run `python tools/auto_brief.py --raw-dir <project-dir>/raw/ --out <project-dir>/DATASET_BRIEF.md --json <project-dir>/auto_brief_scan.json`
   - This auto-fills: channels, sampling rate, format, event codes, acquisition system guess, data path.
   - Read the generated brief. Identify remaining `[USER]` fields.
   - **Ask the user only the essential questions conversationally** (do NOT dump the whole template):
     a. "Detected markers {11, 12, 21, 22} — what does each code mean?" (or confirm recipe default mapping)
     b. Any recipe-specific data requirements that couldn't be verified from the header.
   - Fill in the user's answers, remove `[USER]` tags from answered fields.
3. If `DATASET_BRIEF.md` already exists, read it and check for remaining `[USER]` placeholders — ask about those.
4. Verify against recipe requirements:
   - Required channels are present in the user's data.
   - Required marker codes are present in the events. If user has different codes, accept `— marker-map: target=1,standard=2` to translate.
   - Sampling rate meets recipe minimum (after planned resample).
   - Per-condition trial counts likely meet minimum (estimate from event counts).
   - For continuous recipes without per-trial markers, check recording duration and any required state annotations instead of event counts. Use the recipe's own minimum duration and segmentation requirements.
5. If any check fails, surface the precise mismatch and stop. Do NOT proceed silently.

### C. ANALYSIS_PLAN instantiation

1. Copy the recipe's claim table into `<project-dir>/ANALYSIS_PLAN.md`, with channels/markers translated from the user's mapping.
2. Set `Plan version = recipe-<slug>-<recipe-version>` using the declared version verbatim so the audit trail records provenance without adding a second `v` prefix.
3. Mark the plan as **frozen** (mtime stamp). Subsequent stages must respect this.
4. Present the instantiated plan and wait for the user's confirmation before Phase D, unless the user has already explicitly approved this plan and execution.

### D. Run pipeline

For each stage declared in the recipe, including `[bids?, preprocess, ica, epoch?, erp?, tfr?, spectral?, connectivity?, complexity?, microstate?, source?, stats, figure, report]`:
- Invoke the matching skill through the client's skill mechanism (`complexity` → `eeg-complexity`). If no child-skill invocation tool is available, read `skills/eeg-<stage>/SKILL.md` directly and follow it. Keep the repository root as the working directory.
- Pass recipe parameters as overrides to the skill (e.g., bandpass from recipe).
- **Continuous vs event-locked routing.** Read the recipe's data requirements and pipeline, not an exact `paradigm` string. A continuous recording with no required per-trial markers (for example, `required_markers: []` and `min_duration_s`) does not require event epoching or ERP analysis. Run its declared spectral, connectivity, complexity, or microstate stages using its own segmentation settings. Use fixed-length windows only where the recipe specifies them; microstate fitting may use the continuous record directly. Preserve any block-level state labels.
- After each stage completes, append summary to `<project-dir>/RECIPE_RUN_LOG.md`.

### E. Methods text + citation receipt

1. Invoke `eeg-methods-text` to generate COBIDAS-MEEG paragraph.
2. Copy `recipes/<slug>/citation.bib` to `<project-dir>/report-stage/citation.bib`.
3. Append to the report: "If you use this analysis in a publication, cite: <recipe references>".

### F. Figure comparison (generated vs reference)

If the recipe has a `validation_dataset` and reference figures:

1. Check for `recipes/<slug>/reference_figures/` directory.
2. For each generated figure in `figure-stage/`:
   - Find the corresponding reference figure by name pattern (e.g., `C1_erp_topo.png` → `reference_figures/C1_erp_topo.png`).
   - If reference exists, compare:
     - **Visual layout**: same axes, same channel selection, same time window.
     - **Quantitative**: if both have associated JSON data, compare peak latencies and amplitudes (within tolerance).
   - Write comparison to `<project-dir>/FIGURE_COMPARISON.md`:
     ```markdown
     ## C1: N170 ERP
     - Generated: figure-stage/C1_erp_topo.png
     - Reference: recipes/n170/reference_figures/C1_erp_topo.png
     - Peak latency: generated=168ms, reference=172ms (delta=4ms, OK)
     - Peak amplitude: generated=-4.2uV, reference=-3.8uV (delta=0.4uV, OK)
     - Status: MATCH
     ```
3. If no reference figures exist, skip this phase and note in the run log.

### G. Audit

Unless `--skip-audit`, invoke `eeg-audit`. For pre-submission, ask the reviewer to use an adversarial perspective in the audit prompt. Configure its reviewer connection as described in that skill.

### H. Recipe versioning

Track recipe version history in `RECIPE_VERSION.json`:

```json
{
  "recipe_slug": "n170",
  "runs": [
    {
      "version": "v0.1",
      "run_date": "2026-05-20T14:00:00Z",
      "status": "complete",
      "audit_verdict": "pass",
      "n_subjects": 24,
      "claims_supported": ["C1", "C2"],
      "claims_unsupported": []
    },
    {
      "version": "v0.2",
      "run_date": "2026-05-22T10:00:00Z",
      "status": "complete",
      "audit_verdict": "pass-with-caveats",
      "n_subjects": 24,
      "claims_supported": ["C1"],
      "claims_unsupported": ["C2"],
      "changes_from_previous": "Updated ICA threshold from 0.8 to 0.9"
    }
  ]
}
```

**Version tracking rules**:
- Each recipe run records the recipe version used.
- If the recipe YAML `version` changed since last run, log `changes_from_previous`.
- If the user re-runs with the same version, append a new run entry (same version, different date).
- When comparing versions, diff the claim outcomes (which claims flipped support status).

### I. Reproducibility receipt

Write `<project-dir>/report-stage/REPRO_RECEIPT.md`:
- Recipe slug + version + commit SHA at run time.
- All RNG seeds.
- Backend versions from `ENVIRONMENT.json`.
- SHA256 hashes of input raw files and every stage output.
- Full `ANALYSIS_PLAN.md` (instantiated from the recipe).

## State-tracking recipe class (continuous, windowed)

Most starter recipes are **event-locked** (epoch around a marker, average to an ERP/TFR). A second class is **state-tracking**: there is no per-trial stimulus, only block-level brain states (e.g., *awake* vs *deep anesthesia*, *eyes-open* vs *eyes-closed*, sleep stages). These recipes do not epoch around events; they use the continuous processing or fixed-length windows specified in their pipeline. Declare the duration, state labels, segmentation, and analysis stages explicitly. The `paradigm` field can remain a human-readable description.

### Windowing convention (recipe default)

Use `mne.make_fixed_length_epochs` to produce the sliding windows that the metric is computed over, then feed each window to `eeg-complexity`:

```python
# Default: 5 s windows, 2 s overlap (3 s step) — the canonical setting for
# entropy / Lempel-Ziv / RQA on EEG. Resample to ~100 Hz first if higher.
win = mne.make_fixed_length_epochs(raw, duration=5.0, overlap=2.0, preload=True)
# win.get_data() -> (n_windows, n_channels, n_times); metric computed per window
# per channel yields a (n_channels, n_windows) time course tracking the state.
```

- **Entropy / LZC / PLZC / permutation entropy / RQA:** 5 s windows, ~40–60% overlap (default above). Short enough to resolve state transitions, long enough for stable estimates.
- **Scale-free / criticality / Hurst / DFA / power-law slope:** ≥ 16 s windows (≥ 75% overlap), because these estimators need many cycles of the slowest rhythm to be stable. Do **not** reuse the 5 s entropy window for Hurst/DFA.
- Aggregate per state by taking the mean (and IQR) of each channel's window time course; report both the contrast and the time course so reviewers can see state transitions.

### Built-in validation (sanity check before trusting the contrast)

State-tracking recipes have a cheap, paradigm-agnostic validity check that does not need the source dataset: **resting eyes-open EEG should show higher complexity than eyes-closed** (alpha synchronization in eyes-closed lowers LZC/entropy). If a recipe (or the user's pipeline) reports eyes-closed ≥ eyes-open complexity on a resting block, the windowing, referencing, or filtering is almost certainly wrong — surface this before reporting the headline state contrast. The same monotonicity underlies the anesthesia-depth contrast: complexity (LZC, PLZC, SampEn, permutation/wavelet entropy, RQA determinism and entropy) **decreases** and recurrence rate **increases** from awake to deep anesthesia.

### Expected output (anesthesia-depth reference)

For an `anesthesia_depth` recipe, the validated direction of every metric is fixed and can be asserted as a claim regardless of dataset:

- Lempel-Ziv complexity (LZC) and its permutation variant (PLZC), sample/approximate entropy, permutation entropy, and wavelet/Hilbert-Huang entropy all **decrease** from light to deep anesthesia.
- Recurrence-quantification determinism (DET) and entropy (ENTR) **decrease**; recurrence rate (RR) **increases** (the trajectory becomes more recurrent/regular).
- These are monotone with depth, so a state-tracking recipe can frame its primary claim as a signed paired contrast (deep < awake for complexity, deep > awake for RR), tested with a non-parametric paired test or cluster permutation over channels — there is no ERP-style peak to localize.

Citation for the anesthesia-LZC link: Zhang, X.-S., Roy, R. J., & Jensen, E. W. (2001). EEG complexity as a measure of depth of anesthesia for patients. *IEEE Transactions on Biomedical Engineering*, 48(12), 1424–1433. doi:10.1109/10.966601.

## Contributed-recipe quality gates

For recipes in `recipes/` contributed by external authors, enforce these quality gates before marking `status: validated`:

### Gate 1: Frontmatter completeness
- All required YAML fields present (see Phase A step 2).
- `references` list includes at least one peer-reviewed paper.
- `validation_dataset` is specified (can be a public dataset name).

### Gate 2: Reproducibility
- Recipe must include `citation.bib` with valid BibTeX entries.
- Recipe must include `RECIPE.md` with a claim table.
- If `validation_dataset` is public, recipe should include `reference_figures/` with expected outputs.

### Gate 3: Validation run
- Recipe must have been run on the validation dataset with `status: validated` outcome.
- Audit verdict must be `pass` or `pass-with-caveats`.
- All primary claims must be `supports`.

### Gate 4: Documentation
- Recipe must include a plain-language description of what it does.
- Recipe must document any non-standard parameters and why they differ from defaults.
- Recipe must list known limitations.

New contributed recipes failing a gate remain at `status: experimental` until fixed. Do not relabel existing recipes as part of executing this skill.

## Failure modes

| Symptom | Action |
|---|---|
| Recipe slug not found | List `recipes/*/RECIPE.md` and ask user. |
| YAML frontmatter invalid or incomplete | Stop. Report missing/invalid fields. |
| Required channel missing | Stop. Report which channel is missing; suggest closest available. Do NOT silently substitute. |
| Required marker code absent | Stop. Ask for `--marker-map`. |
| Trial count below recipe minimum | Warn loudly, list per-subject deficits, ask user whether to proceed (effect size is the user's call). |
| Continuous recipe has no per-trial markers, but Phase B's trial-count gate fires | Follow its declared duration and segmentation requirements instead of per-condition trial counts. Check state labels only when its analysis requires them. Do NOT block on missing event codes. |
| State labels (awake/deep, eyes-open/eyes-closed) are encoded as block annotations, not numeric markers | Map annotation descriptions to states via `--marker-map` / `mne.events_from_annotations`; if states are separate files, treat each file as one state. Verify each state has enough continuous clean data for ≥ a few windows. |
| Eyes-closed complexity ≥ eyes-open on a resting block | Stop and re-check before reporting any state contrast — almost always a referencing/filtering/windowing bug (see State-tracking built-in validation). Do not present the headline contrast until the eyes-open>eyes-closed sanity check passes. |
| Scale-free / Hurst / DFA computed on 5 s entropy windows | Estimates unstable. Re-run those metrics on ≥ 16 s windows; never share the 5 s entropy window with power-law/Hurst estimators. |
| Recipe declares feature unsupported by ENVIRONMENT.json | Stop. Either skill hasn't shipped yet, or env probe is missing a backend. |
| Validation dataset not found | Warn. Skip figure comparison. Proceed with pipeline. |
| Recipe version mismatch (user requests v0.2 but only v0.1 exists) | Stop. List available versions. |
| Figure comparison shows large delta | Warn. Do not stop — deltas may be legitimate (different data). Log in FIGURE_COMPARISON.md. |

## Cross-references

- Recipe library: `recipes/`, see `recipes/README.md`.
- Template for new recipes: `recipes/_template/RECIPE.md`.
- Contributing recipes: `CONTRIBUTING.md`.
- Auto-brief tool: `tools/auto_brief.py`.
- Figure comparison output: `FIGURE_COMPARISON.md`.
- Version tracking: `RECIPE_VERSION.json`.
- Complexity / entropy / RQA metrics for state-tracking recipes: `eeg-complexity` (the `complexity` stage skill).
- Windowing helper for continuous recipes: `mne.make_fixed_length_epochs` (default 5 s duration, 2 s overlap; ≥16 s for scale-free/Hurst).
