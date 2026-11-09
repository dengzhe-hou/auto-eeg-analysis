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

## Public versions and archives

| Entry | Published version or source | What it contains |
| --- | --- | --- |
| [GitHub](https://github.com/dengzhe-hou/auto-eeg-analysis) | `main`, changing with commits | Current source and documentation. Record the commit used. |
| [GitHub stable release](https://github.com/dengzhe-hou/auto-eeg-analysis/releases/tag/v0.3.2) | `v0.3.2`, 3 October 2026 | Earlier fixed release. Later package and adapter changes have separate versions. |
| [PyPI](https://pypi.org/project/auto-eeg-analysis/0.3.3rc2/) | `0.3.3rc2` | Resource installer and project initialization. Bundled resources come from `cdc0c30105cc4547aed8e5ece41739a8462cb47a`. |
| [EEGLAB catalogue](https://sccn.ucsd.edu/eeglab/plugin_uploader/plugin_list_all.php) | Adapter `0.1.3` | EEGLAB menu extension. Connect it to a matching AEA resource checkout and coding client. |
| [FieldTrip directory](https://www.fieldtriptoolbox.org/extensions/) | External extension listing, merged 7 November 2026 | AEA entry linking to its independently maintained source and support. |
| [MATLAB toolbox](https://github.com/dengzhe-hou/auto-eeg-analysis/releases/tag/eeglab-v0.1.3-preview) | `0.1.3 preview` | `.mltbx` containing the adapter and resource library, with installation helpers. |
| [File Exchange](https://www.mathworks.com/matlabcentral/fileexchange/185187-aea-for-matlab-and-eeglab) | GitHub `main` source | Source download and a link to the tested `.mltbx`. Its listing version can advance separately from the binary preview. |
| [Zenodo](https://doi.org/10.5281/zenodo.24012489) | Snapshot `2026-11-06`, published 7 November 2026 | Frozen resources and validation records for the 600-session study and retained ERP evaluations. |
| [Website](https://dengzhe-hou.github.io/auto-eeg-analysis/) | GitHub Pages from `docs/` | Current usage guidance and links to these releases and archives. |

FieldTrip accepted the directory entry in [PR #968](https://github.com/fieldtrip/website/pull/968). The [MNE directory request](https://github.com/mne-tools/mne-python/pull/14504) remains open as of 7 November 2026.

Software, adapter and archive versions identify different objects. The Zenodo
record does not include later package builds or runs completed after its frozen
snapshot. For the numerical and behavioural configurations actually checked,
see [validation coverage](CERTIFICATION_LEVELS.md).

### Cite the material used

Use [CITATION.cff](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/CITATION.cff)
for the software and record the actual release or source commit. Cite
[10.5281/zenodo.24012489](https://doi.org/10.5281/zenodo.24012489) when using that fixed resource and validation
archive. The [all-version DOI](https://doi.org/10.5281/zenodo.24012488) identifies
the archive series. Recipe source papers and original datasets retain their own
citation requirements.

### Keep public entries aligned

Maintain source and documentation in GitHub. The website deploys from `docs/`,
and the current File Exchange connection follows the default branch. PyPI
packages, EEGLAB catalogue updates and `.mltbx` assets require their own release
steps. Build matching packages from the recorded source and update the links
and this version table when publishing them.

Keep published archives fixed. Add a new Zenodo version for a subsequent
archival snapshot rather than describing the existing record as current source.
