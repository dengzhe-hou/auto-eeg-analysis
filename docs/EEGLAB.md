# Use AEA from EEGLAB

**AEA 0.1.3 has been approved by the EEGLAB team and is listed in the
[official extension catalogue](https://sccn.ucsd.edu/eeglab/plugin_uploader/plugin_list_all.php).**

The preview extension adds **Tools > AEA**. Export the current EEG dataset,
prepare a separate study folder, open your coding assistant and return to the
saved report from EEGLAB. Analysis still uses your approved study choices and
AEA's existing skills and recipes, mainly with MNE-Python.

The 0.1.3 preview also has a [native MATLAB route](MATLAB_NATIVE.md)
for preparation, client launch and bounded epoched ERP means, figures and reports
without Python/MNE. It is not in the published 0.1.2 ZIP and does not port all skills.

For a first installation on Windows, follow the
[first-report walkthrough](WINDOWS_FIRST_RUN.md), including client login and
commands to find the executable paths. Version 0.1.3 adds a fifth field for the backend.

## Install the preview

Sign in to your chosen Codex CLI or Claude Code client and obtain the matching
AEA checkout. Choose `matlab` for native preparation and bounded epoched ERP
analysis; Python is not required. Choose `mne` after completing
[Python/MNE setup](GETTING_STARTED.md). The plugin does not include a model.

For an existing AEA checkout, save local edits and run `git pull --ff-only`
before installing a published plugin. The ZIP supplies the MATLAB adapter; the
checkout supplies the skills/procedures and the Python bridge for backend `mne`.
Version 0.1.3 requires a matching checkout: use tag `eeglab-v0.1.3-preview`
or an updated `main`.

In EEGLAB, open **File > Manage EEGLAB extensions**, search for **AEA**, and
install version **0.1.3**. Then restart EEGLAB and configure the plugin below.
The separate AEA checkout and signed-in coding client are still required for
assisted runs.

For manual installation, download the
[0.1.3 preview ZIP](https://github.com/dengzhe-hou/auto-eeg-analysis/releases/download/eeglab-v0.1.3-preview/aea-eeglab-0.1.3.zip)
for either native MATLAB or MNE. The older 0.1.2 ZIP supports the MNE route.
You can also build the plugin from its matching checkout:

```bash
python tools/package_eeglab_plugin.py --output aea-eeglab-0.1.3.zip
```

For manual installation, remove any previous AEA plugin folder, then extract the ZIP inside `plugins`, yielding
`plugins/aea0.1.3/` for this version. Install only one AEA plugin copy.

Open **Tools > AEA > Settings** and set the AEA checkout folder, assistant choice,
assistant executable and backend. Leave Python blank for `matlab`; for `mne`,
select the configured Python executable. These are local settings.
No model is selected and no credentials are requested or saved by the plugin.

## Start a study

1. Load the EEG dataset in EEGLAB.
2. Choose **Export current dataset and prepare study**, and select a new study folder. Choose a recipe or `custom` to discuss the task with AEA.
3. Choose **Start AEA for exported study**. The assistant reads the exported facts and asks about missing scientific choices before their dependent analyses. Keep an existing approved plan when present.
4. When the analysis produces `report-stage/report.html`, choose **Open study report** and select its analysis output folder. The native helper uses a fresh output folder inside the exported study.

The export is a copy of the current dataset, which may already have undergone
processing. AEA records its history and does not assume it is acquisition-raw or
automatically re-run ICA or epoching. The data copy uses EEGLAB's float32 save;
MNE reads its microvolts as volts, while native EEGLAB retains microvolts.
Dataset/participant identity, condition meanings
and actual channel types still need confirmation.

## What is checked

Each route compares the imported channel count, sampling rate, samples and epoch
count with the EEGLAB export. Automated tests exercise continuous and epoched
exports against real EEGLAB functions and MNE, compare sample values and event
timing, and check that the original working EEG is preserved. Preparation itself
does not invoke a model. The native route also has real MATLAB preparation,
arithmetic/report and fresh-process replay checks. Real Claude Code also generated
and executed a native MATLAB entry point, with independent first-delivery checks
and replay. That client read documented reference values; this is a known-answer
functional case. See [native validation](MATLAB_NATIVE.md#validation-status).

On 2026-10-28, the preview with the fixes in this checkout passed real desktop
tests on Windows 11, MATLAB R2026a Update 2, EEGLAB 2026.0.0, Python 3.12.10 and
MNE 1.11.0. The initial test covered menus, settings save/reload, continuous and
four-epoch synthetic data export/readback, terminal launch with labelled test
clients, and report-menu opening in Chrome.

A subsequent test on the same Windows configuration used the actual EEGLAB
menus to export four synthetic epochs, start Codex CLI 0.165.0-alpha.1.2 and open
its generated report. The client used its existing gpt-6.1-sol/xhigh configuration;
two Python commands required user approval under its existing permission policy.
Independent checks of all 808 input samples, the three known-answer measurements,
actual SVG trace coordinates and displayed report values passed. Replaying the
generated script in a new output directory passed the same checks. The export
callback was corrected to preserve the working EEG history and avoid a new-dataset
dialog. Initial failures were retained; the Windows client-startup fix is described below.
This is a synthetic engineering integration test, without statistical inference
or evidence of general analysis reliability.

On 2026-10-29, the same fixed fixture passed the complete Windows route with
Claude Code 2.1.312, model `claude-opus-5-5` and its existing `auto` permission
mode. The actual EEGLAB export/start/report menus, all-sample MNE checks,
independent numerical/SVG/report checks and a fresh-directory replay passed.
First-time CLI sign-in and text-style initialization needed manual completion;
analysis commands raised no human execution-approval prompts in that session.
The client's own HTML-title checker initially failed because it included the
inline SVG title. Its parser was corrected; the analysis and report were unchanged.
Session token usage was recorded, but billed cost was unavailable and was not
reported as zero. macOS/Linux desktop behavior remains untested.
MacBook validation is left to external contributors; platform tests should retain
the actual software versions, commands and artifacts.

The desktop runs above used development sources labelled 0.1.1. Preview 0.1.2
packages the tested MATLAB export-menu fix with a new version label. The Windows
terminal-environment fix is part of the companion AEA checkout, which must also
be updated. The historical 0.1.1 ZIP has not been changed.

The 0.1.1 preview ZIP includes the initial MATLAB compatibility fixes. The original
`eeglab-v0.1.0-preview` tag predates them. Also update your AEA checkout for the
Windows skill-link fix in `tools/install_skills.py`.

## Current limits

- Export supports continuous data and at least two epochs, with samples loaded in memory. A single epoched trial fails explicitly before export.
- Choose a new folder for a different input; the previous exported `.set`/`.fdt` is not overwritten.
- AEA remains a separate configured library/environment; the plugin is its EEGLAB entry point.
- Linux desktop launch requires `x-terminal-emulator` or `gnome-terminal`. For a headless server, run the printed `session` command in an existing terminal.
- Backend `mne` requires Python/MNE. Backend `matlab` requires the matching native functions and EEGLAB dependencies; it does not silently switch to MNE when an analysis is unsupported.

See the [plugin README](https://github.com/dengzhe-hou/auto-eeg-analysis/tree/main/extensions/eeglab/aea)
for command-line retry instructions and requirements. The adapter follows
[EEGLAB's plugin interface](https://eeglab.org/tutorials/contribute/design_plugin.html)
and is distributed through the official catalogue following approval.

## Windows client startup

If Codex pauses with `TERM is set to "dumb"`, update the AEA checkout. The Windows
launcher removes that inherited value when creating a new interactive console.
It preserves the remaining environment and does not select a model or permissions.

Check the selected executable with `--version` and `login status`. An older npm
CLI may reject configuration written by a newer desktop app. Use an installed
CLI version that understands the existing configuration rather than changing
the model or permission settings to accommodate an older binary.

The tested desktop-app bundled Codex CLI 0.165.0-alpha.1.2 reported a missing
background-service package when started outside the app. In that test, a local
`.cmd` launcher calling the same binary with `--no-daemon %*` allowed it to run
with its existing model, login and permission settings. Select such a launcher
in Settings before exporting when using that tested configuration. Prefer a
normal standalone CLI installation for routine setup.

The exported study stores its own client executable in `AEA_BRIDGE_CONFIG.json`.
Changing Settings affects new exports. To repair an existing study's client
installation, update that field explicitly and keep the original configuration
with the study's troubleshooting record.
