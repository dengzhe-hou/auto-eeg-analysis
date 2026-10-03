# AEA Recipe Library

A **recipe** is a single Markdown file that completely specifies an EEG analysis for a published paradigm: what data shape it expects, how to preprocess, how to test, what figures to render, and which paper it derives from. Drop the recipe + your data into AEA, run one command, get a paper-ready figure + methods text + reproducibility receipt.

## Why recipes

EEG analyses are reinvented in every lab. The same paradigm (P300 oddball, N170 face inversion, alpha attention modulation) is rerun with subtle parameter differences across hundreds of papers, and reproducibility suffers. A recipe is the **smallest unit of sharable EEG analysis**:

- One file
- Cites the methodological source
- Declares data requirements explicitly
- Runs with one command
- Produces an auditable, reproducible trail

This is what HuggingFace did for models. EEG has never had it.

## Run a recipe

First follow [Getting started](../docs/GETTING_STARTED.md) to create the Python environment, load the skills, and prepare a separate analysis project. Recipe commands are prompts to your coding assistant, not shell commands.

For example, after loading the skills in Claude Code:

```text
/eeg-recipe p300-oddball --data /path/to/my-oddball-project
```

In Codex, ask the assistant to use the `eeg-recipe` skill with the same recipe slug and project path. See [Getting started](../docs/GETTING_STARTED.md) for the installation and invocation steps for each assistant.

The [eeg-recipe skill](../skills/eeg-recipe/SKILL.md) reads the recipe and your dataset brief, checks channels, markers, sampling rate, and available trials or recording duration, then asks you to confirm the analysis plan. The assistant generates and runs the analysis code using the stages the recipe specifies. Event-related recipes use epochs and ERP or time-frequency analysis; continuous recipes use the declared spectral, connectivity, microstate, or complexity stages.

Outputs belong to your analysis project:

| Output | Purpose |
|---|---|
| `ANALYSIS_PLAN.md` | Recipe instantiated for your channels, conditions, and data |
| `RECIPE_RUN_LOG.md` | Stage progress and deviations |
| `figure-stage/` | Figures declared by the recipe; filenames follow its figure plan |
| `report-stage/methods.md` | Methods text generated from the completed analysis |
| `report-stage/citation.bib` | Source references copied from the recipe |
| `report-stage/REPRO_RECEIPT.md` | Recipe version, environment, seeds, and run provenance |
| `RECIPE_VERSION.json` | Version and outcome history for the project |

Read the recipe's numerical-specification notes before comparing outputs with a committed benchmark. For example, some ERP benchmarks use a minimal pipeline without ICA; the recipe also describes a fuller preprocessing path. These are separately documented configurations.

## Available recipes

The library contains **10 recipes**. The status column below reproduces each recipe's frontmatter. Validation evidence is described separately because it applies to the datasets, contrasts, and configurations recorded in that recipe.

| Recipe | Analysis | Declared status | Recorded validation |
|---|---|---|---|
| [mmn-oddball](mmn-oddball/RECIPE.md) | Auditory mismatch negativity, deviant versus standard | `validated` | ERP CORE MMN group analysis |
| [p300-oddball](p300-oddball/RECIPE.md) | P300 auditory or visual oddball | `experimental` | ERP CORE P3 group analysis and numerical benchmark are recorded in the recipe |
| [n170-faces](n170-faces/RECIPE.md) | Face selectivity, faces versus non-face controls | `validated` | OpenNeuro ds000117 and ERP CORE N170 group analyses |
| [n170-face-inversion](n170-face-inversion/RECIPE.md) | Upright versus inverted faces | `experimental` | Predicted outputs; end-to-end validation pending |
| [n400-semantic](n400-semantic/RECIPE.md) | Semantic priming, unrelated versus related words | `validated` | ERP CORE N400 group analysis |
| [ern-flankers](ern-flankers/RECIPE.md) | Conflict N2, response-related negativity, and frontal theta | `validated` | Single-subject conflict demonstration and a separate group error-versus-correct ERN analysis |
| [alpha-attention-cueing](alpha-attention-cueing/RECIPE.md) | Posterior alpha modulation during spatial attention | `experimental` | Predicted outputs; end-to-end validation pending |
| [resting-microstate](resting-microstate/RECIPE.md) | Resting microstate maps and temporal parameters | `validated` | PhysioNet EEGBCI eyes-closed analysis |
| [resting-spectral-connectivity](resting-spectral-connectivity/RECIPE.md) | Spectral power, aperiodic fits, and debiased wPLI | `validated` | EEGBCI alpha-reactivity validation; the recipe records separate aperiodic and connectivity checks and their limitations |
| [complexity-anesthesia](complexity-anesthesia/RECIPE.md) | Continuous complexity and entropy measures | `validated` | EEGBCI eyes-open versus eyes-closed check; the anesthesia contrast has not been tested here |

For face selectivity, use `n170-faces`. Face inversion is a different contrast and has its own `n170-face-inversion` recipe.

Validation scripts and result JSON files live in [tools/validation/](../tools/validation/); numerical comparisons live in [tools/benchmark/](../tools/benchmark/). [Benchmark documentation](../docs/BENCHMARK.md) and [certification levels](../docs/CERTIFICATION_LEVELS.md) explain how those checks relate to the certified core. A recipe's status does not replace its configuration-specific validation notes.

## Anatomy of a recipe

Every shipped recipe has these files:

```text
recipes/<recipe-name>/
├── RECIPE.md       # version, data requirements, pipeline, claims, figures, limitations
└── citation.bib    # references for the analysis
```

The `ern-flankers` recipe also has [a regression test](ern-flankers/tests/test_ern_flankers.py). Validation scripts, figures, and result JSON files are currently shared under `tools/validation/`, rather than bundled into each recipe directory. Raw validation datasets are obtained separately.

For new recipes, start from the [recipe template](_template/RECIPE.md). A contribution can add `validation/README.md` with dataset access instructions, `reference_figures/` with its reference outputs, and `tests/` with a numerical regression check. These are contribution assets, not directories present in every existing recipe.

## Contributing a recipe

See [`CONTRIBUTING.md`](../CONTRIBUTING.md). Short version:

1. Fork the repo.
2. Copy `recipes/_template/` to `recipes/<your-paradigm-name>/`.
3. Fill in `RECIPE.md`. Cite the paper.
4. Validate against ≥1 publicly available dataset.
5. Open a PR with the dataset, parameters, execution command, numerical results, and test outcome. Reviewers check the cited method, the completed run, and the declared numerical expectations.

Each accepted recipe earns the contributor a co-authorship line in the eventual AEA paper (similar to how MNE handles tutorial contributions).

## Recipes and project analysis plans

- A **recipe** is a reusable artifact written once and applied to many datasets.
- **ANALYSIS_PLAN.md** specifies the analysis and claims for one study, dataset, and team. It is a preregistration only if you register it before the relevant analysis.

When you run a recipe on your data, AEA instantiates it into an `ANALYSIS_PLAN.md` with your dataset, marker mapping, and parameters. Review that plan before execution; changes belong in the run record.

## Recipe versioning

Recipes are versioned with semantic versioning (`v1.0.0`). Breaking changes (e.g., adding required marker codes) bump major; new optional fields bump minor; bug fixes / clarifications bump patch. The recipe file declares its version in YAML frontmatter, and AEA records the version in every reproducibility receipt.
