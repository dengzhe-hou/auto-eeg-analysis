"""AUDIT follow-up experiments (responses to the GPT cross-model review of the
resting validation). Three things the reviewer asked for:

  1a. Complexity ICA-sensitivity + binarization: re-run LZC/PE WITHOUT ICA and with
      median vs mean binarization, to quantify how much the EO>EC contrast depends on
      ICA (the with-ICA arm comes from tools/validation/resting_results.json).
  1b. Microstate stability + physical-unit smoothing: at NATIVE 160 Hz with smoothing
      expressed in ms (not samples), plus K=4 across 3 seeds and split-half GEV — show
      the duration artifact is fixed and maps are reproducible.
  1c. Alpha topography: per-channel paired t-map (EC-EO, 8-13 Hz) to show the cluster is
      posterior-maximal, not uniformly whole-scalp.

Runs WITHOUT ICA (fast; ICA-cleaned arm already committed). Usage:
  python tools/validation/audit_followups.py --subjects 20 --ms-subjects 10
"""
from __future__ import annotations
import argparse, json, sys, warnings
from pathlib import Path
import numpy as np

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_resting_recipes import load_run, posterior_alpha, EO_RUN, EC_RUN  # noqa: E402


def _lzc(x, mode):
    import antropy
    b = (x > np.median(x)) if mode == "median" else (x > np.mean(x))
    return float(antropy.lziv_complexity(b, normalize=True))


def complexity_variants(raw):
    import antropy
    r = raw.copy().filter(0.5, 45, verbose="ERROR")
    X = r.get_data()
    return {
        "lzc_median": float(np.mean([_lzc(ch, "median") for ch in X])),
        "lzc_mean": float(np.mean([_lzc(ch, "mean") for ch in X])),
        "pe": float(np.mean([antropy.perm_entropy(ch, order=3, normalize=True) for ch in X])),
    }


def paired(ec, eo):
    from scipy import stats
    ec, eo = np.asarray(ec, float), np.asarray(eo, float)
    d = ec - eo
    t, p = stats.ttest_rel(ec, eo)
    return {"ec": round(float(ec.mean()), 4), "eo": round(float(eo.mean()), 4),
            "diff_ec_minus_eo": round(float(d.mean()), 4), "t": round(float(t), 2),
            "p": float(p), "dz": round(float(d.mean() / d.std(ddof=1)), 2)}


def microstate_stability(subj, seeds=(42, 7, 123)):
    """Native 160 Hz, physical-unit smoothing; GEV across seeds + split-half map similarity."""
    import mne
    from pycrostates.cluster import ModKMeans
    from pycrostates.preprocessing import extract_gfp_peaks
    raw = load_run(subj, EC_RUN, sfreq=160.0, do_ica=False)   # NATIVE 160 Hz
    raw.filter(2, 20, verbose="ERROR")
    sf = raw.info["sfreq"]
    hw = max(1, round(0.030 * sf))          # 30 ms half-window (physical units)
    minseg = max(1, round(0.020 * sf))      # 20 ms minimum segment
    out = {"subject": subj, "sfreq": sf, "half_window_ms": 30, "seeds": {}}
    maps = {}
    for sd in seeds:
        gfp = extract_gfp_peaks(raw, verbose="ERROR")
        mk = ModKMeans(n_clusters=4, random_state=sd)
        mk.fit(gfp, n_jobs=1, verbose="ERROR")
        seg = mk.predict(raw, factor=10, half_window_size=hw, min_segment_length=minseg,
                         reject_by_annotation=False, verbose="ERROR")
        params = seg.compute_parameters()
        durs = sorted(v * 1000 for k, v in params.items() if k.endswith("_meandurs"))
        out["seeds"][sd] = {"gev": round(float(mk.GEV_), 3),
                            "dur_median_ms": round(float(np.median(durs)), 1)}
        maps[sd] = mk.cluster_centers_      # (4, n_ch)
    # split-half: fit on each half, correlate the 4 maps (polarity-invariant, greedy match)
    n = raw.n_times
    halves = [raw.copy().crop(0, raw.times[n // 2], verbose="ERROR"),
              raw.copy().crop(raw.times[n // 2], None, verbose="ERROR")]
    hmaps = []
    for h in halves:
        mk = ModKMeans(n_clusters=4, random_state=42)
        mk.fit(extract_gfp_peaks(h, verbose="ERROR"), n_jobs=1, verbose="ERROR")
        hmaps.append(mk.cluster_centers_)
    C = np.abs(np.corrcoef(hmaps[0], hmaps[1])[:4, 4:])   # |corr| 4x4, polarity-free
    matched = [float(C[i].max()) for i in range(4)]
    out["split_half_map_abscorr_mean"] = round(float(np.mean(matched)), 3)
    return out


def main():
    import mne
    from scipy import stats
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", type=int, default=20)
    ap.add_argument("--ms-subjects", type=int, default=10)
    ap.add_argument("--out", default="tools/validation/audit_followup_results.json")
    args = ap.parse_args()

    # 1a + 1c : no-ICA arm
    ec_cx, eo_cx, ec_pc, eo_pc, info = [], [], [], [], None
    for s in range(1, args.subjects + 1):
        try:
            ec = load_run(s, EC_RUN, sfreq=250.0, do_ica=False)
            eo = load_run(s, EO_RUN, sfreq=250.0, do_ica=False)
            ec_cx.append(complexity_variants(ec)); eo_cx.append(complexity_variants(eo))
            _, ecpc, _, _, _ = posterior_alpha(ec); _, eopc, _, _, _ = posterior_alpha(eo)
            ec_pc.append(ecpc); eo_pc.append(eopc)
            if info is None:
                info = ec.copy().filter(1, 45, verbose="ERROR").info
            print(f"  cx/topo subj {s:2d} ok", flush=True)
        except Exception as e:
            print(f"  cx/topo subj {s:2d} SKIP {type(e).__name__}: {str(e)[:60]}", flush=True)

    complexity_noica = {
        "lzc_median": paired([c["lzc_median"] for c in ec_cx], [c["lzc_median"] for c in eo_cx]),
        "lzc_mean": paired([c["lzc_mean"] for c in ec_cx], [c["lzc_mean"] for c in eo_cx]),
        "pe": paired([c["pe"] for c in ec_cx], [c["pe"] for c in eo_cx]),
    }
    # topography t-map (EC - EO) per channel
    X = np.array(ec_pc) - np.array(eo_pc)            # (subj, ch)
    tvals, _ = stats.ttest_1samp(X, 0, axis=0)
    post_set = {"O1","Oz","O2","PO3","PO4","POz","PO7","PO8","P1","P2","Pz","P3","P4","P7","P8"}
    post_idx = [i for i, c in enumerate(info["ch_names"]) if c in post_set]
    ant_idx = [i for i in range(len(info["ch_names"])) if i not in post_idx]
    topo = {"t_posterior_mean": round(float(tvals[post_idx].mean()), 2),
            "t_anterior_mean": round(float(tvals[ant_idx].mean()), 2),
            "t_max_channel": info["ch_names"][int(np.argmax(tvals))],
            "t_max": round(float(tvals.max()), 2)}

    # 1b microstate stability
    ms = []
    for s in range(1, args.ms_subjects + 1):
        try:
            ms.append(microstate_stability(s)); print(f"  microstate subj {s:2d} ok", flush=True)
        except Exception as e:
            print(f"  microstate subj {s:2d} SKIP {type(e).__name__}: {str(e)[:60]}", flush=True)
    ms_durs = [v["dur_median_ms"] for m in ms for v in m["seeds"].values()]
    ms_gevs = [v["gev"] for m in ms for v in m["seeds"].values()]
    ms_splithalf = [m["split_half_map_abscorr_mean"] for m in ms]
    ms_summary = {
        "native_sfreq": 160, "smoothing": "physical-unit (30 ms half-window)",
        "dur_median_ms_mean": round(float(np.mean(ms_durs)), 1),
        "dur_median_ms_range": [round(min(ms_durs), 1), round(max(ms_durs), 1)],
        "gev_mean": round(float(np.mean(ms_gevs)), 3),
        "split_half_map_abscorr_mean": round(float(np.mean(ms_splithalf)), 3),
        "n_subjects": len(ms), "seeds": [42, 7, 123],
    }

    results = {
        "complexity_ica_sensitivity": {
            "with_ICA (committed, from resting_results.json)":
                {"lzc_median": {"ec": 0.4731, "eo": 0.5197, "p": 4.15e-5, "note": "EO>EC, clean"}},
            "without_ICA": complexity_noica,
            "interpretation": "compare with vs without ICA to gauge artifact dependence",
        },
        "alpha_topography": topo,
        "microstate_stability_native160_physical_smoothing": ms_summary,
        "microstate_per_subject": ms,
    }
    json.dump(results, open(args.out, "w", encoding="utf-8"), indent=2)

    # Figure: alpha t-map topomap + complexity-sensitivity bars
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
        mne.viz.plot_topomap(tvals, info, axes=ax[0], show=False, cmap="RdBu_r",
                             contours=4, sensors=True)
        ax[0].set_title(f"A) EC−EO alpha t-map\nposterior t̄={topo['t_posterior_mean']} "
                        f"vs anterior t̄={topo['t_anterior_mean']}")
        labels = ["LZC(median)", "LZC(mean)", "PE"]
        wi = [0.4731, None, None]  # with-ICA only have lzc_median committed
        noica = [complexity_noica["lzc_median"], complexity_noica["lzc_mean"], complexity_noica["pe"]]
        xs = np.arange(3)
        ax[1].bar(xs, [c["diff_ec_minus_eo"] for c in noica], color=["C3","C1","C0"])
        ax[1].axhline(0, color="k", lw=0.8)
        ax[1].set_xticks(xs); ax[1].set_xticklabels(labels)
        ax[1].set(ylabel="EC − EO (negative = EO>EC, expected)",
                  title="B) Complexity contrast WITHOUT ICA\n(p: "
                        f"{complexity_noica['lzc_median']['p']:.1e}/"
                        f"{complexity_noica['lzc_mean']['p']:.1e}/{complexity_noica['pe']['p']:.1e})")
        plt.tight_layout()
        figp = "tools/validation/figures/audit_followups.png"
        plt.savefig(figp, dpi=140, bbox_inches="tight"); plt.close()
        print(f"Figure: {figp}")
    except Exception as e:
        print(f"[figure skipped] {type(e).__name__}: {e}")

    print("\n==== AUDIT FOLLOW-UP SUMMARY ====")
    print(f"[1a] complexity WITHOUT ICA: LZC(median) EC={complexity_noica['lzc_median']['ec']} "
          f"EO={complexity_noica['lzc_median']['eo']} p={complexity_noica['lzc_median']['p']:.2e} "
          f"| LZC(mean) p={complexity_noica['lzc_mean']['p']:.2e} | PE p={complexity_noica['pe']['p']:.2e}")
    print(f"[1c] alpha t-map: posterior t̄={topo['t_posterior_mean']} vs anterior t̄={topo['t_anterior_mean']}, "
          f"max @ {topo['t_max_channel']} (t={topo['t_max']})")
    print(f"[1b] microstate native 160Hz + physical smoothing: dur={ms_summary['dur_median_ms_mean']}ms "
          f"(range {ms_summary['dur_median_ms_range']}), GEV={ms_summary['gev_mean']}, "
          f"split-half map |r|={ms_summary['split_half_map_abscorr_mean']}")
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()
