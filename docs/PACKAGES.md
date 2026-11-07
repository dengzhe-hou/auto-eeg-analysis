# Install AEA packages

## Python resource package

Use Python 3.10 or newer in your existing analysis environment.

```sh
python -m pip install auto-eeg-analysis==0.3.3rc2
aea-eeg init ./my-eeg-study --agent codex
cd my-eeg-study
```

Use `--agent claude` for Claude Code or `--agent both` for both clients. The
command creates a new project containing 22 skills, 10 recipes, templates and
tools, then registers project-local skill links. Existing nonempty folders are
refused. Start your separately installed coding client inside the new project.

The default package has no scientific runtime dependencies. Reuse an existing
MNE environment. To create a new Conda environment from the copied specification,
run `conda env create -f environment.yml` and `conda activate aeais` in the project.
Alternatively install the existing analysis dependency set with
`python -m pip install 'auto-eeg-analysis[analysis]==0.3.3rc2'`.

Read `AGENT_GUIDE.md` and approve a study-specific plan before computation.
The package version is separate from retained validation and plugin versions.
`aea-eeg --version` reports the resource source commit.

The [PyPI page](https://pypi.org/project/auto-eeg-analysis/0.3.3rc2/) contains release files. Version 0.3.3rc2 preserves the
archive source-version record. The first rc1 remains available. Initial package
checks and fixes are distribution checks and add no scientific validation.

## MATLAB toolbox preview

Download the [AEA 0.1.3 toolbox](https://github.com/dengzhe-hou/auto-eeg-analysis/releases/download/eeglab-v0.1.3-preview/AEA_MATLAB_EEGLAB_0_1_3_preview.mltbx) and install the `.mltbx` file in MATLAB.
The candidate was built and checked with Windows MATLAB R2026a Update 2.

Run `aea_setup` with the folder containing your `eeglab.m`. Existing AEA plugin
files are retained. Native MATLAB requires adapter 0.1.3 or newer. Restart
EEGLAB after a new plugin installation. In Tools > AEA > Settings, use the
path returned by `aea_library_root` as the AEA checkout folder.

Choose backend `matlab`, leave Python blank, and select your installed and
signed-in Codex CLI or Claude Code executable. Export a dataset to a new study,
approve the analysis plan, then open the saved report from EEGLAB.

The native helper covers explicit ERP means from existing epochs. The broader
resource library primarily uses MNE-Python. See [native MATLAB coverage](MATLAB_NATIVE.md)
and the [toolbox setup guide](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/extensions/matlab/README.md).
The [File Exchange listing](https://www.mathworks.com/matlabcentral/fileexchange/185187-aea-for-matlab-and-eeglab) provides the GitHub source.
Use the linked GitHub release for the tested `.mltbx` installer.
