"""Harmonized MNE-BIDS-Pipeline config: ERP CORE N170, matched to AEA's n170-faces recipe.

Every choice pinned to tools/validation/validate_n170_erpcore_group.py so a residual per-subject
difference reflects IMPLEMENTATION, not parameters:

  filter 0.1-40 Hz | resample 256 Hz | average reference | 30 EEG (EOG excluded)
  epoch -0.2..0.5 s | baseline (-0.2, 0) | NO peak-to-peak rejection | NO ICA/SSP
  conditions face vs car | contrast face - car (occipito-temporal N170)

reject=None so both pipelines average the identical trial set (zero epoch-selection divergence).
Env vars: BENCH_BIDS_ROOT, BENCH_DERIV_ROOT, BENCH_SUBJECTS.

  BENCH_SUBJECTS=all mne_bids_pipeline --config tools/benchmark/config_n170_bidspipe.py
"""
import os
from pathlib import Path

bids_root = os.environ.get("BENCH_BIDS_ROOT", str(Path.home() / "mne_data" / "erpcore_n170_bench_bids"))
deriv_root = os.environ.get("BENCH_DERIV_ROOT", str(Path.home() / "mne_data" / "erpcore_n170_bench_deriv"))

study_name = "ERPCORE_N170_harmonized"
task = "N170"
ch_types = ["eeg"]

_subs = os.environ.get("BENCH_SUBJECTS", "all")
subjects = "all" if _subs == "all" else _subs.split(",")

eeg_reference = "average"
l_freq = 0.1
h_freq = 40.0
raw_resample_sfreq = 256.0
spatial_filter = None

epochs_tmin = -0.2
epochs_tmax = 0.5
baseline = (-0.2, 0.0)
conditions = ["face", "car"]
contrasts = [("face", "car")]             # face - car (N170 selectivity)
reject = None

run_source_estimation = False
on_error = "continue"
n_jobs = 4
