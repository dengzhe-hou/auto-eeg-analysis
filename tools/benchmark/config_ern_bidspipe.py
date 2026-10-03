"""Harmonized MNE-BIDS-Pipeline config: ERP CORE ERN (RESPONSE-locked), matched to AEA.

Pinned to tools/validation/validate_ern_erpcore_group.py:

  filter 0.1-30 Hz | resample 256 Hz | average reference | 30 EEG (EOG excluded)
  RESPONSE-locked epoch -0.4..0.6 s | pre-response baseline (-0.4, -0.2) | NO reject | NO ICA/SSP
  conditions correct vs error | contrast error - correct (ERN, 0-100 ms post-response)

Epochs lock to the response events (relabeled correct/error); stimulus events are ignored.
reject=None so both pipelines average the identical trial set.
Env vars: BENCH_BIDS_ROOT, BENCH_DERIV_ROOT, BENCH_SUBJECTS.

  BENCH_SUBJECTS=all mne_bids_pipeline --config tools/benchmark/config_ern_bidspipe.py
"""
import os
from pathlib import Path

bids_root = os.environ.get("BENCH_BIDS_ROOT", str(Path.home() / "mne_data" / "erpcore_ern_bench_bids"))
deriv_root = os.environ.get("BENCH_DERIV_ROOT", str(Path.home() / "mne_data" / "erpcore_ern_bench_deriv"))

study_name = "ERPCORE_ERN_harmonized"
task = "ERN"
ch_types = ["eeg"]

_subs = os.environ.get("BENCH_SUBJECTS", "all")
subjects = "all" if _subs == "all" else _subs.split(",")

eeg_reference = "average"
l_freq = 0.1
h_freq = 30.0
raw_resample_sfreq = 256.0
spatial_filter = None

# response-locked
epochs_tmin = -0.4
epochs_tmax = 0.6
baseline = (-0.4, -0.2)
conditions = ["correct", "error"]
contrasts = [("error", "correct")]        # error - correct = ERN
reject = None

run_source_estimation = False
on_error = "continue"
n_jobs = 4
