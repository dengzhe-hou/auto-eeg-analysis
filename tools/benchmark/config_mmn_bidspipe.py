"""Harmonized MNE-BIDS-Pipeline config: ERP CORE MMN, matched to AEA's mmn-oddball recipe.

Every analysis choice is pinned to AEA's `tools/validation/validate_mmn_group.py` so a
per-subject numeric difference reflects pipeline IMPLEMENTATION, not parameter choices:

  filter 0.1-30 Hz | resample 256 Hz | average reference | 30 EEG (EOG excluded)
  epoch -0.2..0.5 s | baseline (-0.2, 0) | peak-to-peak reject 100 uV | NO ICA/SSP
  conditions standard(80) vs deviant(70) | contrast deviant - standard | first-stream(180) excluded

Driven by env vars so the same config serves any subject subset:
  BENCH_BIDS_ROOT, BENCH_DERIV_ROOT, BENCH_SUBJECTS (comma list or "all")

Run:
  BENCH_SUBJECTS=all mne_bids_pipeline tools/benchmark/config_mmn_bidspipe.py
"""
import os
from pathlib import Path

bids_root = os.environ.get("BENCH_BIDS_ROOT", str(Path.home() / "mne_data" / "erpcore_mmn_bench_bids"))
deriv_root = os.environ.get("BENCH_DERIV_ROOT", str(Path.home() / "mne_data" / "erpcore_mmn_bench_deriv"))

study_name = "ERPCORE_MMN_harmonized"
task = "MMN"
ch_types = ["eeg"]

_subs = os.environ.get("BENCH_SUBJECTS", "all")
subjects = "all" if _subs == "all" else _subs.split(",")

# --- preprocessing (match AEA) ---
eeg_reference = "average"
l_freq = 0.1
h_freq = 30.0
raw_resample_sfreq = 256.0
spatial_filter = None            # no ICA, no SSP — AEA runs MMN without ICA on clean passive data

# --- epoching (match AEA) ---
epochs_tmin = -0.2
epochs_tmax = 0.5
baseline = (-0.2, 0.0)
conditions = ["standard", "deviant"]
contrasts = [("deviant", "standard")]   # deviant - standard difference wave
reject = {"eeg": 100e-6}                # peak-to-peak, same as AEA

# --- scope / robustness ---
run_source_estimation = False
on_error = "continue"
n_jobs = 4
