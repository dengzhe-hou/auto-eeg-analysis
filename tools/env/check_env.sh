#!/usr/bin/env bash
# AEA environment probe — macOS / Linux.
# Writes ENVIRONMENT.json describing which capabilities are available.
# Skills read this file to know what they CAN do; never run a capability without checking.
#
# MNE-Python is the DEFAULT and reference backend: every committed certified value was produced
# by it. EEGLAB and FieldTrip are supported as *selectable alternatives* — they were validated
# against the reference on all five certified ERP CORE components (tools/benchmark/
# CROSS_TOOLBOX_EVAL.md: 10/10 runs reproduce the group conclusion), so this probe reports them.
#
# Schema 2 deliberately did not probe them, on the grounds that AEA was MNE-only. That decision
# predated any evidence the other toolboxes agreed; it now exists, so schema 3 probes them.
#
# Availability alone is NOT sufficient to use one: cross-toolbox agreement is a property of how
# completely the specification is pinned, not of the toolbox. See tools/env/backends.json and
# resolve_backend.py — never select a backend without emitting its `pin` list.
#
# (Reading EEGLAB .set files is handled inside MNE via `mne.io.read_raw_eeglab`; that needs no
# MATLAB and is not a "backend".)

set -u

OUT="${1:-ENVIRONMENT.json}"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

probe_python() {
  if command -v python3 >/dev/null 2>&1; then
    PY=$(python3 -c 'import sys; print(sys.version.split()[0])' 2>/dev/null || echo "unknown")
    PY_PATH=$(command -v python3)
    echo "{\"available\": true, \"version\": \"$PY\", \"path\": \"$PY_PATH\"}"
  else
    echo '{"available": false}'
  fi
}

probe_pkg() {
  # $1 = import name, $2 = pip name (for hint)
  #
  # NOTE: this used to pipe into awk with a `|| echo` fallback. That fallback never fired for a
  # missing package, because the exit status of `python3 ... | awk ...` is awk's, and awk exits 0
  # on empty input. The field was emitted empty and the whole ENVIRONMENT.json became invalid
  # JSON — on any machine lacking an optional package, for every skill that is required to read
  # it first. Capture, then branch.
  local ver
  ver=$(python3 -c "import $1; print(getattr($1, '__version__', 'unknown'))" 2>/dev/null)
  if [ -n "$ver" ]; then
    echo "{\"available\": true, \"version\": \"$ver\", \"pip\": \"$2\"}"
  else
    echo "{\"available\": false, \"pip\": \"$2\"}"
  fi
}

probe_freesurfer() {
  if [ -n "${FREESURFER_HOME:-}" ] && [ -f "$FREESURFER_HOME/SetUpFreeSurfer.sh" ]; then
    VER=$(cat "$FREESURFER_HOME/build-stamp.txt" 2>/dev/null | head -1 || echo "unknown")
    echo "{\"available\": true, \"path\": \"$FREESURFER_HOME\", \"version\": \"$VER\"}"
  else
    echo '{"available": false, "hint": "FREESURFER_HOME not set; eeg-source on individual MRI unavailable. Template (fsaverage) path still works via MNE."}'
  fi
}

probe_matlab_engine() {
  # Either MATLAB or GNU Octave can drive the EEGLAB/FieldTrip backends. AEA's cross-toolbox
  # validation was done under Octave; MATLAB is assumed equivalent but was not verified.
  if command -v matlab >/dev/null 2>&1; then
    VER=$(matlab -batch "disp(version)" 2>/dev/null | tr -d '\r' | tail -1 || echo "unknown")
    echo "{\"available\": true, \"engine\": \"matlab\", \"version\": \"$VER\", \"path\": \"$(command -v matlab)\"}"
  elif [ -n "${OCTAVE_HOME:-}" ] && [ -x "$OCTAVE_HOME/bin/octave-cli" ]; then
    VER=$("$OCTAVE_HOME/bin/octave-cli" --no-gui --quiet --eval "disp(version)" 2>/dev/null | tail -1 || echo "unknown")
    echo "{\"available\": true, \"engine\": \"octave\", \"version\": \"$VER\", \"path\": \"$OCTAVE_HOME/bin/octave-cli\"}"
  elif command -v octave-cli >/dev/null 2>&1; then
    VER=$(octave-cli --no-gui --quiet --eval "disp(version)" 2>/dev/null | tail -1 || echo "unknown")
    echo "{\"available\": true, \"engine\": \"octave\", \"version\": \"$VER\", \"path\": \"$(command -v octave-cli)\", \"hint\": \"a conda Octave usually needs OCTAVE_HOME exported, or core functions like getfield are undefined\"}"
  else
    echo '{"available": false, "hint": "no matlab on PATH and no Octave (set OCTAVE_HOME or install octave-cli); EEGLAB/FieldTrip backends unavailable"}'
  fi
}

probe_eeglab() {
  if [ -n "${EEGLAB_PATH:-}" ] && [ -f "$EEGLAB_PATH/eeglab.m" ]; then
    VER=$(grep -m1 -oE "v?[0-9]+\.[0-9]+(\.[0-9]+)?" "$EEGLAB_PATH/eeglab.m" 2>/dev/null | head -1 || echo "unknown")
    echo "{\"available\": true, \"path\": \"$EEGLAB_PATH\", \"version\": \"$VER\", \"note\": \"'eeglab nogui' fails under Octave; add functions/ and plugins/ to the path instead\"}"
  else
    echo '{"available": false, "hint": "set EEGLAB_PATH to an install dir containing eeglab.m"}'
  fi
}

probe_fieldtrip() {
  if [ -n "${FIELDTRIP_PATH:-}" ] && [ -f "$FIELDTRIP_PATH/ft_defaults.m" ]; then
    VER=$(basename "$FIELDTRIP_PATH" | grep -oE "[0-9]{8}" || echo "unknown")
    echo "{\"available\": true, \"path\": \"$FIELDTRIP_PATH\", \"version\": \"$VER\"}"
  else
    echo '{"available": false, "hint": "set FIELDTRIP_PATH to an install dir containing ft_defaults.m"}'
  fi
}

probe_gpu() {
  if command -v nvidia-smi >/dev/null 2>&1; then
    NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo "unknown")
    echo "{\"available\": true, \"vendor\": \"nvidia\", \"name\": \"$NAME\"}"
  elif [[ "$(uname)" == "Darwin" ]] && system_profiler SPDisplaysDataType 2>/dev/null | grep -qi "Apple M"; then
    NAME=$(system_profiler SPDisplaysDataType 2>/dev/null | awk -F': ' '/Chipset Model/{print $2; exit}')
    echo "{\"available\": true, \"vendor\": \"apple-mps\", \"name\": \"$NAME\"}"
  else
    echo '{"available": false}'
  fi
}

OS_NAME="$(uname -s)"
OS_VER="$(uname -r)"

PYTHON=$(probe_python)
MNE=$(probe_pkg mne mne)
MNE_BIDS=$(probe_pkg mne_bids mne-bids)
MNE_ICALABEL=$(probe_pkg mne_icalabel mne-icalabel)
AUTOREJECT=$(probe_pkg autoreject autoreject)
PYCROSTATES=$(probe_pkg pycrostates pycrostates)
MNE_CONNECTIVITY=$(probe_pkg mne_connectivity mne-connectivity)
PYPREP=$(probe_pkg pyprep pyprep)
NUMPY=$(probe_pkg numpy numpy)
SCIPY=$(probe_pkg scipy scipy)
SKLEARN=$(probe_pkg sklearn scikit-learn)
MATPLOTLIB=$(probe_pkg matplotlib matplotlib)
# Optional skill backends (tools/env/requirements-optional.txt) — degrade explicitly if absent.
SPECPARAM=$(probe_pkg specparam specparam)
ANTROPY=$(probe_pkg antropy antropy)
STATSMODELS=$(probe_pkg statsmodels statsmodels)
TENSORPAC=$(probe_pkg tensorpac tensorpac)
FREESURFER=$(probe_freesurfer)
MATLAB_ENGINE=$(probe_matlab_engine)
EEGLAB=$(probe_eeglab)
FIELDTRIP=$(probe_fieldtrip)
GPU=$(probe_gpu)

cat > "$OUT" <<EOF
{
  "schema_version": "3",
  "backend": {
    "default": "mne",
    "reference": "mne",
    "note": "MNE-Python produced every committed certified value. EEGLAB and FieldTrip are selectable alternatives with MEASURED agreement (https://github.com/dengzhe-hou/auto-eeg-analysis/blob/995f53d42cc74205b164e8711d4b289b8c2ad3a1/tools/benchmark/CROSS_TOOLBOX_EVAL.md); resolve with tools/env/resolve_backend.py, which also emits the numerical conventions that must be pinned."
  },
  "probed_at": "$TS",
  "os": {
    "name": "$OS_NAME",
    "release": "$OS_VER"
  },
  "python": $PYTHON,
  "python_packages": {
    "mne": $MNE,
    "mne_bids": $MNE_BIDS,
    "mne_icalabel": $MNE_ICALABEL,
    "autoreject": $AUTOREJECT,
    "pycrostates": $PYCROSTATES,
    "mne_connectivity": $MNE_CONNECTIVITY,
    "pyprep": $PYPREP,
    "numpy": $NUMPY,
    "scipy": $SCIPY,
    "scikit_learn": $SKLEARN,
    "matplotlib": $MATPLOTLIB
  },
  "optional_packages": {
    "specparam": $SPECPARAM,
    "antropy": $ANTROPY,
    "statsmodels": $STATSMODELS,
    "tensorpac": $TENSORPAC
  },
  "freesurfer": $FREESURFER,
  "matlab_engine": $MATLAB_ENGINE,
  "eeglab": $EEGLAB,
  "fieldtrip": $FIELDTRIP,
  "gpu": $GPU,
  "capabilities": {
    "preprocess.mne": "requires python_packages.mne",
    "preprocess.ransac": "requires python_packages.pyprep",
    "ica.mne_icalabel": "requires python_packages.mne_icalabel",
    "stats.mne_cluster": "requires python_packages.mne",
    "stats.mixed_anova": "requires optional_packages.statsmodels",
    "microstate.pycrostates": "requires python_packages.pycrostates",
    "connectivity.mne": "requires python_packages.mne_connectivity",
    "spectral.specparam": "requires optional_packages.specparam",
    "complexity.antropy": "requires optional_packages.antropy",
    "connectivity.pac": "requires optional_packages.tensorpac",
    "source.mne_template": "requires python_packages.mne (fsaverage shipped)",
    "source.mne_individual": "requires freesurfer for individual MRI",
    "erp.preprocess_average.mne": "requires python_packages.mne",
    "erp.preprocess_average.eeglab": "requires eeglab + matlab_engine",
    "erp.preprocess_average.fieldtrip": "requires fieldtrip + matlab_engine",
    "ica.label.eeglab": "requires eeglab + matlab_engine + the ICLabel plugin",
    "stats.cluster_permutation.fieldtrip": "requires fieldtrip + matlab_engine"
  }
}
EOF

echo "Wrote $OUT"
echo "Summary:"
python3 -c "import json; d=json.load(open('$OUT')); \
  print(f\"  Python: {d['python'].get('version','-')}\"); \
  print(f\"  MNE: {d['python_packages']['mne'].get('version','MISSING')}\"); \
  print(f\"  pycrostates: {d['python_packages']['pycrostates'].get('version','MISSING')}\"); \
  print(f\"  optional: specparam={d['optional_packages']['specparam'].get('version','no')} antropy={d['optional_packages']['antropy'].get('version','no')} statsmodels={d['optional_packages']['statsmodels'].get('version','no')}\"); \
  print(f\"  FreeSurfer: {'yes' if d['freesurfer']['available'] else 'no'}\"); \
  print(f\"  GPU: {d['gpu'].get('name','none')}\")" 2>/dev/null || cat "$OUT"
