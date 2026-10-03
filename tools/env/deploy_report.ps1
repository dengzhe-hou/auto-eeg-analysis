# AEA cold-start report  -  Windows (PowerShell).
#
#   powershell -File tools/env/deploy_report.ps1     (Windows PowerShell 5.1, always present)
#   pwsh tools/env/deploy_report.ps1                 (PowerShell 7, if installed)
#   -> AEA_DEPLOY_REPORT.md
#
# Same contract as deploy_report.sh: probes the machine, resolves a backend, runs the test suite,
# writes ONE Markdown file with home paths redacted to `~`. Nothing is uploaded and nothing is
# installed; the ~1.5 GB test dataset is not needed.
#
# NOTE: this script HAS now been run on a real Windows machine under PowerShell 5.1, on both the
# normal and the BLOCKED route. It has NOT been run under PowerShell 7, where it takes the `pwsh`
# branch below. If it is the first thing that fails there, that is a genuinely useful result  -
# send the report anyway.

param(
  [string]$Out = "AEA_DEPLOY_REPORT.md"
)

$ErrorActionPreference = "Continue"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $root

# Pick an interpreter that actually WORKS, preferring one that can run the suite.
# `python3` on Windows is a Microsoft Store stub: it is on PATH, satisfies Get-Command, and has no
# packages at all. Selecting it produces a FALSE failure report that blames AEA for the wrong
# interpreter. Require the candidate to actually execute before trusting it.
function Select-Python {
  # An explicit AEA_PYTHON is an instruction, not a hint. Honour it if it runs at all -
  # silently substituting a "better" interpreter would hide the very environment the tester
  # meant to report on.
  if ($env:AEA_PYTHON) {
    & $env:AEA_PYTHON -c "import sys" 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { return $env:AEA_PYTHON }
    Write-Host "AEA_PYTHON is set to '$env:AEA_PYTHON' but it does not run."
    return $null
  }
  $cands = @("python", "python3", "py")
  $first = $null
  foreach ($c in $cands) {
    if (-not (Get-Command $c -ErrorAction SilentlyContinue)) { continue }
    & $c -c "import sys" 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { continue }          # a Store stub dies here
    if (-not $first) { $first = $c }
    # `import mne` is NOT sufficient. An interpreter inside a conda env that was never ACTIVATED
    # imports numpy and mne fine -- numpy registers its own DLL directory -- then hard-crashes the
    # process the first time scipy reaches LAPACK, because <env>\Library\bin is missing from the
    # DLL search path: `Windows fatal exception: 0xc06d007f`. It surfaces only in the one test
    # doing PCA whitening, so 6 of 7 pass first and the report blames AEA. Same "present but
    # unusable" class as the Store python3 stub, failing much later. Probe what actually breaks.
    & $c -c "import pytest, mne" 2>$null | Out-Null
    $okImport = ($LASTEXITCODE -eq 0)
    & $c -c "import scipy.linalg as L, numpy as N; L.svd(N.eye(2))" 2>$null | Out-Null
    if ($okImport -and $LASTEXITCODE -eq 0) { return $c }
  }
  return $first
}
$py = Select-Python
if (-not $py) {
  Write-Host "No working Python found on PATH (tried AEA_PYTHON, python, python3, py)."
  Write-Host "Install Python 3.10+ then: pip install mne numpy scipy pytest"
  exit 1
}

$missing = @()
foreach ($m in @("pytest", "mne", "numpy", "scipy")) {
  & $py -c "import $m" 2>$null | Out-Null
  if ($LASTEXITCODE -ne 0) { $missing += $m }
}
function Redact([string]$s) {
  if (-not $s) { return "" }
  # A home path appears in this report in more than one SHAPE, and matching only the literal one
  # leaked a real username: an embedded ENVIRONMENT.json carries it JSON-escaped
  # ("C:\\Users\\name"), and a Python repr does the same, while some tools emit forward slashes.
  # Redact every shape, then sweep the bare username as a backstop -- this file gets emailed.
  $homes = @($HOME, "C:\Users\$env:USERNAME") | Where-Object { $_ } | Select-Object -Unique
  foreach ($h in $homes) {
    foreach ($form in @($h, $h.Replace('\','\\'), $h.Replace('\','/'))) {
      $s = $s -replace [regex]::Escape($form), "~"
    }
  }
  if ($env:USERNAME) { $s = $s -replace [regex]::Escape($env:USERNAME), "<user>" }
  return $s
}

function Assert-NoLeak([string]$path) {
  # Warn if the report still contains the username.
  # (This comment is a # comment on purpose: a Python-style triple-quoted docstring is not a
  # comment in PowerShell at all, it is a string expression that lands in the output stream.)
  if (-not $env:USERNAME) { return }
  $hits = Select-String -Path $path -Pattern ([regex]::Escape($env:USERNAME)) -SimpleMatch
  if ($hits) {
    Write-Host ""
    Write-Host "WARNING: '$env:USERNAME' still appears in $path on line(s): $($hits.LineNumber -join ', ')"
    Write-Host "Redaction did not catch every form. Please remove those lines before sending,"
    Write-Host "and tell the maintainer which shape leaked -- that is itself a finding."
  }
}
function Add-Out([string]$s) { Add-Content -Path $Out -Value (Redact $s) -Encoding UTF8 }

Write-Host "AEA cold-start report -> $Out"
Write-Host "(this takes a couple of minutes; nothing is uploaded, it just writes a file)"

Set-Content -Path $Out -Value "# AEA cold-start report" -Encoding UTF8
Add-Out ""
Add-Out "Generated by ``tools/env/deploy_report.ps1``. Paths are redacted to ``~``."

# ---------------------------------------------------------------- machine
Add-Out "`n## Machine`n"
Add-Out '```'
Add-Out ("os          : Windows " + [System.Environment]::OSVersion.Version.ToString() + " " + $env:PROCESSOR_ARCHITECTURE)
Add-Out ("powershell  : " + $PSVersionTable.PSVersion.ToString())
Add-Out ("python      : " + (& $py -c "import sys; print(sys.version.split()[0], 'at', sys.executable)" 2>&1))
Add-Out ("  (chosen as : $py)")
if ($missing.Count -eq 0) { Add-Out "required    : pytest, mne, numpy, scipy all present" }
else { Add-Out ("required    : MISSING -> " + ($missing -join " ")) }
$commit = (& git rev-parse --short HEAD 2>$null)
if (-not $commit) {
  # A tarball has no .git. git archive substitutes the commit into ARCHIVE_VERSION so the report
  # can still identify itself -- otherwise there is no way to tell which package was run.
  $vf = Join-Path $root "tools\env\ARCHIVE_VERSION"
  if (Test-Path $vf) {
    $raw = (Get-Content $vf -First 1)
    if ($raw -match '^([0-9a-f]{7})') { $commit = $Matches[1] + " (from archive)" }
  }
}
Add-Out ("git commit  : " + $(if ($commit) { $commit } else { "unknown" }))
Add-Out '```'

# A blocked run must say WHAT is missing and HOW to fix it, not just fail.
if ($missing.Count -gt 0) {
  Add-Out "`n## BLOCKED - required packages missing`n"
  Add-Out ("This machine's Python is missing: **" + ($missing -join ", ") + "**")
  Add-Out "`nInstall them and re-run:`n"
  Add-Out '```powershell'
  Add-Out ("$py -m pip install " + ($missing -join " "))
  Add-Out "powershell -File tools/env/deploy_report.ps1   # or: pwsh tools/env/deploy_report.ps1"
  Add-Out '```'
  Add-Out "`nIf you have a conda env or venv with these already, activate it first, or point the script at it directly:`n"
  Add-Out '```powershell'
  Add-Out '$env:AEA_PYTHON = "C:\path\to\that\python.exe"; powershell -File tools/env/deploy_report.ps1'
  Add-Out '```'
  Add-Out "`n**This is not an AEA failure** - nothing was tested. Please send the report anyway if the instructions were unclear about the prerequisites; that is a finding too."
  Write-Host ""
  Write-Host ("BLOCKED: missing " + ($missing -join " "))
  Write-Host "Report written anyway: $root\$Out"
  exit 2
}

# The scratch directory is created only AFTER the BLOCKED early-exit above. Creating it earlier
# left an empty %TEMP%\aea_<guid> behind on every blocked run: the cleanup at the end of this
# script is unreachable from `exit 0`, and PowerShell has no equivalent of the `trap ... EXIT`
# that protects deploy_report.sh. A blocked run is the route a first-time tester is most likely
# to take, so that was the most-reachable litter in the script.
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("aea_" + [System.Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp -Force | Out-Null

# ---------------------------------------------------------------- 1. probe
Add-Out "`n## 1. Environment probe`n"
$envJson = Join-Path $tmp "ENVIRONMENT.json"
# Windows ships powershell.exe (5.1) and NOT pwsh (7) - pwsh is a separate install. Hardcoding
# pwsh made this script fail with CommandNotFoundException on a stock Windows box, and the report
# then blamed check_env.ps1, which was fine. Same lesson as the Store python3 stub: resolve the
# interpreter, do not assume it. $PSCommandPath's own host is the safest choice.
$psExe = if ($PSVersionTable.PSEdition -eq 'Core') { 'pwsh' } else { 'powershell' }
if (-not (Get-Command $psExe -ErrorAction SilentlyContinue)) {
  $psExe = @('pwsh','powershell') | Where-Object { Get-Command $_ -ErrorAction SilentlyContinue } | Select-Object -First 1
}
$probeLog = & $psExe -NoProfile -File (Join-Path $root "tools\env\check_env.ps1") $envJson 2>&1 | Out-String
$probeExit = $LASTEXITCODE
$probeOk = Test-Path $envJson
$jsonOk = $false
if ($probeOk) {
  try { Get-Content $envJson -Raw | ConvertFrom-Json | Out-Null; $jsonOk = $true } catch { $jsonOk = $false }
}
if ($probeExit -eq 0 -and $jsonOk) {
  Add-Out "**PASS**  -  wrote a valid ``ENVIRONMENT.json``."
} elseif ($probeExit -ne 0) {
  Add-Out "**FAIL**  -  the probe exited non-zero."
} elseif ($probeOk) {
  Add-Out "**FAIL**  -  the probe ran but its output is not valid JSON. Every skill reads this file first."
} else {
  Add-Out "**FAIL**  -  the probe produced no output file."
}
Add-Out "`n``````"
Add-Out $probeLog
Add-Out "``````"
if ($probeOk) {
  Add-Out "`n<details><summary>full ENVIRONMENT.json</summary>`n"
  Add-Out '```json'
  Add-Out (Get-Content $envJson -Raw)
  Add-Out '```'
  Add-Out "`n</details>"
}

# ---------------------------------------------------------------- 2. backend resolution
Add-Out "`n## 2. Backend resolution`n"
$brMd = Join-Path $tmp "BACKEND_RESOLUTION.md"
$resolveOk = $false
$resolveLog = & $py "tools\env\resolve_backend.py" --capability erp.preprocess_average `
  --env $envJson --out $brMd 2>&1 | Out-String
if ($LASTEXITCODE -eq 0) {
  $resolveOk = $true
  Add-Out "**PASS**  -  resolved a backend and wrote the record."
} elseif ($resolveLog -match '(?m)^Traceback') {
  # A crash and a refusal both exit non-zero. Labelling a crash "a legitimate outcome" is the same
  # silent-degradation failure this project exists to prevent, one layer up in the report itself.
  # A refusal prints "ERROR: ..."; a crash prints a traceback.
  Add-Out "**CRASH**  -  the resolver raised an unhandled exception. This is a defect, NOT the designed refusal. The traceback below is the finding."
} else {
  Add-Out "**Resolver declined.** That is a legitimate outcome (it refuses rather than degrading silently); the message below says what is missing."
}
Add-Out "`n``````"
Add-Out $resolveLog
Add-Out "``````"

# ---------------------------------------------------------------- 3. tests
Add-Out "`n## 3. Test suite`n"
$pytestLog = & $py -m pytest "tools/tests/" -q -rs 2>&1 | Out-String
$rc = $LASTEXITCODE
$summary = ($pytestLog -split "`n" | Where-Object { $_ -match "[0-9]+ (passed|failed|error)" } | Select-Object -Last 1)
# pytest can die before printing any summary (missing module, collection crash). A blank failure
# section is the one outcome that makes this whole exercise worthless.
if (-not $summary) { $summary = "no pytest summary line - the run died before reporting (see below)" }
if ($rc -eq 0) { Add-Out "**PASS**  -  ``$summary``" } else { Add-Out "**FAIL** (exit $rc)  -  ``$summary``" }
Add-Out "`nSkips are expected when large datasets are absent; they are listed below.`n"
Add-Out '```'
Add-Out (($pytestLog -split "`n" | Where-Object { $_ -match "SKIPPED|FAILED|ERROR|passed|failed" } | Select-Object -First 40) -join "`n")
Add-Out '```'
if ($rc -ne 0) {
  Add-Out "`n<details><summary>failure detail</summary>`n"
  Add-Out '```'
  $detail = ($pytestLog -split "`n" | Where-Object { $_ -match "^(FAILED|ERROR)|^E " } | Select-Object -First 60) -join "`n"
  if (-not $detail) { $detail = ($pytestLog -split "`n" | Select-Object -Last 60) -join "`n" }
  Add-Out $detail
  Add-Out '```'
  Add-Out "`n</details>"
}

# ---------------------------------------------------------------- verdict
Add-Out "`n## Verdict`n"
$overallOk = $probeExit -eq 0 -and $jsonOk -and $resolveOk -and $rc -eq 0
if ($overallOk) {
  Add-Out "**PASS**  -  environment probe, backend resolution, and test suite completed."
} else {
  Add-Out "**NOT READY**  -  one or more stages failed or declined; see sections 1-3."
}
Add-Out "`nPlease send back this file (``$Out``) and, if anything failed, say what you expected to happen. A failure here is the useful result: it is a defect on a machine that is not the developer's, which is exactly what this report exists to find."

Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
# Defined-but-never-called is how a guarantee becomes vapour: the first real Windows run reported
# "no WARNING line", which was consistent with both "redaction worked" and "the check never ran".
# It was the latter. Call it, right where the tester is told to hand the file over.
Assert-NoLeak $Out
Write-Host ""
Write-Host "Done. Send back: $root\$Out"
if ($overallOk) {
  Write-Host "Result: PASS ($summary)"
  exit 0
}
Write-Host "Result: NOT READY (see report)"
exit 1
