#!/usr/bin/env python
"""MNE side of the cluster-permutation certification.

What can and cannot be compared across two permutation implementations:

  DETERMINISTIC, must match to numerical precision
    - the observed t-map
    - which samples exceed the cluster-forming threshold
    - the resulting clusters and their summed-t statistics

  STOCHASTIC, can only agree within Monte Carlo error
    - the p-values. Two implementations draw different random permutations even from the same
      seed, so identical p-values are neither expected nor evidence of anything. With n
      permutations the standard error on a p near p0 is sqrt(p0*(1-p0)/n); the comparison has to
      be made against that, not against zero.

Reporting a p-value match as if it were exact would be the same category error as claiming two
toolboxes agree because their grand means do.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

import numpy as np
from scipy import stats as sstats
from scipy.io import loadmat


def main() -> int:
    import mne
    mne.set_log_level("ERROR")
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--n-permutations", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--tail", type=int, choices=(-1, 1), default=-1,
                    help="predicted direction: P3b positive (+1); MMN/N170/ERN/N400 negative (-1)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--dump", type=Path,
                    help="also write the full observed t-map and integer cluster-label map to this "
                         ".mat, for elementwise cross-toolbox comparison (contract B5: summaries "
                         "cannot support a bit-identity claim)")
    ap.add_argument("--tmin", type=float, help="crop to times >= tmin (s); pass the exact sample time")
    ap.add_argument("--tmax", type=float, help="crop to times <= tmax (s); pass the exact sample time")
    ap.add_argument("--threshold", choices=("two-sided-0.975", "auto"), default="two-sided-0.975",
                    help="'two-sided-0.975': the original certification's explicit t.ppf(0.975, df) "
                         "(an author-side choice, NOT MNE's default); 'auto': threshold=None, i.e. "
                         "MNE's own one-sided default t.ppf(0.95, df) for tail != 0 -- the convention "
                         "the shipped validation scripts actually use")
    args = ap.parse_args()

    m = loadmat(str(args.input), simplify_cells=True)
    if args.tmin is not None or args.tmax is not None:
        t = np.asarray(m["times"], dtype=float).ravel()
        keep = ((t >= (args.tmin if args.tmin is not None else -np.inf))
                & (t <= (args.tmax if args.tmax is not None else np.inf)))
        m["X"] = np.asarray(m["X"])[:, keep, :]          # X is chan x time x subj in the .mat
        m["times"] = t[keep]
    X = np.transpose(m["X"], (2, 1, 0))          # -> subject x time x channel (MNE's layout)
    A = np.asarray(m["adjacency"])
    comp = str(m["component"])
    n_sub, n_time, n_chan = X.shape

    from scipy.sparse import csr_matrix
    adjacency = csr_matrix(A)

    # Threshold pinned explicitly rather than left to the default: it is one of the two things
    # the two toolboxes must share for the comparison to be about the algorithm.
    df = n_sub - 1
    if args.threshold == "auto":
        signed = None                                  # MNE default: one-sided t.ppf(0.95, df)
        effective_threshold = args.tail * float(sstats.t.ppf(0.95, df))
    else:
        thresh = sstats.t.ppf(1 - 0.025, df)          # two-tailed-style alpha .05 (author-side choice)
        signed = thresh * args.tail
        effective_threshold = float(signed)

    T_obs, clusters, cluster_pv, H0 = mne.stats.spatio_temporal_cluster_1samp_test(
        X, adjacency=adjacency, n_permutations=args.n_permutations,
        threshold=signed, tail=args.tail, seed=args.seed, n_jobs=1, out_type="mask", verbose=False,
    )

    tsums = [float(T_obs[c].sum()) for c in clusters]
    # leading cluster first: most negative for tail=-1, largest for tail=+1
    order = np.argsort(tsums) if args.tail == -1 else np.argsort(tsums)[::-1]
    rows = [{
        "rank": int(i),
        "t_sum": round(tsums[j], 4),
        "n_points": int(clusters[j].sum()),
        "p": float(cluster_pv[j]),
        "significant": bool(cluster_pv[j] < 0.05),
    } for i, j in enumerate(order)]

    if args.dump:
        from scipy.io import savemat
        labelmap = np.zeros(T_obs.shape, dtype=np.int32)
        for k, c in enumerate(clusters, 1):
            labelmap[c] = k
        savemat(str(args.dump), {"tmap": T_obs, "labelmap": labelmap})

    res = {
        "toolbox": "MNE-Python",
        "threshold_mode": args.threshold, "threshold_value": effective_threshold,
        "window_s": [args.tmin, args.tmax], "n_times_used": int(m["X"].shape[1]),
        "component": comp,
        "n_subjects": n_sub, "n_channels": n_chan, "n_times": n_time,
        "threshold_t": round(effective_threshold, 6), "df": df, "tail": args.tail,
        "n_permutations": args.n_permutations, "seed": args.seed,
        "n_clusters": len(clusters),
        "n_significant": int(sum(r["significant"] for r in rows)),
        "clusters": rows,
        "t_obs_checksum": round(float(np.abs(T_obs).sum()), 6),
        "t_obs_min": round(float(T_obs.min()), 6),
    }
    args.out.write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    print(f"{comp}: {res['n_clusters']} clusters, {res['n_significant']} significant")
    for r in rows[:4]:
        print(f"   t_sum={r['t_sum']:12.3f}  n={r['n_points']:5d}  p={r['p']:.4f}"
              f"{'  *' if r['significant'] else ''}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
