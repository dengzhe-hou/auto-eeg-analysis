# AEA environment probe  -  Windows (PowerShell).
# Writes ENVIRONMENT.json describing which capabilities are available.
# Usage: powershell -File tools/env/check_env.ps1 [output-path]   (5.1, always present)
#        pwsh tools/env/check_env.ps1 [output-path]           (PowerShell 7)
#
# MNE-Python is the DEFAULT and reference backend: every committed certified value was produced
# by it. EEGLAB and FieldTrip are selectable alternatives, validated against the reference on all
# five certified ERP CORE components (https://github.com/dengzhe-hou/auto-eeg-analysis/blob/995f53d42cc74205b164e8711d4b289b8c2ad3a1/tools/benchmark/CROSS_TOOLBOX_EVAL.md), so schema 3 probes
# them. Availability alone does not make one usable: cross-toolbox agreement is a property of how
# completely the specification is pinned, not of the toolbox. Resolve with
# tools/env/resolve_backend.py and always emit its `pin` list.
# (Reading EEGLAB .set files is handled inside MNE via mne.io.read_raw_eeglab; no MATLAB needed.)

param(
  [string]$Out = "ENVIRONMENT.json"
)

$ErrorActionPreference = "Continue"
$ts = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

function Probe-Python {
  $py = Get-Command python -ErrorAction SilentlyContinue
  if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
  if ($py) {
    $ver = & $py.Source -c "import sys; print(sys.version.split()[0])" 2>$null
    return @{ available = $true; version = $ver; path = $py.Source }
  }
  return @{ available = $false }
}

function Probe-Pkg($importName, $pipName) {
  $py = Get-Command python -ErrorAction SilentlyContinue
  if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
  if (-not $py) { return @{ available = $false; pip = $pipName } }
  $ver = & $py.Source -c "import $importName; print(getattr($importName, '__version__', 'unknown'))" 2>$null
  if ($LASTEXITCODE -eq 0 -and $ver) {
    return @{ available = $true; version = $ver.Trim(); pip = $pipName }
  }
  return @{ available = $false; pip = $pipName }
}

function Probe-FreeSurfer {
  # Native Windows FreeSurfer is not supported. Check WSL.
  $wsl = Get-Command wsl -ErrorAction SilentlyContinue
  if ($wsl) {
    $fsh = & wsl bash -c 'echo $FREESURFER_HOME' 2>$null
    if ($fsh -and ($fsh.Trim() -ne "")) {
      return @{ available = $true; via = "wsl"; path = $fsh.Trim() }
    }
    return @{ available = $false; hint = "WSL detected but FREESURFER_HOME not set inside WSL; install FreeSurfer in WSL2 and export FREESURFER_HOME" }
  }
  return @{ available = $false; hint = "FreeSurfer requires WSL2 on Windows. Source on individual MRI unavailable; template (fsaverage) path still works via MNE." }
}

function Probe-MatlabEngine {
  # Either MATLAB or GNU Octave can drive the EEGLAB/FieldTrip backends. AEA's cross-toolbox
  # validation ran under Octave; MATLAB is assumed equivalent but was not verified.
  $ml = Get-Command matlab -ErrorAction SilentlyContinue
  if ($ml) {
    $ver = (& $ml.Source -batch "disp(version)" 2>$null | Select-Object -Last 1)
    return @{ available = $true; engine = "matlab"; version = "$ver".Trim(); path = $ml.Source }
  }
  $oc = Get-Command octave-cli -ErrorAction SilentlyContinue
  if (-not $oc) { $oc = Get-Command octave -ErrorAction SilentlyContinue }
  if ($oc) {
    $ver = (& $oc.Source --no-gui --quiet --eval "disp(version)" 2>$null | Select-Object -Last 1)
    return @{ available = $true; engine = "octave"; version = "$ver".Trim(); path = $oc.Source }
  }
  return @{ available = $false; hint = "no matlab or octave on PATH; EEGLAB/FieldTrip backends unavailable" }
}

function Probe-EEGLAB {
  $root = $env:EEGLAB_PATH
  if ($root -and (Test-Path (Join-Path $root "eeglab.m"))) {
    return @{ available = $true; path = $root }
  }
  return @{ available = $false; hint = "set EEGLAB_PATH to an install dir containing eeglab.m" }
}

function Probe-FieldTrip {
  $root = $env:FIELDTRIP_PATH
  if ($root -and (Test-Path (Join-Path $root "ft_defaults.m"))) {
    return @{ available = $true; path = $root; version = (Split-Path $root -Leaf) }
  }
  return @{ available = $false; hint = "set FIELDTRIP_PATH to an install dir containing ft_defaults.m" }
}

function Probe-GPU {
  $smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
  if ($smi) {
    $name = (& nvidia-smi --query-gpu=name --format=csv,noheader 2>$null | Select-Object -First 1)
    return @{ available = $true; vendor = "nvidia"; name = $name }
  }
  return @{ available = $false }
}

$obj = [ordered]@{
  schema_version = "3"
  backend        = @{
    default   = "mne"
    reference = "mne"
    note      = "MNE-Python produced every committed certified value. EEGLAB and FieldTrip are selectable alternatives with MEASURED agreement (https://github.com/dengzhe-hou/auto-eeg-analysis/blob/995f53d42cc74205b164e8711d4b289b8c2ad3a1/tools/benchmark/CROSS_TOOLBOX_EVAL.md); resolve with tools/env/resolve_backend.py, which also emits the numerical conventions that must be pinned."
  }
  probed_at      = $ts
  os = @{
    name    = "Windows"
    release = [System.Environment]::OSVersion.Version.ToString()
  }
  python             = Probe-Python
  python_packages    = @{
    mne              = Probe-Pkg "mne" "mne"
    mne_bids         = Probe-Pkg "mne_bids" "mne-bids"
    mne_icalabel     = Probe-Pkg "mne_icalabel" "mne-icalabel"
    autoreject       = Probe-Pkg "autoreject" "autoreject"
    pycrostates      = Probe-Pkg "pycrostates" "pycrostates"
    mne_connectivity = Probe-Pkg "mne_connectivity" "mne-connectivity"
    pyprep           = Probe-Pkg "pyprep" "pyprep"
    numpy            = Probe-Pkg "numpy" "numpy"
    scipy            = Probe-Pkg "scipy" "scipy"
    scikit_learn     = Probe-Pkg "sklearn" "scikit-learn"
    matplotlib       = Probe-Pkg "matplotlib" "matplotlib"
  }
  optional_packages  = @{
    specparam   = Probe-Pkg "specparam" "specparam"
    antropy     = Probe-Pkg "antropy" "antropy"
    statsmodels = Probe-Pkg "statsmodels" "statsmodels"
    tensorpac   = Probe-Pkg "tensorpac" "tensorpac"
  }
  freesurfer    = Probe-FreeSurfer
  matlab_engine = Probe-MatlabEngine
  eeglab        = Probe-EEGLAB
  fieldtrip     = Probe-FieldTrip
  gpu           = Probe-GPU
  capabilities = @{
    "preprocess.mne"          = "requires python_packages.mne"
    "preprocess.ransac"       = "requires python_packages.pyprep"
    "ica.mne_icalabel"        = "requires python_packages.mne_icalabel"
    "stats.mne_cluster"       = "requires python_packages.mne"
    "stats.mixed_anova"       = "requires optional_packages.statsmodels"
    "microstate.pycrostates"  = "requires python_packages.pycrostates"
    "connectivity.mne"        = "requires python_packages.mne_connectivity"
    "spectral.specparam"      = "requires optional_packages.specparam"
    "complexity.antropy"      = "requires optional_packages.antropy"
    "connectivity.pac"        = "requires optional_packages.tensorpac"
    "source.mne_template"     = "requires python_packages.mne (fsaverage shipped)"
    "source.mne_individual"   = "requires freesurfer (WSL on Windows) for individual MRI"
    "erp.preprocess_average.mne"        = "requires python_packages.mne"
    "erp.preprocess_average.eeglab"     = "requires eeglab + matlab_engine"
    "erp.preprocess_average.fieldtrip"  = "requires fieldtrip + matlab_engine"
    "ica.label.eeglab"                  = "requires eeglab + matlab_engine + the ICLabel plugin"
    "stats.cluster_permutation.fieldtrip" = "requires fieldtrip + matlab_engine"
  }
}

$obj | ConvertTo-Json -Depth 10 | Out-File -FilePath $Out -Encoding UTF8

Write-Host "Wrote $Out"
Write-Host "Summary:"
Write-Host "  Python:     $($obj.python.version)"
Write-Host "  MNE:        $($obj.python_packages.mne.version)"
Write-Host "  pycrostates:$($obj.python_packages.pycrostates.version)"
Write-Host "  optional:   specparam=$($obj.optional_packages.specparam.available) antropy=$($obj.optional_packages.antropy.available) statsmodels=$($obj.optional_packages.statsmodels.available)"
Write-Host "  FreeSurfer: $($obj.freesurfer.available)"
Write-Host "  GPU:        $($obj.gpu.name)"
Write-Host "  engine:     $($obj.matlab_engine.engine) $($obj.matlab_engine.version)"
Write-Host "  EEGLAB:     $($obj.eeglab.available)  FieldTrip: $($obj.fieldtrip.available)"
