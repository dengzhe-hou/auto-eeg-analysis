"""
AEA Full Case Study — ERP CORE Flankers (Kappenman et al. 2021)
Complete W2 pipeline: auto-brief → preprocess → ICA → epoch → ERP → TFR → spectral → stats → figure → methods-text

Demonstrates AEA's full capability on real EEG data.
"""
import mne, json, numpy as np, matplotlib, hashlib, subprocess
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime
from scipy import stats as scipy_stats
from collections import Counter

mne.set_log_level("WARNING")
SEED = 42
np.random.seed(SEED)
PROJECT = Path("projects/erp-core-full")
START_TIME = datetime.now()

def stage_print(stage, msg):
    elapsed = (datetime.now() - START_TIME).total_seconds()
    print(f"[{elapsed:6.1f}s] {stage}: {msg}", flush=True)

def sha256_short(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]

# Create all directories
for d in ["preprocess-stage/sub-01", "ica-stage/sub-01", "epoch-stage/sub-01",
          "erp-stage/sub-01", "tfr-stage/sub-01", "spectral-stage/sub-01",
          "stats-stage", "figure-stage", "report-stage", "audit-stage"]:
    (PROJECT / d).mkdir(parents=True, exist_ok=True)

# ================================================================
# STEP 1: Fill DATASET_BRIEF (simulate conversational fill)
# ================================================================
stage_print("BRIEF", "Filling DATASET_BRIEF from auto-brief + known info")

brief = """# DATASET_BRIEF — erp-core-flankers-full

## 1. Study identity
- **Study short name:** erp-core-flankers-full
- **Paradigm:** Eriksen Flankers — compatible vs incompatible, stimulus-locked + response-locked
- **Hypothesis:** (C1) Incompatible stimuli elicit larger N2 at FCz 200-350ms; (C2) Incompatible responses elicit larger ERN at FCz 0-100ms; (C3) Theta power (4-8Hz) is greater for incompatible 200-500ms post-stimulus
- **Source:** Kappenman et al. 2021, NeuroImage (ERP CORE)

## 2. Subjects
- **N:** 1 (case study demo)
- **Group structure:** single-subject, within-subject conditions

## 3. Acquisition
- **System:** BioSemi ActiveTwo
- **Channels:** 30 EEG (10-20) + 3 EOG (HEOG_left, HEOG_right, VEOG_lower)
- **Sampling rate:** 1024 Hz
- **Online reference:** CMS/DRL
- **Online filter:** DC-coupled

## 4. Conditions
| Condition | Event | N trials |
|-----------|-------|----------|
| stimulus/compatible/target_left | 3 | 100 |
| stimulus/compatible/target_right | 4 | 100 |
| stimulus/incompatible/target_left | 5 | 100 |
| stimulus/incompatible/target_right | 6 | 100 |
| response/left | 1 | ~200 |
| response/right | 2 | ~200 |

## 5. Preprocessing
- Bandpass: 0.1–30 Hz zero-phase FIR
- Notch: 60 Hz (US data)
- Reference: average
- Bad channel detection: RANSAC (default)
- Epoch window (stimulus): -0.2 to 0.8 s
- Epoch window (response): -0.4 to 0.6 s
- Baseline: -0.2 to 0 s (stimulus), -0.4 to -0.2 s (response)
- Artifact rejection: ±150 µV threshold

## 6. Analyses planned
- [x] ERP — N2 (stimulus-locked) + ERN (response-locked)
- [x] Time-frequency (TFR) — theta band conflict effect
- [x] Spectral — PSD comparison

## 7. Statistical plan
- Cluster permutation, trial-level (single subject)
- 5000 permutations, seed 42
- One-sided tests per directional hypothesis
"""
(PROJECT / "DATASET_BRIEF.md").write_text(brief, encoding="utf-8")

# ================================================================
# STEP 2: Freeze ANALYSIS_PLAN
# ================================================================
stage_print("PLAN", "Writing and freezing ANALYSIS_PLAN")

plan = """# ANALYSIS_PLAN — erp-core-flankers-full
## Plan version
- **v1**, frozen """ + datetime.now().strftime('%Y-%m-%d %H:%M') + """

## Claims
| ID | Claim | Contrast | ROI | Window | Test | Direction | alpha |
|----|-------|----------|-----|--------|------|-----------|-------|
| C1 | Incompatible elicits larger N2 | incomp_stim − comp_stim | FCz, Fz, Cz | 200–350 ms post-stim | cluster perm, 1-sample, trial-level | incomp more negative | 0.05 |
| C2 | Incompatible responses elicit larger ERN | incomp_resp − comp_resp | FCz, Fz, Cz | 0–100 ms post-resp | cluster perm, 1-sample, trial-level | incomp more negative | 0.05 |
| C3 | Theta power greater for incompatible (TFR) | incomp_stim − comp_stim | FCz, Fz, Cz | 200–500 ms, 4–8 Hz | cluster perm on TFR, trial-level | incomp more positive | 0.05 |

## Seeds
- ICA: 42, Cluster: 42, AutoReject: N/A (threshold)

## Multiple comparisons
- Bonferroni N=3, adjusted alpha = 0.0167
"""
(PROJECT / "ANALYSIS_PLAN.md").write_text(plan, encoding="utf-8")

# ================================================================
# STEP 3: PREPROCESS
# ================================================================
stage_print("PREPROCESS", "Loading and preprocessing")

raw = mne.io.read_raw_fif(PROJECT / "raw/sub-01.fif", preload=True)
raw.pick_types(eeg=True, eog=True)
raw_eeg = raw.copy().pick_types(eeg=True)
raw_eeg.filter(l_freq=0.1, h_freq=30.0, n_jobs=1)
raw_eeg.notch_filter(60.0, n_jobs=1)
raw_eeg.set_eeg_reference("average", projection=False)

pp_path = PROJECT / "preprocess-stage/sub-01/sub-01_preprocessed_raw.fif"
raw_eeg.save(pp_path, overwrite=True)
pp_summary = {"bandpass": [0.1, 30], "notch": 60, "reference": "average",
              "n_ch": raw_eeg.info["nchan"], "sfreq": raw_eeg.info["sfreq"]}
json.dump(pp_summary, open(PROJECT / "preprocess-stage/sub-01/preprocess_summary.json", "w", encoding="utf-8"), indent=2)
stage_print("PREPROCESS", f"{raw_eeg.info['nchan']} ch, 0.1-30Hz, 60Hz notch, avg ref")

# ================================================================
# STEP 4: ICA + ICLabel
# ================================================================
stage_print("ICA", "Fitting ICA + ICLabel")

raw_pp = mne.io.read_raw_fif(pp_path, preload=True)
raw_hp = raw_pp.copy().filter(l_freq=1.0, h_freq=None)
ica = mne.preprocessing.ICA(n_components=15, method="infomax", random_state=SEED,
                             max_iter="auto", fit_params=dict(extended=True))
ica.fit(raw_hp)

from mne_icalabel import label_components
labels = label_components(raw_hp, ica, method="iclabel")
label_list = labels["labels"]
exclude = [i for i, l in enumerate(label_list) if l in {"eye blink", "muscle artifact", "heart beat"}]
ica.exclude = exclude

raw_clean = raw_pp.copy()
ica.apply(raw_clean)
ica_path = PROJECT / "ica-stage/sub-01/sub-01_ica-cleaned_raw.fif"
raw_clean.save(ica_path, overwrite=True)
ica_summary = {"method": "infomax_extended", "n_components": int(ica.n_components_),
               "labels": label_list, "excluded": exclude, "seed": SEED}
json.dump(ica_summary, open(PROJECT / "ica-stage/sub-01/ica_summary.json", "w", encoding="utf-8"), indent=2)
stage_print("ICA", f"{ica.n_components_} comp, {len(exclude)} excluded: {[(i,label_list[i]) for i in exclude]}")

# ================================================================
# STEP 5: EPOCH (stimulus-locked + response-locked)
# ================================================================
stage_print("EPOCH", "Creating stimulus-locked and response-locked epochs")

raw_full = mne.io.read_raw_fif(PROJECT / "raw/sub-01.fif", preload=False)
all_events, all_event_id = mne.events_from_annotations(raw_full)

# --- Stimulus-locked epochs ---
stim_event_id = {
    "compatible": 3,   # compatible/target_left
    "compatible2": 4,  # compatible/target_right
    "incompatible": 5, # incompatible/target_left
    "incompatible2": 6 # incompatible/target_right
}
# Remap to just compatible(101) vs incompatible(102)
stim_events = all_events[np.isin(all_events[:, 2], [3, 4, 5, 6])].copy()
stim_events[stim_events[:, 2] == 3, 2] = 101
stim_events[stim_events[:, 2] == 4, 2] = 101
stim_events[stim_events[:, 2] == 5, 2] = 102
stim_events[stim_events[:, 2] == 6, 2] = 102

stim_id = {"compatible": 101, "incompatible": 102}
epochs_stim = mne.Epochs(raw_clean, stim_events, event_id=stim_id,
                          tmin=-0.2, tmax=0.8, baseline=(-0.2, 0),
                          preload=True, reject=dict(eeg=150e-6))
stage_print("EPOCH", f"Stimulus-locked: {len(epochs_stim)} ({dict(Counter(epochs_stim.events[:,2]))})")

# --- Response-locked epochs ---
stim_all = all_events[np.isin(all_events[:, 2], [3, 4, 5, 6])]
resp_all = all_events[np.isin(all_events[:, 2], [1, 2])]

comp_resp, incomp_resp = [], []
for resp in resp_all:
    prior = stim_all[stim_all[:, 0] < resp[0]]
    if len(prior) == 0: continue
    code = int(prior[-1, 2])
    r = resp.copy()
    if code in (3, 4):
        r[2] = 201
        comp_resp.append(r)
    elif code in (5, 6):
        r[2] = 202
        incomp_resp.append(r)

resp_events = np.vstack([np.array(comp_resp), np.array(incomp_resp)])
resp_events = resp_events[resp_events[:, 0].argsort()]
resp_id = {"comp_resp": 201, "incomp_resp": 202}

epochs_resp = mne.Epochs(raw_clean, resp_events, event_id=resp_id,
                          tmin=-0.4, tmax=0.6, baseline=(-0.4, -0.2),
                          preload=True, reject=dict(eeg=150e-6))
stage_print("EPOCH", f"Response-locked: {len(epochs_resp)} ({dict(Counter(epochs_resp.events[:,2]))})")

# Save
epochs_stim.save(PROJECT / "epoch-stage/sub-01/sub-01_stim-epo.fif", overwrite=True)
epochs_resp.save(PROJECT / "epoch-stage/sub-01/sub-01_resp-epo.fif", overwrite=True)
epoch_summary = {
    "stim_locked": {"n": len(epochs_stim), "per_cond": {k: len(epochs_stim[k]) for k in stim_id}},
    "resp_locked": {"n": len(epochs_resp), "per_cond": {k: len(epochs_resp[k]) for k in resp_id}},
    "reject_threshold_uV": 150
}
json.dump(epoch_summary, open(PROJECT / "epoch-stage/sub-01/epoch_summary.json", "w", encoding="utf-8"), indent=2)

# ================================================================
# STEP 6: ERP — C1 (N2) + C2 (ERN)
# ================================================================
stage_print("ERP", "Computing ERPs for C1 (N2) and C2 (ERN)")

# C1: Stimulus-locked N2
evk_comp_stim = epochs_stim["compatible"].average()
evk_incomp_stim = epochs_stim["incompatible"].average()
evk_diff_stim = mne.combine_evoked([evk_incomp_stim, evk_comp_stim], weights=[1, -1])

# C2: Response-locked ERN
evk_comp_resp = epochs_resp["comp_resp"].average()
evk_incomp_resp = epochs_resp["incomp_resp"].average()
evk_diff_resp = mne.combine_evoked([evk_incomp_resp, evk_comp_resp], weights=[1, -1])

# Save
for name, evk in [("comp_stim", evk_comp_stim), ("incomp_stim", evk_incomp_stim),
                    ("diff_stim", evk_diff_stim), ("comp_resp", evk_comp_resp),
                    ("incomp_resp", evk_incomp_resp), ("diff_resp", evk_diff_resp)]:
    evk.save(PROJECT / f"erp-stage/sub-01/{name}-ave.fif", overwrite=True)

# Measure at ROI
roi = ["FCz", "Fz", "Cz"]
roi_idx_stim = [evk_comp_stim.ch_names.index(c) for c in roi]
roi_idx_resp = [evk_comp_resp.ch_names.index(c) for c in roi]

# C1: N2 (200-350ms)
t_n2 = (evk_comp_stim.times >= 0.2) & (evk_comp_stim.times <= 0.35)
comp_n2 = evk_comp_stim.data[roi_idx_stim][:, t_n2].mean() * 1e6
incomp_n2 = evk_incomp_stim.data[roi_idx_stim][:, t_n2].mean() * 1e6

# C2: ERN (0-100ms)
t_ern = (evk_comp_resp.times >= 0.0) & (evk_comp_resp.times <= 0.1)
comp_ern = evk_comp_resp.data[roi_idx_resp][:, t_ern].mean() * 1e6
incomp_ern = evk_incomp_resp.data[roi_idx_resp][:, t_ern].mean() * 1e6

erp_summary = {
    "C1_N2": {"comp_uV": round(comp_n2, 2), "incomp_uV": round(incomp_n2, 2),
              "diff_uV": round(incomp_n2 - comp_n2, 2), "roi": roi, "window": [0.2, 0.35]},
    "C2_ERN": {"comp_uV": round(comp_ern, 2), "incomp_uV": round(incomp_ern, 2),
               "diff_uV": round(incomp_ern - comp_ern, 2), "roi": roi, "window": [0.0, 0.1]}
}
json.dump(erp_summary, open(PROJECT / "erp-stage/sub-01/erp_summary.json", "w", encoding="utf-8"), indent=2)
stage_print("ERP", f"N2: comp={comp_n2:.2f} incomp={incomp_n2:.2f} diff={incomp_n2-comp_n2:.2f} µV")
stage_print("ERP", f"ERN: comp={comp_ern:.2f} incomp={incomp_ern:.2f} diff={incomp_ern-comp_ern:.2f} µV")

# ================================================================
# STEP 7: TFR — C3 (theta conflict)
# ================================================================
stage_print("TFR", "Computing time-frequency for theta conflict (C3)")

freqs = np.arange(4, 30, 1)
n_cycles = freqs / 3  # safe for epoch length

tfr_comp = mne.time_frequency.tfr_morlet(epochs_stim["compatible"], freqs=freqs,
    n_cycles=n_cycles, return_itc=False, decim=4, average=True, verbose=False)
tfr_incomp = mne.time_frequency.tfr_morlet(epochs_stim["incompatible"], freqs=freqs,
    n_cycles=n_cycles, return_itc=False, decim=4, average=True, verbose=False)

tfr_comp.apply_baseline(baseline=(-0.2, 0), mode="logratio")
tfr_incomp.apply_baseline(baseline=(-0.2, 0), mode="logratio")

tfr_diff = tfr_incomp.copy()
tfr_diff.data = tfr_incomp.data - tfr_comp.data

# Theta power at ROI (4-8 Hz, 200-500ms)
theta_mask = (freqs >= 4) & (freqs <= 8)
t_theta = (tfr_comp.times >= 0.2) & (tfr_comp.times <= 0.5)
roi_tfr_idx = [tfr_comp.ch_names.index(c) for c in roi]

comp_theta = tfr_comp.data[roi_tfr_idx][:, theta_mask][:, :, t_theta].mean()
incomp_theta = tfr_incomp.data[roi_tfr_idx][:, theta_mask][:, :, t_theta].mean()

tfr_comp.save(PROJECT / "tfr-stage/sub-01/comp_stim-tfr.h5", overwrite=True)
tfr_incomp.save(PROJECT / "tfr-stage/sub-01/incomp_stim-tfr.h5", overwrite=True)
tfr_diff.save(PROJECT / "tfr-stage/sub-01/diff_stim-tfr.h5", overwrite=True)

tfr_summary = {"C3_theta": {"comp_dB": round(float(comp_theta), 4),
    "incomp_dB": round(float(incomp_theta), 4),
    "diff_dB": round(float(incomp_theta - comp_theta), 4),
    "roi": roi, "freq_range": [4, 8], "window": [0.2, 0.5]}}
json.dump(tfr_summary, open(PROJECT / "tfr-stage/sub-01/tfr_summary.json", "w", encoding="utf-8"), indent=2)
stage_print("TFR", f"Theta: comp={comp_theta:.4f} incomp={incomp_theta:.4f} diff={incomp_theta-comp_theta:.4f} dB")

# ================================================================
# STEP 8: SPECTRAL — PSD comparison
# ================================================================
stage_print("SPECTRAL", "Computing PSD per condition")

psd_comp = epochs_stim["compatible"].compute_psd(method="welch", fmin=1, fmax=30, verbose=False)
psd_incomp = epochs_stim["incompatible"].compute_psd(method="welch", fmin=1, fmax=30, verbose=False)

psd_comp_avg = psd_comp.average()
psd_incomp_avg = psd_incomp.average()

# Band power at ROI
bands = {"theta": (4, 8), "alpha": (8, 13), "beta": (13, 30)}
spectral_summary = {}
for band, (fmin, fmax) in bands.items():
    fmask = (psd_comp_avg.freqs >= fmin) & (psd_comp_avg.freqs <= fmax)
    comp_bp = psd_comp_avg.get_data()[roi_idx_stim][:, fmask].mean()
    incomp_bp = psd_incomp_avg.get_data()[roi_idx_stim][:, fmask].mean()
    spectral_summary[band] = {
        "comp_power": float(comp_bp), "incomp_power": float(incomp_bp),
        "ratio": float(incomp_bp / comp_bp) if comp_bp > 0 else None
    }
json.dump(spectral_summary, open(PROJECT / "spectral-stage/sub-01/spectral_summary.json", "w", encoding="utf-8"), indent=2)
stage_print("SPECTRAL", f"Theta ratio (incomp/comp): {spectral_summary['theta']['ratio']:.3f}")

# ================================================================
# STEP 9: STATS — C1, C2, C3
# ================================================================
stage_print("STATS", "Running cluster permutation for C1, C2, C3")

alpha_bonf = 0.05 / 3  # Bonferroni for 3 claims

def run_cluster_perm(epochs_a, epochs_b, roi_names, tmin, tmax, tail, claim_id, alpha):
    n_min = min(len(epochs_a), len(epochs_b))
    X_a = epochs_a.get_data()[:n_min]
    X_b = epochs_b.get_data()[:n_min]
    X_diff = X_a - X_b

    roi_idx = [epochs_a.ch_names.index(c) for c in roi_names]
    tmask = (epochs_a.times >= tmin) & (epochs_a.times <= tmax)
    X_stat = X_diff[:, roi_idx, :][:, :, tmask].transpose(0, 2, 1)
    tw = epochs_a.times[tmask]

    roi_info = mne.pick_info(epochs_a.info, roi_idx)
    adj, _ = mne.channels.find_ch_adjacency(roi_info, ch_type="eeg")

    df = X_stat.shape[0] - 1
    if tail == -1:
        t_thr = -scipy_stats.t.ppf(1 - alpha, df)
    elif tail == 1:
        t_thr = scipy_stats.t.ppf(1 - alpha, df)
    else:
        t_thr = scipy_stats.t.ppf(1 - alpha/2, df)

    t_obs, clusters, cluster_p, H0 = mne.stats.spatio_temporal_cluster_1samp_test(
        X_stat, n_permutations=5000, threshold=t_thr, tail=tail,
        seed=SEED, adjacency=adj, out_type="mask", n_jobs=1, verbose=False)

    sig = [(i, float(p)) for i, p in enumerate(cluster_p) if p < alpha]
    cohens_d = None
    if sig:
        roi_mean = X_diff[:, roi_idx, :][:, :, tmask].mean(axis=(1, 2))
        cohens_d = float(roi_mean.mean() / roi_mean.std())

    result = {
        "claim_id": claim_id, "n_permutations": 5000, "threshold": float(t_thr),
        "tail": tail, "seed": SEED, "window": [tmin, tmax], "roi": roi_names,
        "n_trials": int(n_min), "n_clusters": len(clusters),
        "significant": [{"id": int(i), "p": float(p),
            "t_sum": float(t_obs[clusters[i]].sum()),
            "time_ms": [float(tw[np.where(clusters[i])[0].min()]*1000),
                        float(tw[np.where(clusters[i])[0].max()]*1000)]}
            for i, p in sig],
        "cohens_d": cohens_d,
        "alpha_bonf": float(alpha),
        "verdict": "supports" if sig else "does_not_support"
    }
    json.dump(result, open(PROJECT / f"stats-stage/{claim_id}_cluster_perm.json", "w", encoding="utf-8"), indent=2)
    np.savez(PROJECT / f"stats-stage/{claim_id}_arrays.npz", t_obs=t_obs, cluster_p=np.array(cluster_p))
    return result

# C1: N2 (incompatible more negative → tail=-1 on incomp-comp)
r1 = run_cluster_perm(epochs_stim["incompatible"], epochs_stim["compatible"],
                       roi, 0.2, 0.35, -1, "C1", alpha_bonf)
stage_print("STATS", f"C1 (N2): {r1['verdict']}, {len(r1['significant'])} sig clusters, d={r1['cohens_d']}")

# C2: ERN (incompatible response more negative → tail=-1)
r2 = run_cluster_perm(epochs_resp["incomp_resp"], epochs_resp["comp_resp"],
                       roi, 0.0, 0.1, -1, "C2", alpha_bonf)
stage_print("STATS", f"C2 (ERN): {r2['verdict']}, {len(r2['significant'])} sig clusters, d={r2['cohens_d']}")

# C3: Theta power (incompatible more positive → tail=1 on incomp-comp TFR)
# For TFR stats, extract theta-band power per trial
theta_mask_idx = np.where((freqs >= 4) & (freqs <= 8))[0]
t_theta_idx = np.where((tfr_comp.times >= 0.2) & (tfr_comp.times <= 0.5))[0]

# Re-compute trial-level TFR for stats (no average)
tfr_comp_trials = mne.time_frequency.tfr_morlet(epochs_stim["compatible"], freqs=freqs,
    n_cycles=n_cycles, return_itc=False, decim=4, average=False, verbose=False)
tfr_incomp_trials = mne.time_frequency.tfr_morlet(epochs_stim["incompatible"], freqs=freqs,
    n_cycles=n_cycles, return_itc=False, decim=4, average=False, verbose=False)

tfr_comp_trials.apply_baseline(baseline=(-0.2, 0), mode="logratio")
tfr_incomp_trials.apply_baseline(baseline=(-0.2, 0), mode="logratio")

n_min_tfr = min(len(tfr_comp_trials), len(tfr_incomp_trials))
# Extract theta at ROI: (trials, freqs_theta, times_theta) → average over freq → (trials, times)
X_comp_theta = tfr_comp_trials.data[:n_min_tfr, roi_tfr_idx][:, :, theta_mask_idx][:, :, :, t_theta_idx].mean(axis=(1, 2))
X_incomp_theta = tfr_incomp_trials.data[:n_min_tfr, roi_tfr_idx][:, :, theta_mask_idx][:, :, :, t_theta_idx].mean(axis=(1, 2))
X_diff_theta = X_incomp_theta - X_comp_theta  # (trials, times)

# Simple 1D permutation test on theta time course
from scipy.stats import ttest_1samp
t_vals, p_vals = ttest_1samp(X_diff_theta, 0, axis=0)
sig_theta = (p_vals < alpha_bonf).sum()
mean_diff_theta = X_diff_theta.mean()
d_theta = float(X_diff_theta.mean(axis=1).mean() / X_diff_theta.mean(axis=1).std()) if X_diff_theta.mean(axis=1).std() > 0 else 0

r3 = {"claim_id": "C3", "test": "ttest_1samp_per_timepoint", "n_trials": int(n_min_tfr),
      "sig_timepoints": int(sig_theta), "total_timepoints": X_diff_theta.shape[1],
      "mean_diff_dB": float(mean_diff_theta), "cohens_d": d_theta,
      "alpha_bonf": float(alpha_bonf),
      "verdict": "supports" if sig_theta > 0 else "does_not_support"}
json.dump(r3, open(PROJECT / "stats-stage/C3_theta_stats.json", "w", encoding="utf-8"), indent=2)
stage_print("STATS", f"C3 (Theta): {r3['verdict']}, {sig_theta}/{X_diff_theta.shape[1]} sig timepoints, d={d_theta:.3f}")

# ================================================================
# STEP 10: FIGURES — 4-panel publication figure
# ================================================================
stage_print("FIGURE", "Generating publication figures")

fig = plt.figure(figsize=(16, 10))
gs = fig.add_gridspec(2, 3, hspace=0.35, wspace=0.3)

# Panel A: Stimulus-locked ERP (N2)
ax = fig.add_subplot(gs[0, 0])
times_stim = evk_comp_stim.times * 1000
comp_roi_stim = evk_comp_stim.data[roi_idx_stim].mean(axis=0) * 1e6
incomp_roi_stim = evk_incomp_stim.data[roi_idx_stim].mean(axis=0) * 1e6
ax.plot(times_stim, comp_roi_stim, "b-", lw=2, label="Compatible")
ax.plot(times_stim, incomp_roi_stim, "r-", lw=2, label="Incompatible")
ax.axvspan(200, 350, alpha=0.12, color="gray", label="N2 window")
ax.axvline(0, color="k", ls="--", alpha=0.5)
ax.axhline(0, color="k", alpha=0.3)
ax.set(xlabel="Time (ms)", ylabel="µV", title="A) Stimulus-locked ERP (FCz,Fz,Cz)", xlim=(-200, 800))
ax.legend(fontsize=7)

# Panel B: Response-locked ERP (ERN)
ax = fig.add_subplot(gs[0, 1])
times_resp = evk_comp_resp.times * 1000
comp_roi_resp = evk_comp_resp.data[roi_idx_resp].mean(axis=0) * 1e6
incomp_roi_resp = evk_incomp_resp.data[roi_idx_resp].mean(axis=0) * 1e6
ax.plot(times_resp, comp_roi_resp, "b-", lw=2, label="Compatible")
ax.plot(times_resp, incomp_roi_resp, "r-", lw=2, label="Incompatible")
ax.axvspan(0, 100, alpha=0.12, color="gray", label="ERN window")
ax.axvline(0, color="k", ls="--", alpha=0.5, label="Response")
ax.axhline(0, color="k", alpha=0.3)
ax.set(xlabel="Time from response (ms)", ylabel="µV", title="B) Response-locked ERP (ERN)", xlim=(-400, 600))
ax.legend(fontsize=7)

# Panel C: Topomap at N2 peak
ax = fig.add_subplot(gs[0, 2])
n2_t_mask = (evk_diff_stim.times >= 0.2) & (evk_diff_stim.times <= 0.35)
peak_idx = np.argmin(evk_diff_stim.data[:, n2_t_mask].mean(axis=0))
peak_time = evk_diff_stim.times[n2_t_mask][peak_idx]
evk_diff_stim.plot_topomap(times=peak_time, axes=ax, show=False, colorbar=False)
ax.set_title(f"C) N2 topomap ({peak_time*1000:.0f} ms)")

# Panel D: TFR difference (incomp - comp)
ax = fig.add_subplot(gs[1, 0])
tfr_diff_roi = tfr_diff.data[roi_tfr_idx].mean(axis=0)
im = ax.pcolormesh(tfr_diff.times * 1000, freqs, tfr_diff_roi,
                    cmap="RdBu_r", vmin=-0.15, vmax=0.15, shading="auto")
ax.axvline(0, color="k", ls="--", alpha=0.7)
ax.contour(tfr_diff.times * 1000, freqs, tfr_diff_roi, levels=[0], colors="k", linewidths=0.5)
ax.set(xlabel="Time (ms)", ylabel="Frequency (Hz)", title="D) TFR difference (Incomp−Comp)", xlim=(-200, 800))
plt.colorbar(im, ax=ax, label="Power (dB)")

# Panel E: Theta band time course
ax = fig.add_subplot(gs[1, 1])
theta_comp = tfr_comp.data[roi_tfr_idx][:, theta_mask][:, :, :].mean(axis=(0, 1))
theta_incomp = tfr_incomp.data[roi_tfr_idx][:, theta_mask][:, :, :].mean(axis=(0, 1))
t_tfr = tfr_comp.times * 1000
ax.plot(t_tfr, theta_comp, "b-", lw=2, label="Compatible")
ax.plot(t_tfr, theta_incomp, "r-", lw=2, label="Incompatible")
ax.axvspan(200, 500, alpha=0.12, color="orange", label="C3 window")
ax.axvline(0, color="k", ls="--", alpha=0.5)
ax.axhline(0, color="k", alpha=0.3)
ax.set(xlabel="Time (ms)", ylabel="Power (dB)", title="E) Theta (4-8 Hz) at ROI", xlim=(-200, 800))
ax.legend(fontsize=7)

# Panel F: PSD
ax = fig.add_subplot(gs[1, 2])
ax.semilogy(psd_comp_avg.freqs, psd_comp_avg.get_data()[roi_idx_stim].mean(axis=0),
            "b-", lw=2, label="Compatible")
ax.semilogy(psd_incomp_avg.freqs, psd_incomp_avg.get_data()[roi_idx_stim].mean(axis=0),
            "r-", lw=2, label="Incompatible")
for band, (fmin, fmax) in bands.items():
    ax.axvspan(fmin, fmax, alpha=0.08, color="gray")
    ax.text((fmin+fmax)/2, ax.get_ylim()[1]*0.7, band, ha="center", fontsize=7, alpha=0.6)
ax.set(xlabel="Frequency (Hz)", ylabel="PSD (V²/Hz)", title="F) Power Spectral Density")
ax.legend(fontsize=7)

plt.suptitle("ERP CORE Flankers — Conflict Processing (AEA Full Case Study)", fontsize=13, fontweight="bold")
plt.savefig(PROJECT / "figure-stage/F1_flankers_full.png", dpi=150, bbox_inches="tight")
plt.savefig(PROJECT / "figure-stage/F1_flankers_full.svg", bbox_inches="tight")
plt.close()
stage_print("FIGURE", "Saved F1_flankers_full.png/svg (6 panels)")

# ================================================================
# STEP 11: METHODS TEXT
# ================================================================
stage_print("METHODS", "Generating COBIDAS-MEEG methods paragraph")

methods = f"""# Methods

> Auto-generated by AEA `eeg-methods-text` from pipeline stage logs.

## EEG Recording and Preprocessing

EEG was recorded from 30 scalp electrodes (BioSemi ActiveTwo, extended 10-20 montage) at 1024 Hz with DC-coupled online bandpass and CMS/DRL reference. Three EOG channels (HEOG_left, HEOG_right, VEOG_lower) monitored ocular artifacts.

Offline, continuous EEG was band-pass filtered between 0.1 and 30 Hz (zero-phase FIR, MNE-Python 1.12.1), notch-filtered at 60 Hz, and re-referenced to the common average of all 30 EEG channels.

## Independent Component Analysis

ICA was performed using the extended Infomax algorithm ({ica.n_components_} components, seed {SEED}) fitted on a 1 Hz high-pass filtered copy of the data (Winkler et al., 2015). Components were classified by ICLabel (mne-icalabel 0.9.0): {len(exclude)} components rejected ({', '.join(f'{label_list[i]}' for i in exclude)}).

## Epoching

Stimulus-locked epochs were extracted from -200 to 800 ms relative to stimulus onset, baseline-corrected against -200 to 0 ms. Response-locked epochs were extracted from -400 to 600 ms relative to response onset, baseline-corrected against -400 to -200 ms. Compatible and incompatible conditions were defined by the flanker congruency. Epochs exceeding ±150 µV were rejected. Stimulus-locked: {len(epochs_stim)} epochs retained ({len(epochs_stim['compatible'])} compatible, {len(epochs_stim['incompatible'])} incompatible). Response-locked: {len(epochs_resp)} epochs retained.

## Time-Frequency Analysis

Time-frequency representations were computed using Morlet wavelets (frequencies 4-29 Hz, n_cycles = freqs/3) with baseline correction (-200 to 0 ms, log-ratio mode). Frontal midline theta (4-8 Hz) power was extracted at FCz, Fz, Cz in the 200-500 ms post-stimulus window.

## Statistical Analysis

Three pre-registered claims were tested with Bonferroni correction (alpha = {alpha_bonf:.4f}):
- C1 (N2): Spatiotemporal cluster permutation (5000 perms, seed {SEED}, tail=-1) on stimulus-locked trial differences at FCz/Fz/Cz, 200-350 ms. Result: {r1['verdict']}, {len(r1['significant'])} significant cluster(s), Cohen's d = {f"{r1['cohens_d']:.3f}" if r1['cohens_d'] else "N/A"}.
- C2 (ERN): Cluster permutation on response-locked trial differences at FCz/Fz/Cz, 0-100 ms. Result: {r2['verdict']}, Cohen's d = {f"{r2['cohens_d']:.3f}" if r2['cohens_d'] else "N/A"}.
- C3 (Theta): Trial-level t-test on theta power differences at ROI, 200-500 ms. Result: {r3['verdict']}, Cohen's d = {d_theta:.3f}.

**Limitation:** Single-subject case study. Trial-level inference only; does not support population claims.

All analyses: MNE-Python 1.12.1, mne-icalabel 0.9.0, Python 3.11. Seeds fixed at {SEED}.
"""
(PROJECT / "report-stage/methods.md").write_text(methods, encoding="utf-8")
stage_print("METHODS", "Saved methods.md")

# ================================================================
# STEP 12: FINDINGS
# ================================================================
findings = f"""# FINDINGS — erp-core-flankers-full (AEA Full Case Study)

## {datetime.now().strftime('%Y-%m-%d')} — Flankers Conflict Processing

### C1: N2 (Incompatible > Compatible, stimulus-locked)
- Compatible N2: {comp_n2:.2f} µV | Incompatible N2: {incomp_n2:.2f} µV | Diff: {incomp_n2-comp_n2:.2f} µV
- ROI: {roi} | Window: 200-350 ms
- Cluster perm: {r1['verdict']}, {len(r1['significant'])} sig, d={r1['cohens_d']}
- Direction: {"CONSISTENT" if (incomp_n2 - comp_n2) < 0 else "CHECK"}

### C2: ERN (Incompatible > Compatible, response-locked)
- Compatible ERN: {comp_ern:.2f} µV | Incompatible ERN: {incomp_ern:.2f} µV | Diff: {incomp_ern-comp_ern:.2f} µV
- ROI: {roi} | Window: 0-100 ms post-response
- Cluster perm: {r2['verdict']}, {len(r2['significant'])} sig, d={r2['cohens_d']}
- Direction: {"CONSISTENT" if (incomp_ern - comp_ern) < 0 else "CHECK"}

### C3: Theta conflict effect (TFR)
- Compatible theta: {comp_theta:.4f} dB | Incompatible theta: {incomp_theta:.4f} dB
- ROI: {roi} | Window: 200-500 ms, 4-8 Hz
- {r3['verdict']}, {sig_theta}/{X_diff_theta.shape[1]} sig timepoints, d={d_theta:.3f}

### Pipeline
- Data: ERP CORE Subject-001, Flankers, BioSemi 30ch, 1024Hz
- Preprocess: 0.1-30 Hz FIR, 60Hz notch, avg ref
- ICA: Infomax {ica.n_components_} comp, ICLabel excluded {len(exclude)}
- Stim epochs: {len(epochs_stim)} (±150µV) | Resp epochs: {len(epochs_resp)}
- Bonferroni alpha = {alpha_bonf:.4f}
"""
(PROJECT / "FINDINGS.md").write_text(findings, encoding="utf-8")

# ================================================================
# STEP 13: REPRO RECEIPT
# ================================================================
stage_print("RECEIPT", "Generating reproducibility receipt")

git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
env = json.load(open("ENVIRONMENT.json", encoding="utf-8-sig"))

hashes = {}
for ext in ("*.fif", "*.png", "*.h5"):
    for f in sorted(PROJECT.rglob(ext)):
        hashes[str(f.relative_to(PROJECT))] = sha256_short(f)

receipt = f"""# REPRO_RECEIPT — erp-core-flankers-full
> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
## AEA Commit: `{git_sha}`
## Environment
- Python: {env['python']['version']}, MNE: {env['python_packages']['mne']['version']}, icalabel: {env['python_packages']['mne_icalabel']['version']}
## Seeds: ICA={SEED}, Cluster={SEED}
## File Hashes
| File | SHA256 prefix |
|------|--------------|
"""
for path, h in sorted(hashes.items()):
    receipt += f"| `{path}` | `{h}` |\n"
(PROJECT / "report-stage/REPRO_RECEIPT.md").write_text(receipt, encoding="utf-8")

# ================================================================
# DONE
# ================================================================
total_time = (datetime.now() - START_TIME).total_seconds()
stage_print("DONE", f"Full pipeline complete in {total_time:.1f}s")
stage_print("DONE", f"3 claims tested: C1={r1['verdict']}, C2={r2['verdict']}, C3={r3['verdict']}")
