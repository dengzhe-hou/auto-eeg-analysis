#!/usr/bin/env python
"""Elementwise cluster-test comparison — the evidence a bit-identity claim actually needs.

The committed JSON summaries (checksums, rounded per-cluster summed-t) agree to printed precision,
but the acceptance-contract reviewer was right that summaries cannot support "bit-identical". Two
separate criteria, because they are different kinds of object:

  t-map   : numeric. Exact elementwise equality -> "bit-identical".
            Relative difference <= 1e-6         -> only "equal within tolerance".
  masks   : integer labels. Tolerance is meaningless, and label IDs are arbitrary — two identical
            partitions can be numbered differently. So: exact Boolean membership equality after
            canonical matching, i.e. the set of clusters-as-index-sets must be equal.

Monte-Carlo p-values are deliberately absent here: they are stochastic and excluded from all
exactness language.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

import numpy as np
from scipy.io import loadmat


def partitions(label_img: np.ndarray) -> set[frozenset]:
    out = set()
    for k in np.unique(label_img):
        if k == 0:
            continue
        out.add(frozenset(np.flatnonzero(label_img == k).tolist()))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mne", type=Path, required=True, help=".mat from cluster_cert_mne.py --dump")
    ap.add_argument("--fieldtrip", type=Path, required=True, help=".mat from DUMP=...")
    ap.add_argument("--component", required=True)
    ap.add_argument("--tail", type=int, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    a = loadmat(str(args.mne))
    b = loadmat(str(args.fieldtrip))
    tmap_a = np.asarray(a["tmap"], dtype=float)                    # time x chan
    lab_a = np.asarray(a["labelmap"], dtype=int)
    tmap_b = np.asarray(b["statmap"], dtype=float).T               # chan x time -> time x chan
    lab_b = np.asarray(b["labelmat"], dtype=int).T

    assert tmap_a.shape == tmap_b.shape, f"shape mismatch {tmap_a.shape} vs {tmap_b.shape}"

    bit_identical = bool(np.array_equal(tmap_a, tmap_b))
    max_abs = float(np.max(np.abs(tmap_a - tmap_b)))
    denom = np.maximum(np.abs(tmap_a), 1e-300)
    max_rel = float(np.max(np.abs(tmap_a - tmap_b) / denom))
    within_rtol = bool(max_rel <= 1e-6)

    part_a, part_b = partitions(lab_a), partitions(lab_b)
    partitions_identical = part_a == part_b

    wording = ("bit-identical" if bit_identical and partitions_identical
               else "equal within tolerance" if within_rtol and partitions_identical
               else "NOT exact")

    res = {
        "component": args.component, "tail": args.tail,
        "tmap_shape": list(tmap_a.shape),
        "tmap_bit_identical": bit_identical,
        "tmap_max_abs_diff": max_abs,
        "tmap_max_rel_diff": max_rel,
        "tmap_within_rtol_1e-6": within_rtol,
        "n_clusters_mne": len(part_a), "n_clusters_fieldtrip": len(part_b),
        "partitions_identical": partitions_identical,
        "supported_wording": wording,
    }
    args.out.write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    print(f"{args.component}: tmap max|Δ|={max_abs:.3e} (rel {max_rel:.3e}, "
          f"bit={bit_identical}) | partitions {len(part_a)} vs {len(part_b)} "
          f"identical={partitions_identical} -> wording: {wording}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
