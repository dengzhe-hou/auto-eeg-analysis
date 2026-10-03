"""eeg-stats case study: cluster permutation on single-subject trial-level data."""
import mne, json, numpy as np
from pathlib import Path
from scipy import stats as scipy_stats

mne.set_log_level("WARNING")
PROJECT = Path("projects/mne-sample-audvis")
SEED = 42
np.random.seed(SEED)

print("=== eeg-stats ===", flush=True)

epochs = mne.read_epochs(PROJECT / "epoch-stage/sub-01/sub-01-epo.fif", preload=True)
aud = mne.concatenate_epochs([epochs["auditory/left"], epochs["auditory/right"]])
vis = mne.concatenate_epochs([epochs["visual/left"], epochs["visual/right"]])

n_min = min(len(aud), len(vis))
X_diff = aud.get_data()[:n_min] - vis.get_data()[:n_min]
print(f"  {n_min} paired trials, {X_diff.shape[1]} ch, {X_diff.shape[2]} times", flush=True)

# Focus on N100 window
tmin_s, tmax_s = 0.05, 0.20
tmask = (aud.times >= tmin_s) & (aud.times <= tmax_s)
X = X_diff[:, :, tmask].transpose(0, 2, 1)  # (trials, times, ch)
tw = aud.times[tmask]
print(f"  Window: {tmin_s}-{tmax_s}s, shape {X.shape}", flush=True)

adj, _ = mne.channels.find_ch_adjacency(aud.info, ch_type="eeg")
df = X.shape[0] - 1
t_thr = scipy_stats.t.ppf(1 - 0.025, df)
print(f"  t-threshold: {t_thr:.3f}, df={df}", flush=True)

print("  Running cluster perm (100 perms)...", flush=True)
t_obs, clusters, cluster_p, H0 = mne.stats.spatio_temporal_cluster_1samp_test(
    X, n_permutations=100, threshold=t_thr, tail=0,
    seed=SEED, adjacency=adj, out_type="mask", n_jobs=1, verbose=False,
)
print(f"  {len(clusters)} clusters found", flush=True)

sig = [(i, float(p)) for i, p in enumerate(cluster_p) if p < 0.05]
print(f"  Significant: {len(sig)}", flush=True)

for i, p in sig:
    mask = clusters[i]
    tidx, cidx = np.where(mask)
    chs = sorted(set(aud.ch_names[c] for c in cidx))
    t_sum = float(t_obs[mask].sum())
    print(f"  Cluster {i}: p={p:.4f}, t_sum={t_sum:.1f}, "
          f"{tw[tidx.min()]*1000:.0f}-{tw[tidx.max()]*1000:.0f}ms, "
          f"{len(chs)} channels: {chs[:5]}", flush=True)

# Effect size
cohens_d = None
if sig:
    best_mask = clusters[sig[0][0]]
    cd = X[:, best_mask]
    cohens_d = float(cd.mean() / cd.std()) if cd.std() > 0 else 0
    print(f"  Cohen's d: {cohens_d:.3f}", flush=True)

# Save
sdir = PROJECT / "stats-stage"
sdir.mkdir(parents=True, exist_ok=True)

result = {
    "claim_id": "C1",
    "claim": "Auditory > Visual N100",
    "test": "spatio_temporal_cluster_1samp_test (trial-level)",
    "n_permutations": 100,
    "threshold": float(t_thr),
    "seed": SEED,
    "window": [tmin_s, tmax_s],
    "n_trials": int(n_min),
    "n_clusters": len(clusters),
    "significant": [
        {"id": int(i), "p": float(p),
         "t_sum": float(t_obs[clusters[i]].sum()),
         "time_ms": [float(tw[np.where(clusters[i])[0].min()]*1000),
                     float(tw[np.where(clusters[i])[0].max()]*1000)],
         "channels": sorted(set(aud.ch_names[c] for c in np.where(clusters[i])[1]))}
        for i, p in sig
    ],
    "cohens_d": cohens_d,
    "verdict": "supports" if sig else "does_not_support",
}
json.dump(result, open(sdir / "C1_cluster_perm.json", "w", encoding="utf-8"), indent=2)
np.savez(sdir / "C1_arrays.npz", t_obs=t_obs, cluster_p=np.array(cluster_p), H0=H0)

print(f"\n  Verdict: {result['verdict']}", flush=True)
print("=== DONE ===", flush=True)
