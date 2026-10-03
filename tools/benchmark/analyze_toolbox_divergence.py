#!/usr/bin/env python
"""Where does cross-toolbox divergence live?

`compare_eeglab.py` answers *how big* the disagreement between two toolboxes is.
This script answers *where it sits*, which is the part that matters scientifically:

  1. **Bias vs noise** — is the signed mean difference ~0 (random implementation noise)
     or does it equal the grand-mean difference (a systematic offset)?
  2. **Sign flips** — for how many subjects do the two toolboxes disagree on the
     *direction* of the effect? Group statistics survive this; per-subject analyses,
     individual-differences correlations and single-subject classification do not.
  3. **Is divergence concentrated on null subjects?** Compare |Δ| for subjects whose
     certified effect is large vs near zero.

Usage:
    python tools/benchmark/analyze_toolbox_divergence.py \
        --result /tmp/ft_bench/fieldtrip_P3.json --result /tmp/eeglab_bench/eeglab_P3.json
    python tools/benchmark/analyze_toolbox_divergence.py --scan /tmp/ft_bench /tmp/eeglab_bench \
        --out tools/benchmark/TOOLBOX_DIVERGENCE.json
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

import numpy as np
from scipy import stats

from compare_eeglab import COMPONENTS, ROOT, load_certified  # noqa: E402


def analyse(path: Path) -> dict | None:
    d = json.loads(path.read_text(encoding="utf-8-sig"))
    comp = d.get("component")
    if comp not in COMPONENTS:
        return None
    got = {k: float(v) for k, v in d["per_subject"].items()}
    ref = load_certified(comp)
    shared = sorted(set(got) & set(ref))
    if len(shared) < 3:
        return None

    a = np.array([got[s] for s in shared])       # candidate toolbox
    b = np.array([ref[s] for s in shared])       # certified (MNE)
    diff = a - b

    # 1. bias vs noise: |signed mean| / mean|Δ| -> 1.0 means a pure offset, 0 means pure noise
    bias_fraction = float(abs(diff.mean()) / np.abs(diff).mean()) if np.abs(diff).mean() > 0 else 0.0

    # 2. sign flips
    flips = [s for s, x, y in zip(shared, a, b) if np.sign(x) != np.sign(y)]

    # 3. divergence vs effect magnitude — split at the median |certified|
    med = np.median(np.abs(b))
    big, small = np.abs(b) >= med, np.abs(b) < med
    grand = abs(b.mean())

    return {
        "component": comp,
        "toolbox": d.get("toolbox", path.stem),
        "reject_mode": d.get("reject_mode"),
        "source": str(path),
        "n": len(shared),
        "signed_mean_diff_uV": round(float(diff.mean()), 4),
        "mean_abs_diff_uV": round(float(np.abs(diff).mean()), 4),
        "bias_fraction": round(bias_fraction, 3),
        "n_sign_flips": len(flips),
        "sign_flip_subjects": flips,
        "sign_flip_certified_uV": [round(float(ref[s]), 3) for s in flips],
        # is a flipped subject one whose effect was near zero to begin with?
        "median_abs_certified_uV": round(float(med), 3),
        "mean_abs_diff_large_effect_uV": round(float(np.abs(diff)[big].mean()), 4),
        "mean_abs_diff_small_effect_uV": round(float(np.abs(diff)[small].mean()), 4),
        "worst_subject": shared[int(np.argmax(np.abs(diff)))],
        "worst_abs_diff_uV": round(float(np.abs(diff).max()), 4),
        "worst_pct_of_group_effect": round(float(np.abs(diff).max() / grand * 100), 1),
        # does the disagreement threaten an individual-differences analysis?
        "between_toolbox_subject_corr": round(float(stats.pearsonr(a, b)[0]), 4),
    }


def fmt(r: dict) -> str:
    return (
        f"{r['component']:5s} {r['toolbox'][:16]:16s} rej={str(r['reject_mode']):4s} n={r['n']:2d} | "
        f"bias {r['signed_mean_diff_uV']:+.4f} ({r['bias_fraction']*100:3.0f}% of mean|Δ|) | "
        f"sign flips {r['n_sign_flips']}/{r['n']} {r['sign_flip_certified_uV']} | "
        f"mean|Δ| big-effect {r['mean_abs_diff_large_effect_uV']:.4f} vs "
        f"near-null {r['mean_abs_diff_small_effect_uV']:.4f} | "
        f"worst {r['worst_subject']} {r['worst_abs_diff_uV']:.3f} µV "
        f"({r['worst_pct_of_group_effect']:.0f}% of group effect)"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", type=Path, action="append", default=[])
    ap.add_argument("--scan", type=Path, nargs="*", default=[])
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    paths = list(args.result)
    for d in args.scan:
        paths += sorted(d.glob("*.json"))

    rows = []
    for p in paths:
        try:
            r = analyse(p)
        except Exception as e:                          # noqa: BLE001
            print(f"skip {p.name}: {e}")
            continue
        if r:
            rows.append(r)
            print(fmt(r))

    if args.out and rows:
        args.out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
