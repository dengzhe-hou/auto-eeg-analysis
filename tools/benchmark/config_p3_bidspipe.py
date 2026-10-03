"""Harmonized MNE-BIDS-Pipeline config: ERP CORE P3, matched to AEA's p300-oddball recipe.

Every analysis choice is pinned to AEA's tools/validation/validate_p3_group.py so a per-subject
numeric difference reflects pipeline IMPLEMENTATION, not parameter choices:

  filter 0.1-30 Hz | resample 256 Hz | average reference | 30 EEG (EOG excluded)
  epoch -0.2..0.8 s | baseline (-0.2, 0) | NO peak-to-peak rejection | NO ICA/SSP
  conditions target vs standard (visual oddball) | contrast target - standard

No rejection: the active P3 task over a 1 s epoch without ICA would lose most trials to
blinks/EMG at 100 uV; averaging all epochs (both pipelines identically) keeps N and removes
epoch-selection divergence — the cleanest cross-tool numeric comparison.

Driven by env vars: BENCH_BIDS_ROOT, BENCH_DERIV_ROOT, BENCH_SUBJECTS (comma list or "all")

  BENCH_SUBJECTS=all mne_bids_pipeline --config tools/benchmark/config_p3_bidspipe.py
"""
import os
from pathlib import Path

bids_root = os.environ.get("BENCH_BIDS_ROOT", str(Path.home() / "mne_data" / "erpcore_p3_bench_bids"))
deriv_root = os.environ.get("BENCH_DERIV_ROOT", str(Path.home() / "mne_data" / "erpcore_p3_bench_deriv"))

study_name = "ERPCORE_P3_harmonized"
task = "P3"
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
conditions = ["standard", "target"]
contrasts = [("target", "standard")]      # target - standard (P3b)
reject = None                              # no peak-to-peak rejection (see header)

run_source_estimation = False
on_error = "continue"
n_jobs = 4
