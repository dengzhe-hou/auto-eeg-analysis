# AEA for EEGLAB

Version 0.1.3 preview. Adds **Tools > AEA** to EEGLAB. The adapter copies the
current dataset to a separate study folder, prepares the AEA handoff, starts your
configured coding assistant in a terminal and opens the resulting HTML report.

Setting backend to `matlab` uses native EEGLAB preparation,
client launch and a bounded epoched-ERP helper without Python/MNE. See
`docs/MATLAB_NATIVE.md` in the matching checkout. This route is not
included in the older 0.1.2 ZIP. Use the matching checkout and
[0.1.3 preview ZIP](https://github.com/dengzhe-hou/auto-eeg-analysis/releases/tag/eeglab-v0.1.3-preview).
AEA 0.1.3 has been approved by the EEGLAB team and is listed in the
[official extension catalogue](https://sccn.ucsd.edu/eeglab/plugin_uploader/plugin_list_all.php).

## Install

For the native route, read `docs/MATLAB_NATIVE.md` in the matching checkout.
For the MNE route, the [Windows walkthrough](https://dengzhe-hou.github.io/auto-eeg-analysis/WINDOWS_FIRST_RUN.html)
includes client setup and executable paths. Version 0.1.3 adds a fifth Settings
field for the analysis backend.

1. Obtain the matching AEA checkout and sign in to Codex CLI or Claude Code. Choose MATLAB/EEGLAB for the native route, or set up the [Python/MNE environment](https://dengzhe-hou.github.io/auto-eeg-analysis/GETTING_STARTED.html) for the MNE route. The ZIP supplies the adapter, while the checkout supplies the AEA skills and procedures.
2. In EEGLAB, open **File > Manage EEGLAB extensions**, search for **AEA**, and install version **0.1.3**. For manual installation instead, extract `aea-eeglab-0.1.3.zip` into EEGLAB's `plugins` folder, giving `plugins/aea0.1.3/`, or copy this `aea` folder there. Remove any previous AEA plugin folder before a manual installation. Install only one AEA plugin copy.
3. Restart EEGLAB. Open **Tools > AEA > Settings** and select your AEA checkout, assistant (`codex` or `claude`), its executable, and backend (`matlab` or `mne`). Leave Python blank for `matlab`; for `mne`, select the full path to the configured environment's Python executable.

For `mne`, the Python field is the executable inside the environment, such as
`/path/to/env/bin/python` or `C:\path\to\env\python.exe`. An existing Conda
installation alone is not a configured environment. The plugin uses your
assistant's current model and permission settings; it does not store an API key.

## Use

1. Load continuous EEG or a dataset with at least two epochs in EEGLAB. Load samples into memory if the dataset uses memory mapping.
2. Choose **Export current dataset and prepare study**, select a new study folder and a recipe, or `custom` to choose with the assistant.
3. Choose **Start AEA for exported study**. Discuss the research question and missing choices, approve the plan, then proceed. Existing approved choices are reused.
4. After analysis, choose **Open study report**. Select the output folder containing `report-stage/report.html`; the native helper uses a fresh analysis output folder within the exported study.

Export and preparation do not call a model or perform an EEG analysis. Starting
the assistant may use your account's model credits. The adapter does not select
new analysis defaults or turn recipe selection into approval.

The original working EEG and its files are preserved. The copy uses EEGLAB's
standard float32 two-file `.set`/`.fdt` save. Events and processing history have
sidecar files; event codes are not assigned scientific condition meanings.
Continuous data and already epoched data remain distinct. Reader channel types
are recorded as software labels that still need physiological confirmation.

## Requirements and current validation

- AEA checkout with `AGENT_GUIDE.md` and the skills/procedures. The `mne` route also requires `tools/eeglab_bridge.py` and Python/MNE.
- EEGLAB with `pop_saveset`/`pop_loadset` and its DIPFIT dependency; MATLAB with `jsonencode` support. Python is not required for the native route.
- A desktop terminal for interactive launch. Linux supports `x-terminal-emulator` or `gnome-terminal`; macOS uses Terminal; Windows uses a new console.
- On a headless server, use the `session` command printed by the launch error in your own terminal.

The first release does not support exporting a single epoched trial. It raises
before writing rather than flattening it into continuous data. An existing
export is never overwritten; use another folder. A failed preparation can be
retried without re-exporting. For `mne`:

```text
python /path/to/aea/tools/eeglab_bridge.py prepare --project /path/to/study
python /path/to/aea/tools/eeglab_bridge.py session --project /path/to/study
```

For `matlab`, call `aea_prepare_matlab(study_folder)` in the initialized EEGLAB
environment, then use the Start AEA menu or `aea_launch_matlab(study_folder)`.

Native preparation, arithmetic, figures/report and fresh-process replay passed
on Windows 11 / MATLAB R2026a Update 2 / EEGLAB 2026.0.0 on 2026-10-29.
Codex/Claude launch routing used labelled test clients. The separate real-Claude
native test subsequently used Claude Code 2.1.312 (`claude-opus-5-5`, existing
`auto` mode) to read AEA skills/procedures, generate `analysis.m` and run MATLAB.
Independent first-delivery checks and fresh-process replay of the unchanged
entry point passed. The client read a test excerpt and documented reference
values despite the requested reading restriction; this is a functional
known-answer case, not blind evaluation or evidence of a skills benefit.
The native helper is bounded to explicit epoched ERP means, not all skills.
MacBook testing is left to external users and remains unverified.

GNU Octave/EEGLAB export, MNE import, units, events, epoch timing and command
routing are exercised by automated tests. On 2026-10-28, the preview with the
Windows/MATLAB fixes in this checkout passed a real Windows 11 desktop test with
MATLAB R2026a Update 2, EEGLAB 2026.0.0, Python 3.12.10 and MNE 1.11.0. This
covered menus, settings reload, continuous and four-epoch synthetic data, MNE
readback, terminal launch with labelled test clients, and report-menu opening in
Chrome. That initial test did not invoke a live model. A subsequent Windows test
with additional export-menu and terminal-environment fixes completed a real Codex
synthetic workflow, independent result/figure/report checks and a fresh-output
replay. The export-menu fix is included in 0.1.2; the terminal-environment fix
comes from the updated AEA checkout. The live-client
test required two Python execution approvals and does not establish unattended
operation or real EEG analysis reliability. On 2026-10-29, the same fixed synthetic
Windows route also passed with real Claude Code 2.1.312 (`claude-opus-5-5`, existing
`auto` permission mode), independent input/result/SVG/report checks and a fresh
replay. First-time CLI login and text-style initialization needed manual completion;
analysis commands needed no human execution approvals in that session. The client's
own HTML-title checker needed a parser correction; analysis outputs were unchanged.
Billed cost was unavailable. macOS/Linux desktop behavior remains untested.

The desktop runs above used the development sources labelled 0.1.1; 0.1.2
packages that MATLAB implementation with a new version label. Version 0.1.1's
published ZIP predates the export-menu fix. The original `eeglab-v0.1.0-preview`
tag also predates the initial MATLAB fixes. Update the AEA checkout (including `tools/install_skills.py`)
for the Windows skill-link fix. Windows skill discovery uses NTFS directory junctions without requiring
symlink privileges; other systems use relative directory symlinks.

[Project](https://github.com/dengzhe-hou/auto-eeg-analysis) ·
[EEGLAB plugin instructions](https://eeglab.org/tutorials/contribute/design_plugin.html)

Code is distributed under the MIT license bundled in the ZIP. EEGLAB and the
coding assistants are separate dependencies under their respective licenses.
