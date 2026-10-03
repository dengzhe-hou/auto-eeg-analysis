"""AEA validation on real EEG data: ERP CORE Flankers (Kappenman et al. 2021).
Paradigm: Eriksen Flankers → ERN (error-related negativity) at FCz.
Tests: compatible vs incompatible response-locked ERP.
"""
import mne, json, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime
from scipy import stats as scipy_stats

mne.set_log_level("WARNING")
SEED = 42
np.random.seed(SEED)

PROJECT = Path("projects/erp-core-flankers")

# === SETUP ===
print("=" * 60, flush=True)
print("AEA VALIDATION — ERP CORE Flankers (real EEG)", flush=True)
print("=" * 60, flush=True)

# Create project structure
for d in ["raw", "preprocess-stage/sub-01", "ica-stage/sub-01",
          "epoch-stage/sub-01", "erp-stage/sub-01", "stats-stage",
          "figure-stage", "report-stage"]:
    (PROJECT / d).mkdir(parents=True, exist_ok=True)

# Resolve data — ERP CORE is NOT auto-downloadable via mne.datasets; resolve a
# local copy by env override or the standard MNE data dir, else fail with a
# clear, actionable message (no hardcoded user-specific path).
import shutil, os

def _resolve_flankers():
    cands = []
    env = os.environ.get("AEA_ERP_CORE_FLANKERS")
    if env:
        cands.append(Path(env))
    mne_data = os.environ.get("MNE_DATA") or mne.get_config("MNE_DATA") or str(Path.home() / "mne_data")
    cands.append(Path(mne_data) / "MNE-ERP-CORE-data" / "ERP-CORE_Subject-001_Task-Flankers_eeg.fif")
    for c in cands:
        if c.exists():
            return c
    raise FileNotFoundError(
        "ERP CORE Flankers data not found. ERP CORE is not fetchable via mne.datasets.\n"
        "Download Subject-001 Flankers (Kappenman et al. 2021, https://doi.org/10.18115/D5JW4R) to:\n"
        f"  {cands[-1]}\n"
        "or set AEA_ERP_CORE_FLANKERS to the .fif path."
    )

src = _resolve_flankers()
dst = PROJECT / "raw" / "sub-01.fif"
if not dst.exists():
    os.symlink(src, dst)

# === AUTO-BRIEF ===
print("\n=== 1. AUTO-BRIEF ===", flush=True)
raw = mne.io.read_raw_fif(dst, preload=False)
events, event_id = mne.events_from_annotations(raw)
print(f"  30 EEG + 3 EOG, {raw.info['sfreq']} Hz, {raw.times[-1]:.0f}s", flush=True)
print(f"  Events: {event_id}", flush=True)
print(f"  Channels: {[ch for ch in raw.ch_names if ch not in ('HEOG_left','HEOG_right','VEOG_lower')]}", flush=True)

# === WRITE DATASET_BRIEF ===
brief = """# DATASET_BRIEF — erp-core-flankers
## 1. Study identity
- **Study short name:** erp-core-flankers
- **Paradigm:** Eriksen Flankers (compatible vs incompatible) — response-locked ERN
- **Hypothesis:** Incompatible trials elicit a larger ERN (more negative) than compatible at FCz
- **Source:** Kappenman et al. 2021, NeuroImage (ERP CORE)
## 2. Subjects
- **N:** 1 (validation demo)
## 3. Acquisition
- **System:** BioSemi ActiveTwo
- **Channels:** 30 EEG (10-20) + 3 EOG
- **Sampling rate:** 1024 Hz
- **Reference:** CMS/DRL (BioSemi), re-reference offline to average
## 4. Conditions
| Condition | Event | N trials |
|-----------|-------|----------|
| compatible/left | stimulus/compatible/target_left | 100 |
| compatible/right | stimulus/compatible/target_right | 100 |
| incompatible/left | stimulus/incompatible/target_left | 100 |
| incompatible/right | stimulus/incompatible/target_right | 100 |
| response/left | response/left | 202 |
| response/right | response/right | 200 |
## 5. Preprocessing
- Bandpass: 0.1–30 Hz (ERN-appropriate)
- Reference: average
- Epoch: -0.4 to 0.8 s response-locked
- Baseline: -0.4 to -0.2 s
"""
(PROJECT / "DATASET_BRIEF.md").write_text(brief, encoding="utf-8")

# === WRITE ANALYSIS_PLAN ===
plan = """# ANALYSIS_PLAN — erp-core-flankers
## Plan version
- **v1**, frozen 2026-05-22
## Claims
| Claim | Contrast | ROI | Window | Test | Direction | alpha |
|-------|----------|-----|--------|------|-----------|-------|
| C1 | incompatible_resp − compatible_resp | FCz, Cz, Fz | 0–0.1s post-response | cluster perm (trial-level, 1-sample) | incompatible more negative | 0.05 |
## Seeds
- ICA: 42, Cluster: 42
"""
(PROJECT / "ANALYSIS_PLAN.md").write_text(plan, encoding="utf-8")
print("  Brief + Plan written", flush=True)

# === PREPROCESS ===
print("\n=== 2. PREPROCESS ===", flush=True)
raw = mne.io.read_raw_fif(dst, preload=True)
raw.pick_types(eeg=True, eog=True)

# Keep EEG only for processing
raw_eeg = raw.copy().pick_types(eeg=True)
raw_eeg.filter(l_freq=0.1, h_freq=30.0, n_jobs=1)
raw_eeg.set_eeg_reference("average", projection=False)

pp_path = PROJECT / "preprocess-stage/sub-01/sub-01_preprocessed_raw.fif"
raw_eeg.save(pp_path, overwrite=True)
json.dump({"bandpass": [0.1, 30], "reference": "average", "n_ch": raw_eeg.info["nchan"],
           "sfreq": raw_eeg.info["sfreq"]},
          open(PROJECT / "preprocess-stage/sub-01/preprocess_summary.json", "w", encoding="utf-8"), indent=2)
print(f"  {raw_eeg.info['nchan']} EEG channels, 0.1–30 Hz, avg ref", flush=True)

# === ICA ===
print("\n=== 3. ICA + ICLabel ===", flush=True)
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
print(f"  {ica.n_components_} components, excluding {len(exclude)}: {[(i,label_list[i]) for i in exclude]}", flush=True)

raw_clean = raw_pp.copy()
ica.apply(raw_clean)
ica_path = PROJECT / "ica-stage/sub-01/sub-01_ica-cleaned_raw.fif"
raw_clean.save(ica_path, overwrite=True)
json.dump({"excluded": exclude, "labels": label_list, "seed": SEED},
          open(PROJECT / "ica-stage/sub-01/ica_summary.json", "w", encoding="utf-8"), indent=2)

# === EPOCH (response-locked) ===
print("\n=== 4. EPOCH (response-locked) ===", flush=True)

# Get response events
raw_full = mne.io.read_raw_fif(dst, preload=False)
all_events, all_event_id = mne.events_from_annotations(raw_full)

# Find stimulus type for each response (compatible vs incompatible)
# Strategy: for each response event, look back to the nearest stimulus
stim_events = all_events[all_events[:, 2].astype(int) >= 3]  # stimulus events (codes 3-6)
resp_events = all_events[all_events[:, 2].astype(int) <= 2]  # response events (codes 1-2)

compatible_resp = []
incompatible_resp = []

for resp in resp_events:
    resp_time = resp[0]
    # Find most recent stimulus before this response
    prior_stim = stim_events[stim_events[:, 0] < resp_time]
    if len(prior_stim) == 0:
        continue
    last_stim = prior_stim[-1]
    stim_code = int(last_stim[2])
    if stim_code in (3, 4):  # compatible
        compatible_resp.append(resp)
    elif stim_code in (5, 6):  # incompatible
        incompatible_resp.append(resp)

compatible_resp = np.array(compatible_resp)
incompatible_resp = np.array(incompatible_resp)
print(f"  Compatible responses: {len(compatible_resp)}", flush=True)
print(f"  Incompatible responses: {len(incompatible_resp)}", flush=True)

# Create epochs locked to response
# Recode: compatible=101, incompatible=102
for e in compatible_resp:
    e[2] = 101
for e in incompatible_resp:
    e[2] = 102

resp_all = np.vstack([compatible_resp, incompatible_resp])
resp_all = resp_all[resp_all[:, 0].argsort()]

resp_event_id = {"compatible": 101, "incompatible": 102}
epochs = mne.Epochs(raw_clean, resp_all, event_id=resp_event_id,
                     tmin=-0.4, tmax=0.8, baseline=(-0.4, -0.2),
                     preload=True, reject=dict(eeg=150e-6))
print(f"  Epochs: {len(epochs)} total", flush=True)
print(f"  Per condition: { {k: len(epochs[k]) for k in resp_event_id} }", flush=True)

epochs.save(PROJECT / "epoch-stage/sub-01/sub-01-epo.fif", overwrite=True)
json.dump({"n_epochs": len(epochs),
           "per_cond": {k: len(epochs[k]) for k in resp_event_id}},
          open(PROJECT / "epoch-stage/sub-01/epoch_summary.json", "w", encoding="utf-8"), indent=2)

# === ERP ===
print("\n=== 5. ERP ===", flush=True)
evk_comp = epochs["compatible"].average()
evk_inco = epochs["incompatible"].average()
evk_diff = mne.combine_evoked([evk_inco, evk_comp], weights=[1, -1])

evk_comp.save(PROJECT / "erp-stage/sub-01/compatible-ave.fif", overwrite=True)
evk_inco.save(PROJECT / "erp-stage/sub-01/incompatible-ave.fif", overwrite=True)
evk_diff.save(PROJECT / "erp-stage/sub-01/inco-minus-comp-ave.fif", overwrite=True)

# ERN at FCz (0-100ms post-response)
roi = ["FCz", "Cz", "Fz"]
roi_available = [ch for ch in roi if ch in evk_comp.ch_names]
roi_idx = [evk_comp.ch_names.index(ch) for ch in roi_available]
ern_window = (0.0, 0.1)
t_mask = (evk_comp.times >= ern_window[0]) & (evk_comp.times <= ern_window[1])

comp_ern = evk_comp.data[roi_idx][:, t_mask].mean() * 1e6
inco_ern = evk_inco.data[roi_idx][:, t_mask].mean() * 1e6
print(f"  Compatible ERN ({roi_available}, 0-100ms): {comp_ern:.2f} µV", flush=True)
print(f"  Incompatible ERN ({roi_available}, 0-100ms): {inco_ern:.2f} µV", flush=True)
print(f"  Difference: {inco_ern - comp_ern:.2f} µV", flush=True)

json.dump({
    "comp_ERN_uV": round(comp_ern, 2), "inco_ERN_uV": round(inco_ern, 2),
    "diff_uV": round(inco_ern - comp_ern, 2), "roi": roi_available,
    "window": list(ern_window),
}, open(PROJECT / "erp-stage/sub-01/erp_summary.json", "w", encoding="utf-8"), indent=2)

# === STATS ===
print("\n=== 6. STATS (cluster permutation) ===", flush=True)
n_min = min(len(epochs["compatible"]), len(epochs["incompatible"]))
X_comp = epochs["compatible"].get_data()[:n_min]
X_inco = epochs["incompatible"].get_data()[:n_min]
X_diff = X_inco - X_comp  # incompatible - compatible

# Constrain to ROI + ERN window
tmask_stat = (epochs.times >= -0.05) & (epochs.times <= 0.15)
X_stat = X_diff[:, :, tmask_stat][:, [epochs.ch_names.index(c) for c in roi_available], :]
X_stat = X_stat.transpose(0, 2, 1)  # (trials, times, channels)
tw = epochs.times[tmask_stat]

roi_info = mne.pick_info(epochs.info, [epochs.ch_names.index(c) for c in roi_available])
adj, _ = mne.channels.find_ch_adjacency(roi_info, ch_type="eeg")

df = X_stat.shape[0] - 1
t_thr = -scipy_stats.t.ppf(1 - 0.05, df)
print(f"  {n_min} paired trials, {len(roi_available)} ROI ch, {tmask_stat.sum()} times", flush=True)
print(f"  Threshold: t={t_thr:.3f} (one-sided, df={df})", flush=True)

t_obs, clusters, cluster_p, H0 = mne.stats.spatio_temporal_cluster_1samp_test(
    X_stat, n_permutations=5000, threshold=t_thr, tail=-1,
    seed=SEED, adjacency=adj, out_type="mask", n_jobs=1, verbose=False,
)
sig = [(i, float(p)) for i, p in enumerate(cluster_p) if p < 0.05]
print(f"  {len(clusters)} clusters, {len(sig)} significant", flush=True)
for i, p in sig:
    mask = clusters[i]
    tidx, cidx = np.where(mask)
    t_sum = float(t_obs[mask].sum())
    print(f"  Cluster {i}: p={p:.4f}, t_sum={t_sum:.1f}, "
          f"{tw[tidx.min()]*1000:.0f}-{tw[tidx.max()]*1000:.0f}ms", flush=True)

# Effect size
cohens_d = None
if sig:
    roi_mean_comp = X_comp[:, [epochs.ch_names.index(c) for c in roi_available], :][:, :, tmask_stat].mean(axis=(1,2))
    roi_mean_inco = X_inco[:, [epochs.ch_names.index(c) for c in roi_available], :][:, :, tmask_stat].mean(axis=(1,2))
    d = roi_mean_inco - roi_mean_comp
    cohens_d = float(d.mean() / d.std())
    print(f"  Cohen's d: {cohens_d:.3f}", flush=True)

json.dump({
    "claim_id": "C1", "claim": "Incompatible > Compatible ERN",
    "test": "spatio_temporal_cluster_1samp_test (trial-level)",
    "n_permutations": 5000, "threshold": float(t_thr), "tail": -1, "seed": SEED,
    "window": [-0.05, 0.15], "roi": roi_available, "n_trials": int(n_min),
    "n_clusters": len(clusters),
    "significant": [{"id": int(i), "p": float(p), "t_sum": float(t_obs[clusters[i]].sum()),
                      "time_ms": [float(tw[np.where(clusters[i])[0].min()]*1000),
                                  float(tw[np.where(clusters[i])[0].max()]*1000)]}
                    for i, p in sig],
    "cohens_d": cohens_d,
    "verdict": "supports" if sig else "does_not_support",
}, open(PROJECT / "stats-stage/C1_cluster_perm.json", "w", encoding="utf-8"), indent=2)

# === FIGURE ===
print("\n=== 7. FIGURE ===", flush=True)
fig, axes = plt.subplots(1, 3, figsize=(15, 4))
times = evk_comp.times * 1000

# Panel A: ERP at ROI
ax = axes[0]
comp_data = evk_comp.data[roi_idx].mean(axis=0) * 1e6
inco_data = evk_inco.data[roi_idx].mean(axis=0) * 1e6
ax.plot(times, comp_data, "b-", lw=2, label="Compatible")
ax.plot(times, inco_data, "r-", lw=2, label="Incompatible")
ax.axvspan(0, 100, alpha=0.15, color="gray", label="ERN window")
ax.axvline(0, color="k", ls="--", alpha=0.7, label="Response")
ax.axhline(0, color="k", alpha=0.3)
ax.set(xlabel="Time from response (ms)", ylabel="µV",
       title=f"A) Response-locked ERP ({','.join(roi_available)})", xlim=(-400, 500))
ax.legend(fontsize=7)

# Panel B: Difference wave
ax = axes[1]
diff_data = evk_diff.data[roi_idx].mean(axis=0) * 1e6
ax.plot(times, diff_data, "k-", lw=2)
ax.fill_between(times, diff_data,
                where=((evk_diff.times >= 0) & (evk_diff.times <= 0.1)),
                alpha=0.3, color="orange", label="ERN window")
ax.axvline(0, color="k", ls="--", alpha=0.7)
ax.axhline(0, color="k", alpha=0.3)
ax.set(xlabel="Time from response (ms)", ylabel="µV",
       title="B) Difference (Incompat − Compat)", xlim=(-400, 500))
ax.legend(fontsize=8)

# Panel C: Topomap at ERN peak
ax = axes[2]
ern_t_mask = (evk_diff.times >= 0) & (evk_diff.times <= 0.1)
peak_idx = np.argmin(evk_diff.data[:, ern_t_mask].mean(axis=0))
peak_time = evk_diff.times[ern_t_mask][peak_idx]
axes[2].remove()
gs = fig.add_gridspec(1, 4, width_ratios=[1, 1, 0.8, 0.05])
ax_topo = fig.add_subplot(gs[0, 2])
ax_cbar = fig.add_subplot(gs[0, 3])
evk_diff.plot_topomap(times=peak_time, axes=[ax_topo, ax_cbar], show=False, colorbar=True)
ax_topo.set_title(f"C) Topomap at {peak_time*1000:.0f} ms")

plt.savefig(PROJECT / "figure-stage/F1_flankers_ERN.png", dpi=150, bbox_inches="tight")
plt.savefig(PROJECT / "figure-stage/F1_flankers_ERN.svg", bbox_inches="tight")
plt.close()
print("  Saved F1_flankers_ERN.png/svg", flush=True)

# === FINDINGS ===
findings = f"""# FINDINGS — erp-core-flankers (ERP CORE validation)

## {datetime.now().strftime('%Y-%m-%d')} — Flankers ERN: Incompatible vs Compatible

### C1: Incompatible > Compatible ERN
- Incompat ERN: {inco_ern:.2f} µV | Compat ERN: {comp_ern:.2f} µV | Diff: {inco_ern-comp_ern:.2f} µV
- ROI: {roi_available} | Window: 0–100 ms post-response
- Cluster perm: {len(sig)} significant, 5000 perms
- Cohen's d: {cohens_d:.3f} if cohens_d else 'N/A'
- Direction: {"CONSISTENT (incompat more negative)" if (inco_ern - comp_ern) < 0 else "CHECK"}
- **Real EEG data** (ERP CORE, Kappenman et al. 2021)
- Single subject, trial-level inference

### Pipeline
- Data: ERP CORE Subject-001, Flankers task, BioSemi 30 EEG, 1024 Hz
- Preprocess: 0.1–30 Hz FIR, average ref
- ICA: Infomax 15 comp, ICLabel excluded {len(exclude)}
- Epochs: {len(epochs)} response-locked, ±150µV reject
- Compatible: {len(epochs['compatible'])} trials, Incompatible: {len(epochs['incompatible'])} trials
"""
(PROJECT / "FINDINGS.md").write_text(findings, encoding="utf-8")

print(f"\n{'='*60}", flush=True)
print("VALIDATION COMPLETE — Real EEG data (ERP CORE Flankers)", flush=True)
print(f"{'='*60}", flush=True)
