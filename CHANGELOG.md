# Versions and changes

## Choose a version

The website and setup commands describe **`main`**, which includes fixes and examples
added after the latest tagged release, **v0.3.2**. The tag is a fixed historical
snapshot; it does not receive later fixes.

- **Use `main`** for the current instructions, saved-analysis replay helpers and
  complete N400 tutorial. Record the commit used for each study.
- **Use `v0.3.2`** when reproducing that release's specifications. Keep its original
  configuration and study environment; the current tutorial scripts are not in it.
  The [coverage record](docs/CERTIFICATION_LEVELS.md) identifies certified outputs
  and configurations. A newer checkout does not certify every generated analysis.

For a separate checkout of the fixed release:

```bash
git clone --branch v0.3.2 --depth 1 https://github.com/dengzhe-hou/auto-eeg-analysis.git aea-v0.3.2
```

Follow the setup guide **inside that checkout**. Do not mix instructions from `main`
with missing helpers in the older release.

## Changes on main since v0.3.2

These changes have not been assigned a new library release tag. EEGLAB plugin
previews use separate tags.

- Released EEGLAB plugin preview 0.1.3 with a selectable native
  MATLAB route: EEGLAB preparation/readback, Codex/Claude terminal launch and
  explicit epoched ERP means with figures, HTML report and fresh-process replay.
  This route does not require Python/MNE; the existing MNE route remains available.
  Native runtime and desktop checks passed on the fixed Windows synthetic case.
  Real Claude Code generated and executed a study-local MATLAB entry point;
  independent first-delivery checks and fresh-process replay passed. It also
  read documented reference values, so this is functional known-answer evidence,
  not blind evaluation. All skills are not translated to MATLAB.
  See the [plugin preview](https://github.com/dengzhe-hou/auto-eeg-analysis/releases/tag/eeglab-v0.1.3-preview).
  Official catalogue inclusion requires a separate application. The library
  release remains v0.3.2.

- Added a preview EEGLAB extension with a Tools menu, dataset/event/history
  export, study preparation, interactive Codex/Claude handoff and a report entry.
  Automated checks exercise real EEGLAB/Octave exports and MNE import. MATLAB
  desktop synthetic workflows with real Codex and Claude clients have passed
  independent result checks and replay on Windows; official EEGLAB catalogue
  registration remains pending. Plugin preview 0.1.2 packages the tested export-menu
  fix. Its companion Python bridge and Windows startup fix come from the updated
  AEA checkout. The library release version remains v0.3.2.
- Reorganized all 22 skills into compact entrypoints with detailed procedures
  and method background loaded from linked reference files. Added section loading
  with source receipts, a channel-identity check before average referencing,
  a memory-bounded SampEn helper and a bounded structured ERP report checker.
  Checks have stated scopes; they do not certify arbitrary generated workflows.
- Spectral templates now require the task's or approved plan's scientific
  settings, including Welch segment/taper/overlap/FFT/DC choices, requested band
  definitions and aggregation, and the selected alpha estimator. Example values
  are labelled; short epochs and missing dependencies no longer silently change
  the approved estimator or segment duration. Existing saved runs are unchanged.
- Redesigned the homepage and README around the library, quickstart and worked
  examples; retained the validation coverage and original evidence links.
- Corrected time-frequency baseline units, Morlet
  padding and the explicit `zero_mean` setting; separated constant segments,
  low-amplitude warnings and rapid-change diagnostics in QC. These changes can affect newly
  generated scripts and results. See [TFR](skills/eeg-tfr/SKILL.md) and
  [QC](skills/eeg-qc/SKILL.md) for the current conventions.
- Corrected N100 trial pairing and Flankers inference,
  including restricted permutations. Original and corrected results, assumptions
  and source snapshots remain linked from [Worked examples](docs/EXAMPLES.md).
- Added saved-code/environment capture and replay, a tested
  Linux package snapshot, and expanded numerical/API checks. See
  [Replay](docs/REPLAY.md) and [Platform support](docs/PLATFORM_SUPPORT.md).
- Added the complete fixed-cohort N400 recipe runner, saved numerical
  results and compact arrays for figure reproduction without raw EEG. The runner
  reads the official OSF `ses-N400` layout and existing sessionless caches directly.
  Full runs check figure fonts before reading EEG or creating outputs; statistical
  replay does not require fonts. Setup distinguishes this fixed tutorial from the
  agent workflow and includes a copy-ready N400 dataset brief. Full runs also
  check all 20 participants' required input files before reading EEG or creating
  outputs, print stage progress, and document failure retries and completion checks.
- Corrected ICLabel probability shapes and class-name
  examples. Full seven-class probabilities require `iclabel_label_components`;
  the existing component-rejection logic was unchanged.
- Focused the default tree on the library, added a workflow
  diagram and N400 figure, and clarified data preparation, study adaptation and help.
  Historical research materials remain accessible through existing source snapshots.

The [commit comparison](https://github.com/dengzhe-hou/auto-eeg-analysis/compare/v0.3.2...main)
contains the complete changes.

## Update an existing checkout

Save your local edits first. From a checkout on `main`:

```bash
git pull --ff-only
python tools/install_skills.py --agent codex
```

Use `--agent claude` for Claude Code, then restart the client. Existing linked skills
track file changes automatically; rerunning the installer also discovers new skills.
The general `environment.yml` is unchanged from v0.3.2. If a later update changes it,
follow its setup instructions in a separate environment before starting a new study.

An update changes the instructions the agent reads. It does not rewrite a saved
program or reproduce previous results automatically. Keep completed studies' code,
plans and captured environments unchanged; use [replay](docs/REPLAY.md) to rerun them.
