# Use AEA from EEGLAB

The preview extension adds **Tools > AEA**. Export the current EEG dataset,
prepare a separate study folder, open your coding assistant and return to the
saved report from EEGLAB. Analysis still uses your approved study choices and
AEA's existing skills and recipes, mainly with MNE-Python.

## Install the preview

First complete [AEA setup](GETTING_STARTED.md) and sign in to your chosen Codex
CLI or Claude Code client. The plugin does not include Python, MNE or a model.

Copy [extensions/eeglab/aea](https://github.com/dengzhe-hou/auto-eeg-analysis/tree/main/extensions/eeglab/aea)
into your EEGLAB `plugins` folder and restart EEGLAB. An installable ZIP can be
built from the AEA checkout:

```bash
python tools/package_eeglab_plugin.py --output aea-eeglab-0.1.0.zip
```

Extract it inside `plugins`, yielding `plugins/aea0.1.0/`. Avoid installing both
the copied folder and ZIP version at the same time.

Open **Tools > AEA > Settings** and set the AEA checkout folder, its Python
executable, assistant choice and assistant executable. These are local settings.
No model is selected and no credentials are requested or saved by the plugin.

## Start a study

1. Load the EEG dataset in EEGLAB.
2. Choose **Export current dataset and prepare study**, and select a new study folder. Choose a recipe or `custom` to discuss the task with AEA.
3. Choose **Start AEA for exported study**. The assistant reads the exported facts and asks about missing scientific choices before their dependent analyses. Keep an existing approved plan when present.
4. When the analysis produces `report-stage/report.html`, choose **Open study report**.

The export is a copy of the current dataset, which may already have undergone
processing. AEA records its history and does not assume it is acquisition-raw or
automatically re-run ICA or epoching. The data copy uses EEGLAB's float32 save;
MNE reads its microvolts as volts. Dataset/participant identity, condition meanings
and actual channel types still need confirmation.

## What is checked

The bridge compares the imported channel count, sampling rate, samples and epoch
count with the EEGLAB export. Automated tests exercise continuous and epoched
exports against real EEGLAB functions and MNE, compare sample values and event
timing, and check that the original working EEG is preserved. Preparation itself
does not invoke a model.

GNU Octave checks do not establish MATLAB GUI compatibility. The preview's
MATLAB dialog, desktop terminal launch and report-opening behavior must also be
tested on the target MATLAB desktop. This extension has not been registered in
the official EEGLAB catalogue.

## Current limits

- Export supports continuous data and at least two epochs, with samples loaded in memory. A single epoched trial fails explicitly before export.
- Choose a new folder for a different input; the previous exported `.set`/`.fdt` is not overwritten.
- AEA remains a separate configured library/environment; the plugin is its EEGLAB entry point.
- Linux desktop launch requires `x-terminal-emulator` or `gnome-terminal`. For a headless server, run the printed `session` command in an existing terminal.
- Missing MNE or an unavailable assistant executable produces a setup error. Exported data remain available to repair preparation.

See the [plugin README](https://github.com/dengzhe-hou/auto-eeg-analysis/tree/main/extensions/eeglab/aea)
for command-line retry instructions and requirements. The adapter follows
[EEGLAB's plugin interface](https://eeglab.org/tutorials/contribute/design_plugin.html);
official catalogue distribution requires a separate submission and approval.
