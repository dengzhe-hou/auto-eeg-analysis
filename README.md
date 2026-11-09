<div align="center">

# AEA: Shareable skills and recipes for EEG analysis

<p align="center"><strong>English</strong> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.ja.md">日本語</a></p>

[![Documentation](https://img.shields.io/badge/Docs-Get_started-2f6fd0)](docs/GETTING_STARTED.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![EEGLAB 0.1.3](https://img.shields.io/badge/EEGLAB-0.1.3-6d4bd6)](docs/EEGLAB.md)

**[Website](https://dengzhe-hou.github.io/auto-eeg-analysis/) · [Documentation](docs/GETTING_STARTED.md) · [Recipes](recipes/README.md) · [Validation coverage](docs/CERTIFICATION_LEVELS.md) · [Contribute](CONTRIBUTING.md) · [Releases](https://github.com/dengzhe-hou/auto-eeg-analysis/releases/latest)**

</div>

AEA (Automated EEG Analysis) is an open library of **22 skills and 11 recipes** for MNE-Python, with executable specifications and a numerically certified core. Skills combine EEG methods, numerical conventions, code templates, and output checks; recipes assemble them into paradigm-specific workflows.

You specify the study and approve the plan. A coding agent adapts and executes the templates in your environment, keeping the plan, code, results, figures, methods text, and review records together.

| Stage | Who and what | Input → Output |
| --- | --- | --- |
| **Specify and approve** | Researcher, recipes and skills | Study question and data → approved analysis plan |
| **Adapt and execute** | Coding agent and code templates | Approved plan → scripts executed mainly with MNE-Python |
| **Inspect and replay** | Researcher and output checks | Saved results → figures, methods, review and documented replay |

## Example outputs

[![N400 results from 20 ERP CORE participants: ERP curves at CPz/Cz/Pz, a descriptive scalp map, and participant amplitude differences.](docs/assets/n400-example.png)](docs/assets/n400-example.png)

The fixed N400 example retains results from 20 ERP CORE participants: CPz/Cz/Pz ERPs with ±1 participant SEM, a descriptive difference scalp map, and participant-level unrelated-minus-related amplitudes at 300–500 ms. Its [saved configuration and results](tools/examples/n400/recipe_case_results.json) are separate from the recorded agent run and historical certification.

[Run the example](docs/EXAMPLES.md#erp-core-complete-n400-recipe-case) · [Replot saved results](docs/EXAMPLES.md#replot-the-saved-results) · [Inspect the recorded agent case](docs/EXAMPLES.md#adapt-a-recipe-to-your-study)

---

## Quickstart

**EEGLAB extension approved:** AEA 0.1.3 is listed in the [official EEGLAB extension catalogue](https://sccn.ucsd.edu/eeglab/plugin_uploader/plugin_list_all.php). In EEGLAB, open **File > Manage EEGLAB extensions**, search for **AEA**, and install it. Then follow the [setup guide](docs/EEGLAB.md) to connect your AEA checkout and coding client.

AEA is also listed in the [FieldTrip extensions directory](https://www.fieldtriptoolbox.org/extensions/). See [backend coverage](templates/backends/README.md) for the available FieldTrip route.

The [PyPI preview](https://pypi.org/project/auto-eeg-analysis/0.3.3rc2/) creates an AEA project in an existing analysis environment.

```sh
python -m pip install auto-eeg-analysis==0.3.3rc2
aea-eeg init ./my-eeg-study --agent codex
cd my-eeg-study
```

Use `--agent claude` or `--agent both` for the other client choices. Work from the initialized project in your MNE environment. The default package has no scientific runtime dependencies. See the [package guide](docs/PACKAGES.md) for environment setup.

A [MATLAB toolbox preview](https://github.com/dengzhe-hou/auto-eeg-analysis/releases/download/eeglab-v0.1.3-preview/AEA_MATLAB_EEGLAB_0_1_3_preview.mltbx) bundles the resource library and EEGLAB adapter. [File Exchange](https://www.mathworks.com/matlabcentral/fileexchange/185187-aea-for-matlab-and-eeglab) provides the GitHub source. Use the `.mltbx` link for the tested installer and follow its [setup guide](extensions/matlab/README.md).

For a Git checkout and a new Conda environment, install Git, Conda, and a signed-in Codex CLI or Claude Code client first. These commands use `main`, including fixes added after [v0.3.2](CHANGELOG.md#choose-a-version).

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

The **[EEGLAB 0.1.3 preview](https://github.com/dengzhe-hou/auto-eeg-analysis/releases/tag/eeglab-v0.1.3-preview)** adds a [native MATLAB route](docs/MATLAB_NATIVE.md)
for preparation, client launch and bounded ERP means, figures and reports without
Python/MNE. Use the matching checkout and ZIP from that preview; the older
0.1.2 package does not contain this route.

> [!TIP]
> To try the N400 example without an agent or model account, use the [fixed Python tutorial](docs/EXAMPLES.md#erp-core-complete-n400-recipe-case). You can also [replot the saved results without raw EEG](docs/EXAMPLES.md#replot-the-saved-results).

---

## How it works

[![AEA workflow: skills and recipes guide an LLM coding agent, the researcher approves the plan, and MNE-Python executes the analysis.](docs/assets/library-overview.svg)](docs/assets/library-overview.svg)

[Recorded agent workflow](docs/EXAMPLES.md#adapt-a-recipe-to-your-study) · [Custom analysis](docs/GETTING_STARTED.md#w2-design-a-custom-analysis) · [Replay guide](docs/REPLAY.md)

---

## Explore the library

| Resource | Contents | Start here |
| --- | --- | --- |
| Skills | Preprocessing, ERPs, spectra, time-frequency analysis, connectivity, statistics, figures, and reporting | [Task reference](docs/GETTING_STARTED.md#choose-skills-for-a-task) · [Skill files](skills/) |
| Recipes | Paradigm-specific workflows, data requirements, parameter choices, and source papers | [Recipe catalogue](recipes/README.md) |
| Worked examples | Plans, scripts, saved results, figures, and replay instructions | [Examples](docs/EXAMPLES.md) |

---

## Validation

Certification applies to the **outputs and configurations** listed in the [coverage record](docs/CERTIFICATION_LEVELS.md). The numerical core includes selected ERP amplitudes, cluster statistics, and spectral band power. EEGLAB and FieldTrip provide independent comparisons and selected alternative backend paths.

Each [recipe](recipes/README.md#available-recipes) records its declared status and available evaluation. A checked numerical core does not certify every option or generated workflow.

[Validation coverage](docs/CERTIFICATION_LEVELS.md) · [Benchmark configurations and results](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/995f53d42cc74205b164e8711d4b289b8c2ad3a1/docs/BENCHMARK.md)

---

## Citation and contributing

Use [CITATION.cff](CITATION.cff) to cite AEA and record the software version or commit used. Cite the source papers declared by the recipes you use. The [Zenodo archive](https://doi.org/10.5281/zenodo.24012489) preserves the resources and validation records frozen on 6 November 2026. See [public versions and archives](docs/PACKAGES.md#public-versions-and-archives) for the package and archive mapping, and the [contribution guide](CONTRIBUTING.md) to add or improve a skill or recipe.

Official usage tutorials are in English. You can also [share a community tutorial in any language](CONTRIBUTING.md#share-a-community-tutorial) or [report your first run and platform results](CONTRIBUTING.md#report-a-first-run-or-platform-check), including incomplete attempts.

[Changes](CHANGELOG.md) · [Troubleshooting](docs/GETTING_STARTED.md#troubleshooting) · [Issues](https://github.com/dengzhe-hou/auto-eeg-analysis/issues)

Software uses the [MIT licence](LICENSE); recipe metadata uses CC BY 4.0. Built on [ARIS](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep).

Layout reference: [CRAFT](https://looketal.com/s/readme-coral-lab-asu-craft.html), via [Look et al.](https://looketal.com/).
