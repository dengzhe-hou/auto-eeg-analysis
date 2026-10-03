"""Harmonized MNE-BIDS-Pipeline config: ERP CORE N400, matched to AEA's n400-semantic recipe.

  filter 0.1-30 Hz | resample 256 Hz | average reference | 30 EEG (EOG excluded)
  epoch -0.2..0.8 s | baseline (-0.2, 0) | NO reject | NO ICA/SSP
  conditions related vs unrelated (target words) | contrast unrelated - related (N400)

reject=None so both pipelines average the identical trial set.
Env vars: BENCH_BIDS_ROOT, BENCH_DERIV_ROOT, BENCH_SUBJECTS.

  BENCH_SUBJECTS=all mne_bids_pipeline --config tools/benchmark/config_n400_bidspipe.py
"""
import os
from pathlib import Path

bids_root = os.environ.get("BENCH_BIDS_ROOT", str(Path.home() / "mne_data" / "erpcore_n400_bench_bids"))
deriv_root = os.environ.get("BENCH_DERIV_ROOT", str(Path.home() / "mne_data" / "erpcore_n400_bench_deriv"))

study_name = "ERPCORE_N400_harmonized"
task = "N400"
ch_types = ["eeg"]

_subs = os.environ.get("BENCH_SUBJECTS", "all")
subjects = "all" if _subs == "all" else _subs.split(",")

eeg_reference = "average"
l_freq = 0.1
h_freq = 30.0
raw_resample_sfreq = 256.0
spatial_filter = None

epochs_tmin = -0.2
epochs_tmax = 0.8
baseline = (-0.2, 0.0)
conditions = ["related", "unrelated"]
contrasts = [("unrelated", "related")]     # unrelated - related = N400
reject = None

run_source_estimation = False
on_error = "continue"
n_jobs = 4
