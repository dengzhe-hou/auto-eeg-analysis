# Auto EEG Analysis (AEA)

AEA provides reusable EEG analysis skills and study recipes for large language
model coding agents. MNE-Python is the primary computation backend. Selected
EEGLAB and FieldTrip routes are described in the bundled documentation.

This package installs the resource library and a project initialization command.
It includes 22 skills, 10 study recipes, analysis helpers, templates and setup
documentation. It does not install or configure a model client or an account.

## Install and create a project

Use Python 3.10 or newer in an environment of your choice.

```sh
python -m pip install auto-eeg-analysis==0.3.3rc2
aea-eeg init ./my-eeg-study --agent codex
cd my-eeg-study
```

Use `--agent claude` for Claude Code or `--agent both` for both clients.
The command copies the library into a new or empty directory and creates
project-local skill links using AEA's existing installer. Existing nonempty
directories are refused. It does not change global client configuration.
`python -m auto_eeg_analysis` accepts the same arguments as `aea-eeg`.

The default installation has no scientific runtime dependencies. Reuse your
existing MNE environment, use the included `environment.yml` to create one,
or install the analysis dependencies from the existing environment specification.

```sh
python -m pip install 'auto-eeg-analysis[analysis]==0.3.3rc2'
```

Read `AGENT_GUIDE.md`, select procedures through `RESOURCE_INDEX.md`, and approve
the study-specific analysis plan. Start the separately installed coding client
from the initialized project directory. `aea-eeg path` shows the installed
resource directory.

## Version and evidence

This packaging candidate uses published AEA source commit
`cdc0c30105cc4547aed8e5ece41739a8462cb47a`. The package version identifies this
distribution. Retained scientific validation records and plugin versions keep
their original identifiers. Packaging checks do not extend the numerical
validation coverage in `docs/CERTIFICATION_LEVELS.md`.

The package contains no participant datasets, model credentials or archived model
sessions. The Git repository remains the development source and the place for
contributions and support.

## License and citation

Code and skills use the repository's MIT license. Study recipes use CC BY 4.0
as stated in `recipes/README.md`. Preserve the recipe citations and original
license notices. `CITATION.cff` retains the source repository's citation metadata.

[Project](https://github.com/dengzhe-hou/auto-eeg-analysis) ·
[Setup guide](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/docs/GETTING_STARTED.md) ·
[Validation coverage](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/docs/CERTIFICATION_LEVELS.md)
