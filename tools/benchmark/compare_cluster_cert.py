#!/usr/bin/env python
"""Compare two toolboxes' cluster-permutation results, honestly about what is comparable.

Two implementations of a permutation test cannot agree exactly on a p-value: they draw different
random permutations. Reporting a p-value match as a success would be the same category error as
declaring two toolboxes equivalent because their grand means agree.

So the comparison is split:

  DETERMINISTIC -- must match to numerical precision, and a mismatch is a real defect:
      the observed t-map, the cluster count, and each cluster's summed-t statistic.
  STOCHASTIC -- can only be checked against Monte Carlo error:
      the p-values. With n permutations the standard error of an estimated p is
      sqrt(p(1-p)/n); agreement means |p_A - p_B| lies within a few of those.

The scientific question -- would the two toolboxes lead to the same conclusion -- is answered by
the significance decision, not by the digits.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

import numpy as np


def mc_se(p: float, n: int) -> float:
    p = min(max(p, 1.0 / n), 1 - 1.0 / n)
    return float(np.sqrt(p * (1 - p) / n))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", type=Path, required=True)
    ap.add_argument("--b", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    A = json.loads(args.a.read_text(encoding="utf-8-sig"))
    B = json.loads(args.b.read_text(encoding="utf-8-sig"))
    n_perm = min(A["n_permutations"], B["n_permutations"])

    print(f"{A['component']}: {A['toolbox']}  vs  {B['toolbox']}   "
          f"({A['n_subjects']} subjects, {A['n_channels']} channels, {A['n_times']} samples)\n")

    print("DETERMINISTIC — must match")
    tobs = abs(A["t_obs_checksum"] - B["t_obs_checksum"]) / max(abs(A["t_obs_checksum"]), 1e-12)
    tmin = abs(A["t_obs_min"] - B["t_obs_min"]) / max(abs(A["t_obs_min"]), 1e-12)
    print(f"  observed t-map, sum|t|      {A['t_obs_checksum']:14.4f}  {B['t_obs_checksum']:14.4f}"
          f"   rel {tobs:.2e}")
    print(f"  observed t-map, min t       {A['t_obs_min']:14.4f}  {B['t_obs_min']:14.4f}"
          f"   rel {tmin:.2e}")

    ca, cb = A["clusters"], B["clusters"]
    big_a = [c for c in ca if abs(c["t_sum"]) > 1.0]
    big_b = [c for c in cb if abs(c["t_sum"]) > 1.0]
    print(f"  clusters found              {A['n_clusters']:14d}  {B['n_clusters']:14d}"
          f"   (>|t_sum|=1: {len(big_a)} vs {len(big_b)})")

    n_cmp = min(len(big_a), len(big_b))
    worst_rel = 0.0
    for i in range(n_cmp):
        r = abs(big_a[i]["t_sum"] - big_b[i]["t_sum"]) / max(abs(big_a[i]["t_sum"]), 1e-12)
        worst_rel = max(worst_rel, r)
    print(f"  leading cluster t_sum       {big_a[0]['t_sum']:14.4f}  {big_b[0]['t_sum']:14.4f}"
          f"   rel {abs(big_a[0]['t_sum']-big_b[0]['t_sum'])/abs(big_a[0]['t_sum']):.2e}")
    print(f"  leading cluster extent      {big_a[0]['n_points']:14d}  {big_b[0]['n_points']:14d}")

    print("\nSTOCHASTIC — only comparable within Monte Carlo error")
    pa, pb = big_a[0]["p"], big_b[0]["p"]
    se = mc_se(max(pa, pb), n_perm)
    print(f"  leading cluster p           {pa:14.5f}  {pb:14.5f}")
    print(f"  Monte Carlo SE (n={n_perm})   {se:.5f}   |diff| = {abs(pa-pb):.5f}"
          f"  = {abs(pa-pb)/se:.2f} SE")

    print("\nCONCLUSION — the thing a paper actually reports")
    print(f"  significant clusters        {A['n_significant']:14d}  {B['n_significant']:14d}"
          f"   {'SAME' if A['n_significant'] == B['n_significant'] else 'DIFFERENT'}")

    res = {
        "component": A["component"], "toolbox_a": A["toolbox"], "toolbox_b": B["toolbox"],
        "n_subjects": A["n_subjects"], "n_permutations": n_perm,
        "t_obs_checksum_rel_diff": tobs, "t_obs_min_rel_diff": tmin,
        "leading_cluster_tsum_a": big_a[0]["t_sum"], "leading_cluster_tsum_b": big_b[0]["t_sum"],
        "leading_cluster_tsum_rel_diff":
            abs(big_a[0]["t_sum"] - big_b[0]["t_sum"]) / abs(big_a[0]["t_sum"]),
        "leading_cluster_extent_a": big_a[0]["n_points"],
        "leading_cluster_extent_b": big_b[0]["n_points"],
        "leading_cluster_p_a": pa, "leading_cluster_p_b": pb,
        "p_diff_in_monte_carlo_se": abs(pa - pb) / se,
        "n_significant_a": A["n_significant"], "n_significant_b": B["n_significant"],
        "same_conclusion": A["n_significant"] == B["n_significant"],
    }
    if args.out:
        args.out.write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
