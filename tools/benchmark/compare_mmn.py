"""Digit-by-digit agreement: AEA mmn-oddball recipe vs MNE-BIDS-Pipeline (gold standard).

Joins the two per-subject MMN tables on the common subjects and reports how closely the
two independent implementations agree when handed the SAME data and the SAME analysis
choices. Differences that survive are pure implementation discrepancies (event handling,
filter/resample internals, average-reference + baseline order, epoch rejection).

  python tools/benchmark/compare_mmn.py
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
from scipy import stats as sstats


def lin_ccc(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    mx, my = x.mean(), y.mean()
    sx, sy = x.var(), y.var()
    cov = ((x - mx) * (y - my)).mean()
    return float(2 * cov / (sx + sy + (mx - my) ** 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aea", default="tools/validation/mmn_group_results.json")
    ap.add_argument("--gold", default="tools/benchmark/bidspipe_mmn_results.json")
    ap.add_argument("--tol", type=float, default=0.5, help="per-subject |delta| tolerance (uV)")
    ap.add_argument("--key", default="mmn_uV", help="per-subject metric key (e.g. p3_uV)")
    ap.add_argument("--label", default="AEA mmn-oddball recipe vs MNE-BIDS-Pipeline 1.10.1")
    ap.add_argument("--out", default="tools/benchmark/MMN_BENCHMARK_RESULT.json")
    ap.add_argument("--figure", default="tools/benchmark/figures/mmn_benchmark.png")
    args = ap.parse_args()
    K = args.key

    aea = {p["subject"]: p for p in json.load(open(args.aea, encoding="utf-8-sig"))["per_subject"]}
    gold = {p["subject"]: p for p in json.load(open(args.gold, encoding="utf-8-sig"))["per_subject"]}
    subs = sorted(set(aea) & set(gold))
    if not subs:
        raise SystemExit("no common subjects between AEA and gold results")

    rows, a, g = [], [], []
    for s in subs:
        av, gv = aea[s][K], gold[s][K]
        a.append(av); g.append(gv)
        rows.append({"subject": s, "aea_uV": av, "gold_uV": gv,
                     "delta_uV": round(av - gv, 3),
                     "aea_ndev": aea[s].get("n_dev"), "gold_ndev": gold[s].get("n_dev")})
    a, g = np.array(a), np.array(g)
    d = a - g

    pear = sstats.pearsonr(a, g)
    spear = sstats.spearmanr(a, g)
    bias, sd = float(d.mean()), float(d.std(ddof=1))
    loa = (round(bias - 1.96 * sd, 3), round(bias + 1.96 * sd, 3))
    within = int(np.sum(np.abs(d) <= args.tol))

    summary = {
        "comparison": args.label,
        "metric_key": K,
        "harmonized": True,
        "n_common_subjects": len(subs),
        "aea_grand_mean_uV": round(float(a.mean()), 3),
        "gold_grand_mean_uV": round(float(g.mean()), 3),
        "group_mean_delta_uV": round(float(a.mean() - g.mean()), 3),
        "per_subject_delta": {
            "max_abs_uV": round(float(np.abs(d).max()), 3),
            "mean_abs_uV": round(float(np.abs(d).mean()), 3),
            "median_abs_uV": round(float(np.median(np.abs(d))), 3),
            "rmse_uV": round(float(np.sqrt((d ** 2).mean())), 3),
        },
        "agreement": {
            "pearson_r": round(float(pear[0]), 4), "pearson_p": float(pear[1]),
            "spearman_rho": round(float(spear[0]), 4),
            "lin_ccc": round(lin_ccc(a, g), 4),
            "bland_altman_bias_uV": round(bias, 3),
            "bland_altman_loa_uV": loa,
            f"n_within_{args.tol}uV": within,
            f"frac_within_{args.tol}uV": round(within / len(subs), 3),
        },
        "tolerance_uV": args.tol,
        "per_subject": rows,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(summary, open(args.out, "w", encoding="utf-8"), indent=2)

    # --- console table ---
    print(f"\n  {'subject':9} {'AEA':>8} {'gold':>8} {'Δ':>7}   {'AEA_ndev':>8} {'gold_ndev':>9}")
    for r in rows:
        print(f"  {r['subject']:9} {r['aea_uV']:+8.3f} {r['gold_uV']:+8.3f} {r['delta_uV']:+7.3f}"
              f"   {str(r['aea_ndev']):>8} {str(r['gold_ndev']):>9}")
    s = summary
    print(f"\n  N={s['n_common_subjects']}  "
          f"AEA grand-mean={s['aea_grand_mean_uV']:+.3f}  gold={s['gold_grand_mean_uV']:+.3f}  "
          f"Δgroup={s['group_mean_delta_uV']:+.3f} uV")
    print(f"  per-subject |Δ|: max={s['per_subject_delta']['max_abs_uV']}  "
          f"mean={s['per_subject_delta']['mean_abs_uV']}  rmse={s['per_subject_delta']['rmse_uV']} uV")
    print(f"  agreement: r={s['agreement']['pearson_r']}  CCC={s['agreement']['lin_ccc']}  "
          f"BA-bias={s['agreement']['bland_altman_bias_uV']}  LoA={s['agreement']['bland_altman_loa_uV']}  "
          f"within±{args.tol}: {s['agreement'][f'n_within_{args.tol}uV']}/{s['n_common_subjects']}")

    # --- figure: scatter + Bland-Altman ---
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(11, 4.4))
        lo = min(a.min(), g.min()) - 0.3; hi = max(a.max(), g.max()) + 0.3
        ax[0].plot([lo, hi], [lo, hi], "k--", lw=1, label="identity")
        ax[0].scatter(g, a, c="C3", zorder=3)
        for r in rows:
            ax[0].annotate(r["subject"].replace("sub-", ""), (r["gold_uV"], r["aea_uV"]),
                           fontsize=7, xytext=(2, 2), textcoords="offset points")
        ax[0].set(xlabel="MNE-BIDS-Pipeline (µV)", ylabel="AEA recipe (µV)",
                  title=f"A) Per-subject agreement\nr={pear[0]:.3f}, CCC={lin_ccc(a,g):.3f}, N={len(subs)}")
        ax[0].legend(fontsize=8); ax[0].set_aspect("equal", "box")
        m = (a + g) / 2
        ax[1].axhline(bias, color="C0", lw=1.5, label=f"bias={bias:+.3f}")
        ax[1].axhline(loa[0], color="grey", ls="--", lw=1, label=f"LoA={loa}")
        ax[1].axhline(loa[1], color="grey", ls="--", lw=1)
        ax[1].axhline(0, color="k", lw=0.6)
        ax[1].scatter(m, d, c="C3", zorder=3)
        ax[1].set(xlabel="mean of two methods (µV)", ylabel="AEA − gold (µV)",
                  title="B) Bland–Altman")
        ax[1].legend(fontsize=8)
        plt.tight_layout()
        figp = args.figure
        Path(figp).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(figp, dpi=140, bbox_inches="tight"); plt.close()
        print(f"  figure: {figp}")
    except Exception as e:
        print(f"  [figure skipped] {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
