# AEA for MATLAB and EEGLAB

AEA connects EEGLAB datasets to a coding assistant and retains reusable EEG
analysis procedures. The toolbox includes the AEA 0.1.3 EEGLAB adapter,
22 skills, 10 recipes, templates and supporting tools.

Install the `.mltbx` file and run `aea_setup` with the folder containing
`eeglab.m`. Existing AEA plugin files are retained. Restart EEGLAB after a new
plugin installation. In Tools > AEA > Settings, set the AEA checkout folder to
the path returned by `aea_library_root`.

For the native route, choose backend `matlab`, leave Python blank, and select
your separately installed and signed-in Codex CLI or Claude Code executable.
Export a dataset to a new study folder, start the assistant, approve the
study-specific plan and open its saved report through EEGLAB.

The native helper covers explicit means from existing epochs, condition epoch
lists, a channel ROI and a time window. It saves numerical results, figures,
an HTML report and replay code. The broader resource library primarily uses
MNE-Python. See `resources/docs/MATLAB_NATIVE.md` and `resources/docs/EEGLAB.md`.

This candidate targets MATLAB R2026a or later. Windows R2026a is the locally
tested release. Other desktop platforms retain the documented adapter routes
and require platform testing. MATLAB Online is not a target for the desktop
client launch route. EEGLAB and coding assistants are separate dependencies.
No model credentials or participant datasets are included.

Code and skills use MIT. Recipes retain their declared licenses, normally
CC BY 4.0. See the bundled `LICENSE` and recipe citations.

Build from a checkout containing the packaging resource manifest with
`build_aea_matlab_toolbox(source_root, output_directory)`. The optional third
argument supplies a resource-manifest path when preparing from a saved source
snapshot. The build uses a new output directory and retains existing outputs.

https://github.com/dengzhe-hou/auto-eeg-analysis
