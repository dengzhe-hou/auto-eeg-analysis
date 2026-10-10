# Contributing to AEA

Contributions can add an analysis recipe, improve a skill, or fix code and documentation. Start with [Getting started](docs/GETTING_STARTED.md) to set up the environment and load the skills. The [recipe library](recipes/README.md) lists the existing analyses; the [backend registry](tools/env/backends.json) records available backend capabilities.

## Contribute a recipe

A recipe is a reusable Markdown specification of a published EEG analysis: data requirements, parameters, claims, figures, and references.

1. Fork the repository and create a branch for your change.
2. Copy [recipes/_template/](recipes/_template/) to `recipes/<your-slug>/`.
3. Fill in `RECIPE.md` and add `citation.bib`. State the required channels, sampling rate, event mapping, trial counts or clean recording duration, preprocessing, statistics, and expected outputs.
4. Run the specified analysis on at least one public dataset. Record where to obtain the data, the exact configuration and command, results, and any deviations from the recipe. Place access instructions in `validation/README.md` if needed; do not commit raw participant data.
5. Add a regression check under `recipes/<your-slug>/tests/` for the key numerical result. The [ERN test](recipes/ern-flankers/tests/test_ern_flankers.py) demonstrates dataset discovery and bounded numerical assertions. Choose tolerances appropriate to your analysis and record their basis.
6. Run the checks below and open a pull request titled `recipe: <slug>: <short description>`.

Use the recipe template's status vocabulary: `experimental`, `validated`, or `canonical`. Document which dataset and configuration support the status, including unsupported claims or contrasts that have not been tested. Validation of one contrast does not establish every other contrast in the recipe. Keep existing results and limitations visible when adding new evidence.

The [eeg-recipe skill](skills/eeg-recipe/SKILL.md) describes the execution sequence and expected project outputs. In the pull request, include the source citation, data access instructions, changed parameters, validation results, and test summary so someone else can repeat the run.

## Contribute a skill

Skills in `skills/eeg-*/SKILL.md` teach the coding assistant how to perform individual analysis stages. You can add a method, clarify parameters, improve data handling, or fix a supported platform path.

- Follow an existing skill's organization: frontmatter, constants, phases, failure modes, and cross-references. [eeg-erp](skills/eeg-erp/SKILL.md) is an example of a computational stage; [eeg-recipe](skills/eeg-recipe/SKILL.md) composes stages.
- Keep methodology and analysis contracts in Markdown. Reusable execution helpers and tests belong in `tools/` or `recipes/<slug>/tests/`; backend code templates belong in [templates/backends/](templates/backends/).
- Add required Python dependencies to [environment.yml](environment.yml). State optional dependencies and how to detect their absence.
- For backend changes, update [backends.json](tools/env/backends.json) and the relevant probes in [check_env.sh](tools/env/check_env.sh) and [check_env.ps1](tools/env/check_env.ps1). Keep the capability description aligned with the paths you actually exercised.
- Test the affected path on public or synthetic data that exercises the change. Record the environment and meaningful numerical expectations when the change affects analysis results.

MNE is the primary execution backend. Existing EEGLAB and FieldTrip paths have specific capabilities, templates, and comparison results; a contribution should state which stage and configuration it implements. See [platform support](docs/PLATFORM_SUPPORT.md) and the [backend templates](templates/backends/README.md).

## Contribute a tool, document, or fix

For usage questions, check [troubleshooting](docs/GETTING_STARTED.md#troubleshooting), then
open a [GitHub issue](https://github.com/dengzhe-hou/auto-eeg-analysis/issues/new/choose).
Issues are the public support channel; maintainer contact is in [CITATION.cff](CITATION.cff).

Bug reports are most useful with the command or prompt, traceback, affected skill or recipe, environment details, and a small public or synthetic example. For documentation fixes, link the relevant instructions and explain the step that was confusing or incorrect.

Useful starting points include [tools/env/](tools/env/), [tools/auto_brief.py](tools/auto_brief.py), the [project templates](templates/), and [docs/](docs/). Existing computational skills include decoding, spectral analysis, behavior, connectivity, microstates, source analysis, and BIDS support; check them before proposing a duplicate skill.

## Run the checks

From the repository root, after creating the `aeais` environment as described in [Getting started](docs/GETTING_STARTED.md):

```bash
conda run -n aeais python -m pytest tools/tests/ recipes/
```

For a recipe with its own test directory, you can first run the focused check:

```bash
conda run -n aeais python -m pytest recipes/<your-slug>/tests/ -v
```

The suite includes infrastructure checks, recorded-result checks, and tests that execute an analysis when its dataset is available. Read the pass and skip counts together:

- The MNE sample-data regression tests skip if the sample dataset is absent. Reuse an existing MNE data cache when possible. Setting `AEA_FETCH_DATA=1` explicitly opts into fetching that dataset for the tests.
- The ERN recipe test looks for a local ERP CORE Flankers file. Set `AEA_ERP_CORE_FLANKERS` to its path, or use the location documented in [the test](recipes/ern-flankers/tests/test_ern_flankers.py). It skips with setup instructions if the data are missing.
- A skipped data-dependent test is not evidence that the analysis passed. Report required datasets and skips in the pull request. Do not turn computation failures into skips.

[GitHub Actions](.github/workflows/ci.yml) runs the same suite on Ubuntu for pull requests and pushes to `main`. Passing the tests verifies the covered checks; the run record for your new analysis or backend path supplies the additional evidence specific to that contribution.

## Recognition

All contributors are listed in the repo. For the eventual AEA paper (target: Scientific Data, Article), significant contributors (major recipes, major skills, or sustained engagement) will be invited as co-authors. The bar is real contribution, not a single typo fix.

## House rules

- Keep skills and recipes readable as standalone methodology specifications, with the source references and parameters needed to reproduce a run.
- Record backend selection and substitutions explicitly. Stop with a useful error when a required capability is missing.
- Verify references against their sources. Include the dataset and configuration behind numerical claims.
- Preserve the analysis plan, seed settings, numerical baselines, and existing result records when changing a stage. Explain any intentional result change in the pull request.

## License

The repository is distributed under the [MIT License](LICENSE). Existing recipe frontmatter also declares `CC-BY-4.0`; preserve its license and attribution fields when editing a recipe.
