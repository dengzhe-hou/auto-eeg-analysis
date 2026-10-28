# AEA for EEGLAB

Version 0.1.1, preview. Adds **Tools > AEA** to EEGLAB. The adapter copies the
current dataset to a separate study folder, prepares the AEA handoff, starts your
configured coding assistant in a terminal and opens the resulting HTML report.

## Install

1. Set up the [AEA repository and Python environment](https://dengzhe-hou.github.io/auto-eeg-analysis/GETTING_STARTED.html), and sign in to Codex CLI or Claude Code.
2. Download the [0.1.1 preview ZIP](https://github.com/dengzhe-hou/auto-eeg-analysis/releases/download/eeglab-v0.1.1-preview/aea-eeglab-0.1.1.zip). Remove any previous AEA plugin folder, then extract it into EEGLAB's `plugins` folder, giving `plugins/aea0.1.1/`. Alternatively copy this `aea` folder there. Install only one AEA plugin copy.
3. Restart EEGLAB. Open **Tools > AEA > Settings** and select your AEA checkout, the full path to its Python executable, and your assistant (`codex` or `claude`). Set the assistant's full executable path if it is not on MATLAB's PATH.

The Python field is the executable inside the environment, such as
`/path/to/env/bin/python` or `C:\path\to\env\python.exe`. An existing Conda
installation alone is not a configured environment. The plugin uses your
assistant's current model and permission settings; it does not store an API key.

## Use

1. Load continuous EEG or a dataset with at least two epochs in EEGLAB. Load samples into memory if the dataset uses memory mapping.
2. Choose **Export current dataset and prepare study**, select a new study folder and a recipe, or `custom` to choose with the assistant.
3. Choose **Start AEA for exported study**. Discuss the research question and missing choices, approve the plan, then proceed. Existing approved choices are reused.
4. After analysis, choose **Open study report**. The report is `report-stage/report.html` in the study folder.

Export and preparation do not call a model or perform an EEG analysis. Starting
the assistant may use your account's model credits. The adapter does not select
new analysis defaults or turn recipe selection into approval.

The original working EEG and its files are preserved. The copy uses EEGLAB's
standard float32 two-file `.set`/`.fdt` save. Events and processing history have
sidecar files; event codes are not assigned scientific condition meanings.
Continuous data and already epoched data remain distinct. Reader channel types
are recorded as software labels that still need physiological confirmation.

## Requirements and current validation

- AEA checkout with `tools/eeglab_bridge.py`; its Python environment includes MNE.
- EEGLAB with `pop_saveset`; MATLAB with `jsonencode` support.
- A desktop terminal for interactive launch. Linux supports `x-terminal-emulator` or `gnome-terminal`; macOS uses Terminal; Windows uses a new console.
- On a headless server, use the `session` command printed by the launch error in your own terminal.

The first release does not support exporting a single epoched trial. It raises
before writing rather than flattening it into continuous data. An existing
export is never overwritten; use another folder. A failed preparation can be
retried without re-exporting:

```text
python /path/to/aea/tools/eeglab_bridge.py prepare --project /path/to/study
python /path/to/aea/tools/eeglab_bridge.py session --project /path/to/study
```

GNU Octave/EEGLAB export, MNE import, units, events, epoch timing and command
routing are exercised by automated tests. On 2026-10-28, the preview with the
Windows/MATLAB fixes in this checkout passed a real Windows 11 desktop test with
MATLAB R2026a Update 2, EEGLAB 2026.0.0, Python 3.12.10 and MNE 1.11.0. This
covered menus, settings reload, continuous and four-epoch synthetic data, MNE
readback, terminal launch with labelled test clients, and report-menu opening in
Chrome. No live model or scientific analysis was run. macOS and Linux desktop
behavior remain untested. This preview is not yet in the EEGLAB extension catalogue.

Version 0.1.1 includes the MATLAB fixes; the original `eeglab-v0.1.0-preview` tag
predates them. Also update the AEA checkout (including `tools/install_skills.py`)
for the Windows skill-link fix. Windows skill discovery uses NTFS directory junctions without requiring
symlink privileges; other systems use relative directory symlinks.

[Project](https://github.com/dengzhe-hou/auto-eeg-analysis) ·
[EEGLAB plugin instructions](https://eeglab.org/tutorials/contribute/design_plugin.html)

Code is distributed under the MIT license bundled in the ZIP. EEGLAB and the
coding assistants are separate dependencies under their respective licenses.
