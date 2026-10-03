"""AEA Case Study: mne-sample-audvis — ICA → Epoch → ERP → Figure end-to-end.
Run: conda run -n aeais python tools/run_case_study.py
"""
import mne, json, numpy as np, sys, os
from pathlib import Path
from datetime import datetime

mne.set_log_level("WARNING")
PROJECT = Path("projects/mne-sample-audvis")
SEED = 42

# === BOOTSTRAP (clean-clone safe) ===
# Ensure the raw symlink and the preprocessed input both exist, fetching the
# free MNE sample dataset if needed. Without this, a fresh clone fails here
# because preprocess-stage/ is gitignored and never produced by a committed step.
raw_link = PROJECT / "raw" / "sub-01.fif"
if not raw_link.exists():
    raw_link.parent.mkdir(parents=True, exist_ok=True)
    sample_raw = Path(mne.datasets.sample.data_path()) / "MEG" / "sample" / "sample_audvis_raw.fif"
    os.symlink(sample_raw, raw_link)
    print(f"=== BOOTSTRAP === linked sample data -> {raw_link}", flush=True)

pp_path = PROJECT / "preprocess-stage" / "sub-01" / "sub-01_preprocessed_raw.fif"
if not pp_path.exists():
    print("=== PREPROCESS (bootstrap) ===", flush=True)
    pp_path.parent.mkdir(parents=True, exist_ok=True)
    raw_bs = mne.io.read_raw_fif(raw_link, preload=True)
    raw_bs.pick_types(meg=False, eeg=True, exclude="bads")
    raw_bs.filter(l_freq=0.1, h_freq=40.0, n_jobs=1)
    raw_bs.set_eeg_reference("average", projection=False)
    raw_bs.save(pp_path, overwrite=True)
    json.dump({"bandpass": [0.1, 40], "reference": "average",
               "n_ch": raw_bs.info["nchan"], "sfreq": raw_bs.info["sfreq"]},
              open(pp_path.parent / "preprocess_summary.json", "w", encoding="utf-8"), indent=2)
    print(f"  Preprocessed -> {pp_path} ({raw_bs.info['nchan']} EEG ch, 0.1-40 Hz, avg ref)", flush=True)

# === ICA ===
print("=== ICA ===", flush=True)
ica_dir = PROJECT / "ica-stage" / "sub-01"
ica_dir.mkdir(parents=True, exist_ok=True)
raw_pp = mne.io.read_raw_fif(PROJECT / "preprocess-stage/sub-01/sub-01_preprocessed_raw.fif", preload=True)
raw_hp = raw_pp.copy().filter(l_freq=1.0, h_freq=None)
ica = mne.preprocessing.ICA(n_components=15, method="infomax", random_state=SEED,
                             max_iter="auto", fit_params=dict(extended=True))
ica.fit(raw_hp)
print(f"  Fit {ica.n_components_} components", flush=True)

from mne_icalabel import label_components
labels = label_components(raw_hp, ica, method="iclabel")
label_list = labels["labels"]
exclude = [i for i, l in enumerate(label_list) if l in {"eye blink", "muscle artifact", "heart beat"}]
ica.exclude = exclude
print(f"  ICLabel: {list(enumerate(label_list))}", flush=True)
print(f"  Excluding: {exclude}", flush=True)

raw_clean = raw_pp.copy()
ica.apply(raw_clean)
ica_path = ica_dir / "sub-01_ica-cleaned_raw.fif"
raw_clean.save(ica_path, overwrite=True)
json.dump({"excluded": exclude, "labels": label_list, "seed": SEED},
          open(ica_dir / "ica_summary.json", "w", encoding="utf-8"), indent=2)
print(f"  Saved: {ica_path}", flush=True)

# === EPOCH ===
print("\n=== EPOCH ===", flush=True)
epoch_dir = PROJECT / "epoch-stage" / "sub-01"
epoch_dir.mkdir(parents=True, exist_ok=True)

raw_orig = mne.io.read_raw_fif(PROJECT / "raw/sub-01.fif", preload=False)
events = mne.find_events(raw_orig, stim_channel="STI 014", shortest_event=1)
event_id = {"auditory/left": 1, "auditory/right": 2, "visual/left": 3, "visual/right": 4}

epochs = mne.Epochs(raw_clean, events, event_id=event_id,
                     tmin=-0.2, tmax=0.5, baseline=(-0.2, 0),
                     preload=True, reject=dict(eeg=150e-6))
per_cond = {k: len(epochs[k]) for k in event_id}
print(f"  {len(epochs)} epochs: {per_cond}", flush=True)
epochs.save(epoch_dir / "sub-01-epo.fif", overwrite=True)
json.dump({"n_epochs": len(epochs), "per_cond": per_cond},
          open(epoch_dir / "epoch_summary.json", "w", encoding="utf-8"), indent=2)

# === ERP ===
print("\n=== ERP ===", flush=True)
erp_dir = PROJECT / "erp-stage" / "sub-01"
erp_dir.mkdir(parents=True, exist_ok=True)

aud = mne.concatenate_epochs([epochs["auditory/left"], epochs["auditory/right"]])
vis = mne.concatenate_epochs([epochs["visual/left"], epochs["visual/right"]])
evk_aud, evk_vis = aud.average(), vis.average()
evk_diff = mne.combine_evoked([evk_aud, evk_vis], weights=[1, -1])

evk_aud.save(erp_dir / "auditory-ave.fif", overwrite=True)
evk_vis.save(erp_dir / "visual-ave.fif", overwrite=True)
evk_diff.save(erp_dir / "aud-minus-vis-ave.fif", overwrite=True)

roi = [ch for ch in evk_aud.ch_names[:6]]
ch_idx = [evk_aud.ch_names.index(c) for c in roi]
t_mask = (evk_aud.times >= 0.08) & (evk_aud.times <= 0.15)
aud_n100 = evk_aud.data[ch_idx][:, t_mask].mean() * 1e6
vis_n100 = evk_vis.data[ch_idx][:, t_mask].mean() * 1e6
print(f"  Aud N100: {aud_n100:.2f} µV, Vis: {vis_n100:.2f} µV, Diff: {aud_n100-vis_n100:.2f} µV", flush=True)
json.dump({"aud_N100_uV": round(aud_n100, 2), "vis_N100_uV": round(vis_n100, 2),
           "diff_uV": round(aud_n100 - vis_n100, 2), "roi": roi,
           "aud_trials": len(aud), "vis_trials": len(vis)},
          open(erp_dir / "erp_summary.json", "w", encoding="utf-8"), indent=2)

# === FIGURE ===
print("\n=== FIGURE ===", flush=True)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig_dir = PROJECT / "figure-stage"
fig_dir.mkdir(parents=True, exist_ok=True)

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
times = evk_aud.times * 1000

# Panel A
ax = axes[0]
aud_roi = evk_aud.data[ch_idx].mean(axis=0) * 1e6
vis_roi = evk_vis.data[ch_idx].mean(axis=0) * 1e6
ax.plot(times, aud_roi, "b-", lw=2, label="Auditory")
ax.plot(times, vis_roi, "r-", lw=2, label="Visual")
ax.axvspan(80, 150, alpha=0.15, color="gray")
ax.axvline(0, color="k", ls="--", alpha=0.5)
ax.axhline(0, color="k", alpha=0.3)
ax.set(xlabel="Time (ms)", ylabel="µV", title="A) ERP at frontocentral ROI", xlim=(-200, 500))
ax.legend(fontsize=8)

# Panel B
ax = axes[1]
diff_roi = evk_diff.data[ch_idx].mean(axis=0) * 1e6
ax.plot(times, diff_roi, "k-", lw=2)
ax.fill_between(times, diff_roi, where=((evk_diff.times >= 0.08) & (evk_diff.times <= 0.15)),
                alpha=0.3, color="orange")
ax.axvline(0, color="k", ls="--", alpha=0.5)
ax.axhline(0, color="k", alpha=0.3)
ax.set(xlabel="Time (ms)", ylabel="µV", title="B) Difference (Aud − Vis)", xlim=(-200, 500))

# Panel C: topomap needs 2 axes (data + colorbar)
peak_idx = np.argmin(evk_diff.data[:, t_mask].mean(axis=0))
peak_time = evk_diff.times[t_mask][peak_idx]
# Remove original axes[2] and create 2 sub-axes for topomap
axes[2].remove()
gs = fig.add_gridspec(1, 4, width_ratios=[1, 1, 0.8, 0.05])
ax_topo = fig.add_subplot(gs[0, 2])
ax_cbar = fig.add_subplot(gs[0, 3])
evk_diff.plot_topomap(times=peak_time, axes=[ax_topo, ax_cbar], show=False, colorbar=True)
ax_topo.set_title(f"C) Topomap at {peak_time*1000:.0f} ms")

plt.tight_layout()
plt.savefig(fig_dir / "F1_auditory_vs_visual_N100.png", dpi=150, bbox_inches="tight")
plt.savefig(fig_dir / "F1_auditory_vs_visual_N100.svg", bbox_inches="tight")
plt.close()
print(f"  Saved figures", flush=True)

# === FINDINGS ===
findings = f"""# FINDINGS — mne-sample-audvis

## {datetime.now().strftime('%Y-%m-%d')} — Case Study: Auditory vs Visual N100

### C1: Auditory > Visual N100
- Aud N100: {aud_n100:.2f} µV | Vis N100: {vis_n100:.2f} µV | Diff: {aud_n100-vis_n100:.2f} µV
- ROI: {roi} | Window: 80–150 ms
- Direction: {"CONSISTENT" if aud_n100 < vis_n100 else "CHECK"}
- Single subject, no group stats.

### Pipeline
- Preprocess: 0.1–40 Hz FIR, average ref, 59 EEG channels
- ICA: Infomax 15 comp, ICLabel excluded {len(exclude)}
- Epochs: {len(epochs)}, 150 µV peak-to-peak rejection
- Aud: {len(aud)} trials, Vis: {len(vis)} trials
"""
(PROJECT / "FINDINGS.md").write_text(findings, encoding="utf-8")

print("\n=== COMPLETE ===", flush=True)
import os
for root, dirs, files in os.walk(str(PROJECT)):
    level = root.replace(str(PROJECT), "").count(os.sep)
    indent = "  " * level
    print(f"{indent}{os.path.basename(root)}/")
    for f in sorted(files):
        sz = os.path.getsize(os.path.join(root, f))
        print(f"{indent}  {f} ({sz//1024}KB)" if sz > 1024 else f"{indent}  {f}")
