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
`tools/env/resolve_backend.py` with [the registry](../tools/env/backends.json) to
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
use the full setup inside WSL. See [skill installation](GETTING_STARTED.md#2-make-the-skills-visible-to-your-client).

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


---

## Windows: calling a conda environment's python directly

**The trap.** `<env>\python.exe` invoked *directly* is not the same as activating the environment.
Activation puts `<env>\Library\bin` on the DLL search path; calling the executable does not. NumPy
registers its own DLL directory, so it imports and computes fine — and so does `import mne`. The
process then **hard-crashes** the first time SciPy reaches LAPACK:

```
Windows fatal exception: 0xc06d007f
```

**Why it is hard to diagnose.** The failure is not where the cause is. Basic numerics work, imports
succeed, and only the code path doing an SVD (PCA whitening inside ICA) dies — 6 of 7 tests passed
before the crash on the machine that found it. The obvious suspects are all wrong: it is not
duplicate OpenMP (`KMP_DUPLICATE_LIB_OK` changes nothing) and not a PyPI/conda BLAS mix (installing
conda-forge's MKL build changes nothing). The cause is how the interpreter was invoked.

**Fix.** Activate, or go through conda:

```powershell
conda run -n aeais python -m pytest tools/tests/
```

**Why this is guarded and not merely documented.** `deploy_report.{sh,ps1}` pick an interpreter off
PATH. Someone who has put a conda environment directory on PATH without activating it — common —
would have that interpreter selected, pass the `import mne` check, and crash inside the test suite.
The report would then record a defect in AEA that is really an activation problem. `Select-Python`
therefore probes `scipy.linalg.svd` rather than an import: the operation that actually breaks.

This is the same class as the Microsoft Store `python3` stub — *present on PATH but not usable* —
except that it fails much later, where the evidence points at the wrong thing.

---

## Negative results worth recording

Findings that cost time and produced nothing. They are here so nobody re-spends that time.

**PowerShell 7 has no known breaking difference for `check_env.ps1`.** Checked against the
documented 5.1 → 7 removals: `Get-WmiObject` (removed in 7) is not used — GPU is probed by shelling
out to `nvidia-smi`, which behaves identically across versions; `Get-CimInstance`,
`Send-MailMessage` and `New-WebServiceProxy` are not used either. The one real difference is
`Out-File -Encoding UTF8`, which writes a BOM under 5.1 and none under 7 — already neutralised by
reading with `utf-8-sig`. The `pwsh` branch has still never *run*, so this is not a guarantee; it
does mean the residual risk is low rather than unknown.

**`.sh` files carry no UTF-8 BOM** (a BOM would break the shebang on Linux), and
`resolve_backend.py` imports only the standard library. Both were hypothesised as portability
risks and disproved before being reported.

**Test-count differences across platforms are skips, not failures.** A Windows run reporting
`187 passed` against Linux's `188 passed` is the same 189 collected tests: Windows adds one skip,
because `test_env_probe_emits_valid_json_when_optional_packages_are_missing` needs a POSIX shell and
skips when only the WSL `bash.exe` launcher is present. Compare `--collect-only` totals, not pass
counts.
