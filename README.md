<h1 align="center">AEA</h1>
<h3 align="center">Shareable skills and recipes for EEG analysis</h3>

AEA (Automated EEG Analysis) is an open library of **22 skills and 10 recipes** for MNE-Python, with executable specifications and a numerically certified core. Skills combine EEG methods, numerical conventions, code templates, and output checks; recipes assemble them into paradigm-specific workflows.

You specify the study and approve the plan. A coding agent adapts and executes the templates in your environment, keeping the plan, code, results, figures, methods text, and review records together.

[Website](https://dengzhe-hou.github.io/auto-eeg-analysis/) · [Documentation](docs/GETTING_STARTED.md) · [Recipes](recipes/README.md) · [Validation coverage](docs/CERTIFICATION_LEVELS.md) · [Contribute](CONTRIBUTING.md) · [Releases](https://github.com/dengzhe-hou/auto-eeg-analysis/releases/latest)

## Quickstart

Install Git, Conda, and a signed-in Codex CLI or Claude Code client first. These commands use `main`, including fixes added after [v0.3.2](CHANGELOG.md#choose-a-version).

```bash
git clone https://github.com/dengzhe-hou/auto-eeg-analysis.git
cd auto-eeg-analysis
conda env create -f environment.yml
conda activate aeais
python tools/install_skills.py --agent codex
codex
```

Run from the repository root with `aeais` active. For compatible data in `projects/my-study/raw/`, enter this **inside Codex**:

```text
$eeg-recipe n400-semantic --data projects/my-study
```

Choose a recipe that matches your paradigm. For ERP CORE, follow the [copy-ready N400 brief and approval prompt](docs/EXAMPLES.md#adapt-a-recipe-to-your-study) to preserve the existing data layout. For Claude Code, install with `--agent claude`, start `claude`, and use `/eeg-recipe` instead of `$eeg-recipe`.

Confirm the analysis plan before execution and [configure the reviewer](docs/GETTING_STARTED.md#configure-the-reviewer) for the audit stage. The [setup guide](docs/GETTING_STARTED.md) covers data formats, study directories, Windows, and output files.

Using Windows and EEGLAB? Follow the [first-report walkthrough](docs/WINDOWS_FIRST_RUN.md) for client installation, Python and executable paths, menu settings, and opening the report. The [preview extension](docs/EEGLAB.md) connects EEGLAB to AEA; analysis mainly uses Python/MNE.

> [!TIP]
> To try the N400 example without an agent or model account, use the [fixed Python tutorial](docs/EXAMPLES.md#erp-core-complete-n400-recipe-case). You can also [replot the saved results without raw EEG](docs/EXAMPLES.md#replot-the-saved-results).

## How it works

| Step | What happens |
| --- | --- |
| Specify and approve | Define the study question and analysis choices; select a recipe or combine skills. |
| Adapt and execute | The agent reads the procedures and adapts code templates, mainly using MNE-Python. |
| Inspect and replay | Review saved outputs, figures, methods, and checks; replay the documented analysis. |

[![AEA workflow: skills and recipes guide an LLM coding agent, the researcher approves the plan, and MNE-Python executes the analysis.](docs/assets/library-overview.svg)](docs/assets/library-overview.svg)

[Recorded agent workflow](docs/EXAMPLES.md#adapt-a-recipe-to-your-study) · [Custom analysis](docs/GETTING_STARTED.md#w2-design-a-custom-analysis) · [Replay guide](docs/REPLAY.md)

## Example outputs

[![N400 results from 20 ERP CORE participants: ERP curves at CPz/Cz/Pz, a descriptive scalp map, and participant amplitude differences.](docs/assets/n400-example.png)](docs/assets/n400-example.png)

The fixed N400 example retains results from 20 ERP CORE participants: CPz/Cz/Pz ERPs with ±1 participant SEM, a descriptive difference scalp map, and participant-level unrelated-minus-related amplitudes at 300–500 ms. Its [saved configuration and results](tools/examples/n400/recipe_case_results.json) are separate from the recorded agent run and historical certification.

[Run the example](docs/EXAMPLES.md#erp-core-complete-n400-recipe-case) · [Replot saved results](docs/EXAMPLES.md#replot-the-saved-results) · [Inspect the recorded agent case](docs/EXAMPLES.md#adapt-a-recipe-to-your-study)

## Explore the library

| Resource | Contents | Start here |
| --- | --- | --- |
| Skills | Preprocessing, ERPs, spectra, time-frequency analysis, connectivity, statistics, figures, and reporting | [Task reference](docs/GETTING_STARTED.md#choose-skills-for-a-task) · [Skill files](skills/) |
| Recipes | Paradigm-specific workflows, data requirements, parameter choices, and source papers | [Recipe catalogue](recipes/README.md) |
| Worked examples | Plans, scripts, saved results, figures, and replay instructions | [Examples](docs/EXAMPLES.md) |

## Validation

Certification applies to the **outputs and configurations** listed in the [coverage record](docs/CERTIFICATION_LEVELS.md). The numerical core includes selected ERP amplitudes, cluster statistics, and spectral band power. EEGLAB and FieldTrip provide independent comparisons and selected alternative backend paths.

Each [recipe](recipes/README.md#available-recipes) records its declared status and available evaluation. A checked numerical core does not certify every option or generated workflow.

[Validation coverage](docs/CERTIFICATION_LEVELS.md) · [Benchmark configurations and results](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/995f53d42cc74205b164e8711d4b289b8c2ad3a1/docs/BENCHMARK.md)

## Citation and contributing

Use [CITATION.cff](CITATION.cff) to cite AEA, and cite the source papers declared by the recipes you use. See the [contribution guide](CONTRIBUTING.md) to add or improve a skill or recipe.

[Changes](CHANGELOG.md) · [Troubleshooting](docs/GETTING_STARTED.md#troubleshooting) · [Issues](https://github.com/dengzhe-hou/auto-eeg-analysis/issues)

Software uses the [MIT licence](LICENSE); recipe metadata uses CC BY 4.0. Built on [ARIS](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep).

Layout reference: [PEFT](https://looketal.com/s/readme-huggingface-peft.html), via [Look et al.](https://looketal.com/).
