# Platform Support

AEA runs on macOS, Linux, and Windows. Capability differs by platform; this page is the source of truth.

For the complete clone, environment, skill installation, and first-analysis sequence,
start with [Getting started](GETTING_STARTED.md). Launch the agent from the AEA
repository root with the `aeais` environment active. Client installation and model
access are separate from the Python environment.

## Tier 1 — full support: macOS / Linux

Everything in the pipeline works natively:
- MNE-Python (full)
- FreeSurfer for individual-MRI source localization
- Pycrostates for microstates
Recommended hardware: ≥16 GB RAM (32 GB if doing source localization on individual MRI).
Apple Silicon is supported. The [FreeSurfer 7.4.1 macOS release](https://surfer.nmr.mgh.harvard.edu/pub/dist/freesurfer/7.4.1/)
ships Intel x86_64 packages; a native arm64 installer is available in
[FreeSurfer 8.0.0](https://surfer.nmr.mgh.harvard.edu/ftp/dist/freesurfer/8.0.0/).

## Tier 2 — degraded support: Windows native

What works:
- **MNE-Python path entirely** — preprocessing, ICA (mne-icalabel), epoching, ERP, TFR, microstate (Pycrostates), template-MRI source localization (fsaverage), cluster permutation (MNE), figures, report.

What does NOT work natively:
- **FreeSurfer** — no native Windows build. Required for individual-MRI source localization. **Workaround: WSL2** with FreeSurfer installed inside WSL. The env probe (`check_env.ps1`) detects WSL automatically and reports its FreeSurfer status.
## Tier 3 — not supported

- Driving GUI applications (Brainstorm, BrainVision Analyzer, Curry, Neuroscan SCAN) via accessibility / scripting. AEA only consumes their exports (`.set` / `.fif` / `.bdf`).
- Real-time / online EEG analysis. AEA is offline-only.

## Environment probe outputs

`tools/env/check_env.sh` (mac/linux) and `check_env.ps1` (Windows) write `ENVIRONMENT.json`. Every skill reads this file before invoking a backend. Missing backends produce an explicit, logged degradation — never a silent fallback.

Schema fields:
- `python` / `python_packages.{mne, mne_bids, mne_icalabel, autoreject, pycrostates, mne_connectivity, numpy, scipy, matplotlib}`
- `freesurfer` (requires `FREESURFER_HOME`; on Windows, probed inside WSL)
- `gpu` (NVIDIA via nvidia-smi or Apple-MPS)
- `capabilities.*` — derived map of which skill paths are reachable

The current probe also records `optional_packages`, `matlab_engine`, `eeglab`, and
`fieldtrip`. Entries in `capabilities` describe dependency requirements; they are
not successful execution or numerical-certification results. Use
`tools/env/resolve_backend.py` with [the registry](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/main/tools/env/backends.json) to
resolve a supported capability and record its required numerical conventions.
See [certification coverage](CERTIFICATION_LEVELS.md) for the measured evidence.

## How to set up each platform

### macOS / Linux

```bash
# 1. Python env
conda env create -f environment.yml
conda activate aeais

# 2. FreeSurfer (optional, only for individual-MRI source localization)
# Install FreeSurfer for your OS and CPU, then:
export FREESURFER_HOME=/path/to/freesurfer
source "$FREESURFER_HOME/SetUpFreeSurfer.sh"

# 3. Probe from the AEA repository root
bash tools/env/check_env.sh
```

### Windows native (MNE path only)

```powershell
# 1. Python env (Miniconda/Anaconda)
conda env create -f environment.yml
conda activate aeais

# 2. Probe (Windows PowerShell 5.1)
powershell -ExecutionPolicy Bypass -File tools/env/check_env.ps1
```

PowerShell 7 users can use `pwsh -File tools/env/check_env.ps1`. The local skill
installer creates directory links, so Windows must permit symlink creation, for
example through Developer Mode or an appropriately privileged terminal. Otherwise,
use the full setup inside WSL. See [skill installation](GETTING_STARTED.md#3-set-up-an-agent-optional).

### Windows + WSL2 for FreeSurfer

```powershell
# Inside Windows PowerShell:
wsl --install -d Ubuntu-22.04
```

Inside WSL, install the Linux environment and FreeSurfer:

```bash
sudo apt install -y tcsh libgomp1  # FreeSurfer deps
# Download FreeSurfer for Ubuntu, install to /usr/local/freesurfer
echo 'export FREESURFER_HOME=/usr/local/freesurfer' >> ~/.bashrc
echo 'source $FREESURFER_HOME/SetUpFreeSurfer.sh'   >> ~/.bashrc
source ~/.bashrc
```

Back in Windows, the probe checks the WSL `FREESURFER_HOME` value:

```powershell
powershell -ExecutionPolicy Bypass -File tools/env/check_env.ps1
```

That availability check does not execute FreeSurfer or route analysis jobs into
WSL. Run individual-MRI processing in the Linux environment where FreeSurfer is
installed and keep its inputs and outputs accessible to the analysis.

## Known gotchas

- **`mne-icalabel`**: `environment.yml` includes ONNX Runtime for the ICLabel inference path. PyTorch and MPS are not required by this setup.
- **`pyprep` for RANSAC bad-channel detection**: already included in the pip section of `environment.yml`. If the probe reports it missing, confirm the active environment and complete its installation.
- **Optional metrics**: `specparam`, `antropy`, `statsmodels`, and `tensorpac` are probed but are not installed by the core environment file. Install the packages needed by the selected analysis and rerun the probe.
- **Template MRI**: the fsaverage source-localization path fetches template assets through MNE if they are not already cached. The environment probe does not download or validate those assets.

## Windows environment activation

Activate `aeais` or use `conda run`; do not invoke a conda environment's
`python.exe` directly. Without activation, SciPy can fail at LAPACK/SVD with
`Windows fatal exception: 0xc06d007f` even when NumPy and MNE import successfully.
The deployment report probes an actual SVD operation before selecting Python.

```powershell
conda run -n aeais python -m pytest tools/tests/
```

The PowerShell 7 branch has been inspected but not executed. Probe JSON is read with
`utf-8-sig` to support both PowerShell 5.1 and 7 encodings. A Windows test count may
be lower because a POSIX-shell test is skipped when only the WSL launcher is
available; compare collected tests and skip reasons.

The [historical portability record](https://github.com/dengzhe-hou/auto-eeg-analysis/blob/7597b6aa2e82355d56703c81621979b3ff1d45c0/docs/PLATFORM_SUPPORT.md#windows-calling-a-conda-environments-python-directly)
retains the crash investigation, unsuccessful OpenMP/BLAS workarounds, PowerShell
compatibility inspection and original cross-platform test counts.
