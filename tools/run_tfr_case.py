"""eeg-tfr case study: time-frequency analysis on MNE sample auditory vs visual."""
import mne, json, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

mne.set_log_level("WARNING")
PROJECT = Path("projects/mne-sample-audvis")
SEED = 42

print("=== eeg-tfr: Time-Frequency Analysis ===", flush=True)

# Load epochs
epochs = mne.read_epochs(PROJECT / "epoch-stage/sub-01/sub-01-epo.fif", preload=True)

# Load channel mapping for ROI labels
ch_map = json.load(open(PROJECT / "channel_mapping.json", encoding="utf-8-sig"))

# Conditions
aud = mne.concatenate_epochs([epochs["auditory/left"], epochs["auditory/right"]])
vis = mne.concatenate_epochs([epochs["visual/left"], epochs["visual/right"]])

# TFR parameters
freqs = np.arange(6, 35, 1)  # 6-34 Hz (skip lowest theta to fit epoch)
n_cycles = freqs / 3  # fewer cycles → shorter wavelet, fits 0.7s epoch
decim = 2  # temporal decimation

print(f"  Freqs: {freqs[0]}-{freqs[-1]} Hz ({len(freqs)} bins)", flush=True)
print(f"  n_cycles: adaptive (freqs/3)", flush=True)
print(f"  Auditory: {len(aud)} trials, Visual: {len(vis)} trials", flush=True)

# Compute TFR per condition (averaged across trials)
print("  Computing TFR (auditory)...", flush=True)
tfr_aud = mne.time_frequency.tfr_morlet(
    aud, freqs=freqs, n_cycles=n_cycles, return_itc=False,
    decim=decim, average=True, verbose=False
)

print("  Computing TFR (visual)...", flush=True)
tfr_vis = mne.time_frequency.tfr_morlet(
    vis, freqs=freqs, n_cycles=n_cycles, return_itc=False,
    decim=decim, average=True, verbose=False
)

# MNE logratio is log10(power/baseline_power); multiply by 10 for dB.
baseline = (-0.2, 0)
tfr_aud.apply_baseline(baseline=baseline, mode="logratio")
tfr_vis.apply_baseline(baseline=baseline, mode="logratio")
tfr_aud.data *= 10
tfr_vis.data *= 10

# Difference
tfr_diff = tfr_aud.copy()
tfr_diff.data = tfr_aud.data - tfr_vis.data

print("  TFR computed and baselined", flush=True)

# Save TFR data
tfr_dir = PROJECT / "tfr-stage" / "sub-01"
tfr_dir.mkdir(parents=True, exist_ok=True)
tfr_aud.save(tfr_dir / "sub-01_auditory-tfr.h5", overwrite=True)
tfr_vis.save(tfr_dir / "sub-01_visual-tfr.h5", overwrite=True)
tfr_diff.save(tfr_dir / "sub-01_aud-minus-vis-tfr.h5", overwrite=True)

# Summary: mean power in canonical bands
bands = {
    "theta": (6, 7),
    "alpha": (8, 13),
    "beta": (14, 30),
}

# ROI: frontocentral (same as ERP analysis)
plan_roi = {"Fz", "Cz", "FC1", "FC2", "F3", "F4"}
roi_eeg = [ch for ch, name1020 in ch_map.items() if name1020 in plan_roi and ch in tfr_aud.ch_names]
roi_idx = [tfr_aud.ch_names.index(ch) for ch in roi_eeg]

# Time windows of interest
time_windows = {
    "early": (0.05, 0.15),
    "late": (0.15, 0.40),
}

band_summary = {}
for band_name, (fmin, fmax) in bands.items():
    freq_mask = (freqs >= fmin) & (freqs <= fmax)
    for tw_name, (tmin, tmax) in time_windows.items():
        time_mask = (tfr_aud.times >= tmin) & (tfr_aud.times <= tmax)
        aud_power = tfr_aud.data[roi_idx][:, freq_mask][:, :, time_mask].mean()
        vis_power = tfr_vis.data[roi_idx][:, freq_mask][:, :, time_mask].mean()
        key = f"{band_name}_{tw_name}"
        band_summary[key] = {
            "band": band_name, "freq_range": [int(fmin), int(fmax)],
            "time_window": [float(tmin), float(tmax)],
            "aud_power_dB": round(float(aud_power), 4),
            "vis_power_dB": round(float(vis_power), 4),
            "diff_dB": round(float(aud_power - vis_power), 4),
        }
        print(f"  {key}: aud={aud_power:.4f} dB, vis={vis_power:.4f} dB, diff={aud_power-vis_power:.4f} dB", flush=True)

tfr_summary = {
    "stage": "tfr",
    "method": "morlet",
    "freqs": [int(f) for f in freqs],
    "n_cycles": "freqs/3 (adaptive)",
    "baseline": list(baseline),
    "baseline_mode": "logratio",
    "logratio_scale": 10,
    "power_unit": "dB",
    "decim": decim,
    "roi_channels": roi_eeg,
    "roi_1020": [ch_map[c] for c in roi_eeg],
    "band_summary": band_summary,
    "aud_trials": len(aud),
    "vis_trials": len(vis),
}
json.dump(tfr_summary, open(tfr_dir / "tfr_summary.json", "w", encoding="utf-8"), indent=2)

# === FIGURES ===
print("\n=== TFR Figures ===", flush=True)
fig_dir = PROJECT / "figure-stage"

# Figure 2: TFR comparison (3-panel: aud, vis, diff)
fig, axes = plt.subplots(1, 3, figsize=(16, 4))

# ROI-averaged TFR
aud_roi_tfr = tfr_aud.data[roi_idx].mean(axis=0)  # (freqs, times)
vis_roi_tfr = tfr_vis.data[roi_idx].mean(axis=0)
diff_roi_tfr = tfr_diff.data[roi_idx].mean(axis=0)

vmax = max(abs(aud_roi_tfr).max(), abs(vis_roi_tfr).max()) * 0.8
vmax_diff = abs(diff_roi_tfr).max() * 0.8

for ax, data, title, vm in [
    (axes[0], aud_roi_tfr, "A) Auditory", vmax),
    (axes[1], vis_roi_tfr, "B) Visual", vmax),
    (axes[2], diff_roi_tfr, "C) Difference (Aud − Vis)", vmax_diff),
]:
    im = ax.pcolormesh(
        tfr_aud.times * 1000, freqs, data,
        cmap="RdBu_r", vmin=-vm, vmax=vm, shading="auto"
    )
    ax.axvline(0, color="k", ls="--", alpha=0.7)
    ax.set(xlabel="Time (ms)", ylabel="Frequency (Hz)", title=title)
    ax.set_xlim(-200, 500)
    plt.colorbar(im, ax=ax, label="Power (dB)")

plt.suptitle(f"TFR at frontocentral ROI ({','.join(sorted(set(ch_map[c] for c in roi_eeg)))})", fontsize=11)
plt.tight_layout()
plt.savefig(fig_dir / "F2_tfr_auditory_vs_visual.png", dpi=150, bbox_inches="tight")
plt.savefig(fig_dir / "F2_tfr_auditory_vs_visual.svg", bbox_inches="tight")
plt.close()
print("  Saved F2_tfr_auditory_vs_visual.png/svg", flush=True)

# Figure 3: Band-specific time courses (theta + alpha + beta at ROI)
fig, axes = plt.subplots(1, 3, figsize=(15, 3.5))
for ax, (band_name, (fmin, fmax)) in zip(axes, bands.items()):
    freq_mask = (freqs >= fmin) & (freqs <= fmax)
    aud_band = aud_roi_tfr[freq_mask].mean(axis=0)
    vis_band = vis_roi_tfr[freq_mask].mean(axis=0)
    t = tfr_aud.times * 1000

    ax.plot(t, aud_band, "b-", lw=2, label="Auditory")
    ax.plot(t, vis_band, "r-", lw=2, label="Visual")
    ax.axvline(0, color="k", ls="--", alpha=0.5)
    ax.axhline(0, color="k", alpha=0.3)
    ax.fill_between(t, aud_band, vis_band, alpha=0.15, color="gray")
    ax.set(xlabel="Time (ms)", ylabel="Power (dB)",
           title=f"{band_name.capitalize()} ({fmin}–{fmax} Hz)", xlim=(-200, 500))
    ax.legend(fontsize=8)

plt.suptitle("Band-specific power at frontocentral ROI", fontsize=11)
plt.tight_layout()
plt.savefig(fig_dir / "F3_band_timecourses.png", dpi=150, bbox_inches="tight")
plt.savefig(fig_dir / "F3_band_timecourses.svg", bbox_inches="tight")
plt.close()
print("  Saved F3_band_timecourses.png/svg", flush=True)

print("\n=== eeg-tfr COMPLETE ===", flush=True)
