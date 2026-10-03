"""Server-side end-to-end validation of the 3 resting/complexity recipes on a real
public dataset (PhysioNet eegbci eyes-open R01 / eyes-closed R02, 64ch @ 160 Hz).

One group EC-vs-EO analysis does double duty:
  * resting-spectral-connectivity sanity: eyes-closed > eyes-open posterior alpha
  * complexity-anesthesia sanity:        eyes-open > eyes-closed complexity (LZC/PE)
  * resting-microstate sanity:           ~4 maps, ~70% GEV, durations 70-120 ms (EC)
and gives an N>1 second-level (across-subject) cluster test, retiring the "all N=1"
limitation.

Usage:
  python tools/validation/validate_resting_recipes.py --subjects 20 --out tools/validation/resting_results.json
"""
from __future__ import annotations
import argparse, json, warnings
import numpy as np

warnings.filterwarnings("ignore")

POSTERIOR = ["O1", "Oz", "O2", "PO3", "PO4", "POz", "PO7", "PO8",
             "P1", "P2", "Pz", "P3", "P4", "P7", "P8"]
EO_RUN, EC_RUN = 1, 2   # eegbci: R01 = baseline eyes-open, R02 = baseline eyes-closed


def load_run(subj: int, run: int, sfreq: float = 250.0, do_ica: bool = True):
    """Load an eegbci run, standardize montage, resample to >=min_sfreq, avg-ref, and
    (recipe-faithful) ICA-clean eye/muscle/heart components.

    eegbci is natively 160 Hz, BELOW the recipes' min_sfreq=250; we resample up so the
    sample-based microstate smoothing params behave as designed and the recipe's data
    gate is met. ICA+ICLabel is what the complexity recipe needs (residual EMG inflates
    LZC), so it is on by default.
    """
    import mne
    from mne.datasets import eegbci
    fn = eegbci.load_data(subjects=subj, runs=[run], update_path=False, verbose="ERROR")[0]
    raw = mne.io.read_raw_edf(fn, preload=True, verbose="ERROR")
    eegbci.standardize(raw)
    raw.set_montage("standard_1005", on_missing="ignore", verbose="ERROR")
    if sfreq and abs(raw.info["sfreq"] - sfreq) > 1:
        raw.resample(sfreq, verbose="ERROR")
    raw.set_eeg_reference("average", projection=False, verbose="ERROR")
    if do_ica:
        from mne_icalabel import label_components
        raw_hp = raw.copy().filter(l_freq=1.0, h_freq=None, verbose="ERROR")
        ica = mne.preprocessing.ICA(n_components=15, method="infomax", random_state=42,
                                    max_iter="auto", fit_params=dict(extended=True))
        ica.fit(raw_hp, verbose="ERROR")
        labels = label_components(raw_hp, ica, method="iclabel")["labels"]
        ica.exclude = [i for i, l in enumerate(labels)
                       if l in {"eye blink", "muscle artifact", "heart beat"}]
        ica.apply(raw, verbose="ERROR")
    return raw


def posterior_alpha(raw):
    """Return (posterior alpha power, per-channel alpha power, ch_names) — spectral recipe band 1-45."""
    import mne
    r = raw.copy().filter(1, 45, verbose="ERROR")
    ep = mne.make_fixed_length_epochs(r, duration=2.0, overlap=0.0, preload=True, verbose="ERROR")
    psd = ep.compute_psd(method="welch", fmin=1, fmax=45,
                         n_fft=int(r.info["sfreq"] * 2), verbose="ERROR")
    data, freqs = psd.get_data(return_freqs=True)        # (epochs, ch, freqs)
    data = data.mean(0)                                  # (ch, freqs)
    amask = (freqs >= 8) & (freqs <= 13)
    alpha_perch = data[:, amask].mean(1)                 # (ch,)
    post_idx = [r.ch_names.index(c) for c in POSTERIOR if c in r.ch_names]
    alpha_post = float(alpha_perch[post_idx].mean())
    post_curve = data[post_idx].mean(0)                  # posterior-averaged PSD curve
    return alpha_post, alpha_perch, r.ch_names, freqs, post_curve


def complexity(raw):
    """Channel-averaged LZC / permutation-entropy / spectral-entropy — complexity recipe band 0.5-45."""
    import antropy
    r = raw.copy().filter(0.5, 45, verbose="ERROR")
    x = r.get_data()                                     # (ch, times)
    lzc = float(np.mean([antropy.lziv_complexity(ch > np.median(ch), normalize=True) for ch in x]))
    pe = float(np.mean([antropy.perm_entropy(ch, order=3, normalize=True) for ch in x]))
    se = float(np.mean([antropy.spectral_entropy(ch, sf=r.info["sfreq"], method="welch", normalize=True) for ch in x]))
    return {"lzc": lzc, "perm_entropy": pe, "spectral_entropy": se}


def microstate(raw):
    """K=4 modified k-means GEV + durations on eyes-closed — microstate recipe band 2-20."""
    from pycrostates.cluster import ModKMeans
    from pycrostates.preprocessing import extract_gfp_peaks
    r = raw.copy().filter(2, 20, verbose="ERROR")
    gfp = extract_gfp_peaks(r, verbose="ERROR")
    ModK = ModKMeans(n_clusters=4, random_state=42)
    ModK.fit(gfp, n_jobs=1, verbose="ERROR")
    seg = ModK.predict(r, factor=10, half_window_size=8, min_segment_length=5,
                       reject_by_annotation=False, verbose="ERROR")
    params = seg.compute_parameters()
    durations_ms = sorted(float(v * 1000) for k, v in params.items() if k.endswith("_meandurs"))
    return {"gev_total": float(ModK.GEV_), "durations_ms": durations_ms}


def paired(ec, eo):
    from scipy import stats
    ec, eo = np.asarray(ec, float), np.asarray(eo, float)
    d = ec - eo
    t, p = stats.ttest_rel(ec, eo)
    dz = float(d.mean() / d.std(ddof=1)) if d.std(ddof=1) > 0 else 0.0
    return {"ec_mean": float(ec.mean()), "eo_mean": float(eo.mean()),
            "diff_mean": float(d.mean()), "t": float(t), "p": float(p),
            "cohens_dz": dz, "n": int(len(ec))}


def cluster_alpha(ec_perch, eo_perch, info):
    """Second-level spatial cluster-permutation across channels (EC - EO posterior alpha)."""
    import mne
    X = np.asarray(ec_perch) - np.asarray(eo_perch)      # (subjects, ch)
    adj, _ = mne.channels.find_ch_adjacency(info, ch_type="eeg")
    t_obs, clusters, cl_p, _ = mne.stats.spatio_temporal_cluster_1samp_test(
        X[:, :, np.newaxis], n_permutations=5000, adjacency=adj, seed=42,
        tail=0, out_type="mask", n_jobs=1, verbose=False)
    sig = [(int(i), float(p)) for i, p in enumerate(cl_p) if p < 0.05]
    return {"n_clusters": int(len(clusters)), "n_significant": len(sig),
            "min_p": float(min(cl_p)) if len(cl_p) else 1.0,
            "max_cluster_size": int(max((int(c.sum()) for c in clusters), default=0)),
            "significant": sig}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", type=int, default=20)
    ap.add_argument("--out", default="tools/validation/resting_results.json")
    ap.add_argument("--sfreq", type=float, default=250.0)
    ap.add_argument("--no-ica", dest="ica", action="store_false")
    args = ap.parse_args()

    per = []
    ec_alpha_perch, eo_alpha_perch = [], []
    ec_curves, eo_curves, freqs_ref = [], [], None
    info_ref = None
    for s in range(1, args.subjects + 1):
        try:
            ec_raw = load_run(s, EC_RUN, sfreq=args.sfreq, do_ica=args.ica)
            eo_raw = load_run(s, EO_RUN, sfreq=args.sfreq, do_ica=args.ica)
            ec_a, ec_pc, chn, freqs_ref, ec_curve = posterior_alpha(ec_raw)
            eo_a, eo_pc, _, _, eo_curve = posterior_alpha(eo_raw)
            ec_c, eo_c = complexity(ec_raw), complexity(eo_raw)
            ms = microstate(ec_raw)
            per.append({"subject": s, "ec_alpha": ec_a, "eo_alpha": eo_a,
                        "ec_complexity": ec_c, "eo_complexity": eo_c, "microstate_ec": ms})
            ec_alpha_perch.append(ec_pc); eo_alpha_perch.append(eo_pc)
            ec_curves.append(ec_curve); eo_curves.append(eo_curve)
            if info_ref is None:
                info_ref = ec_raw.copy().filter(1, 45, verbose="ERROR").info
            print(f"  subj {s:3d}: EC alpha={ec_a:.2e} EO alpha={eo_a:.2e} | "
                  f"EC LZC={ec_c['lzc']:.3f} EO LZC={eo_c['lzc']:.3f} | GEV={ms['gev_total']:.3f}", flush=True)
        except Exception as e:
            print(f"  subj {s:3d}: SKIP ({type(e).__name__}: {str(e)[:70]})", flush=True)

    # --- Group stats ---
    # paired(ec, eo) reports diff = ec - eo, so the inner ec_mean/eo_mean are always
    # the eyes-closed / eyes-open means. Spectral expects diff>0 (EC>EO alpha);
    # complexity expects diff<0 (EO>EC complexity).
    alpha = paired([p["ec_alpha"] for p in per], [p["eo_alpha"] for p in per])
    lzc = paired([p["ec_complexity"]["lzc"] for p in per], [p["eo_complexity"]["lzc"] for p in per])
    pe = paired([p["ec_complexity"]["perm_entropy"] for p in per], [p["eo_complexity"]["perm_entropy"] for p in per])
    clu = cluster_alpha(ec_alpha_perch, eo_alpha_perch, info_ref)
    gev = np.array([p["microstate_ec"]["gev_total"] for p in per])
    all_durs = np.array([d for p in per for d in p["microstate_ec"]["durations_ms"]])

    results = {
        "dataset": "PhysioNet eegbci (R01 eyes-open / R02 eyes-closed, 64ch, 160 Hz, ~61 s/run)",
        "n_subjects": len(per),
        "spectral_recipe": {
            "sanity": "eyes-closed > eyes-open posterior alpha",
            "posterior_alpha_EC_vs_EO": alpha,
            "second_level_spatial_cluster": clu,
            "PASS": bool(alpha["diff_mean"] > 0 and alpha["p"] < 0.05),
        },
        "complexity_recipe": {
            "sanity": "eyes-open > eyes-closed complexity",
            "lzc_EC_vs_EO": lzc, "perm_entropy_EC_vs_EO": pe,    # diff = EC - EO; expect < 0
            "PASS": bool(lzc["diff_mean"] < 0 and lzc["p"] < 0.05),
        },
        "microstate_recipe": {
            "sanity": "~4 maps, ~70% total GEV, durations 70-120 ms (EC)",
            "gev_total_mean": float(gev.mean()), "gev_total_std": float(gev.std()),
            "duration_ms_median": float(np.median(all_durs)),
            "duration_ms_iqr": [float(np.percentile(all_durs, 25)), float(np.percentile(all_durs, 75))],
            "PASS": bool(0.5 < gev.mean() < 0.95 and 50 < np.median(all_durs) < 150),
        },
        "per_subject": per,
    }
    import os
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(results, open(args.out, "w", encoding="utf-8"), indent=2)

    # --- Figure: grand-average posterior PSD (EC vs EO) + complexity + microstate ---
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        ecc, eoc = np.array(ec_curves), np.array(eo_curves)
        fig, ax = plt.subplots(1, 3, figsize=(15, 4))
        # F1: posterior PSD grand average ±SEM, log-y
        for curves, lab, c in [(ecc, "Eyes-closed", "C0"), (eoc, "Eyes-open", "C1")]:
            m, sem = curves.mean(0), curves.std(0) / np.sqrt(len(curves))
            ax[0].semilogy(freqs_ref, m, c, lw=2, label=lab)
            ax[0].fill_between(freqs_ref, m - sem, m + sem, color=c, alpha=0.2)
        ax[0].axvspan(8, 13, color="gray", alpha=0.15)
        ax[0].set(xlabel="Hz", ylabel="PSD (V²/Hz)", xlim=(1, 40),
                  title=f"A) Posterior PSD (N={len(per)})\nEC>EO α: p={alpha['p']:.1e}")
        ax[0].legend(fontsize=8)
        # F2: complexity EO vs EC (LZC, PE)
        eo_lzc = [p["eo_complexity"]["lzc"] for p in per]; ec_lzc = [p["ec_complexity"]["lzc"] for p in per]
        eo_pe = [p["eo_complexity"]["perm_entropy"] for p in per]; ec_pe = [p["ec_complexity"]["perm_entropy"] for p in per]
        xs = np.arange(2)
        ax[1].bar(xs - 0.18, [np.mean(eo_lzc), np.mean(eo_pe)], 0.36, label="Eyes-open",
                  yerr=[np.std(eo_lzc) / np.sqrt(len(per)), np.std(eo_pe) / np.sqrt(len(per))])
        ax[1].bar(xs + 0.18, [np.mean(ec_lzc), np.mean(ec_pe)], 0.36, label="Eyes-closed",
                  yerr=[np.std(ec_lzc) / np.sqrt(len(per)), np.std(ec_pe) / np.sqrt(len(per))])
        ax[1].set_xticks(xs); ax[1].set_xticklabels(["LZC", "PermEn"])
        ax[1].set(ylabel="complexity", title=f"B) EO>EC complexity\nLZC p={lzc['p']:.1e}, PE p={pe['p']:.1e}")
        ax[1].legend(fontsize=8)
        # F3: microstate GEV per subject
        ax[2].bar(range(len(gev)), gev, color="C2")
        ax[2].axhline(gev.mean(), color="k", ls="--", label=f"mean={gev.mean():.2f}")
        ax[2].set(xlabel="subject", ylabel="total GEV", ylim=(0, 1),
                  title=f"C) Microstate GEV (K=4)\ndur median={np.median(all_durs):.0f} ms")
        ax[2].legend(fontsize=8)
        plt.suptitle("Resting recipes validation — eegbci EC vs EO (server)", fontweight="bold")
        plt.tight_layout()
        figpath = os.path.join(os.path.dirname(args.out), "figures", "resting_validation.png")
        os.makedirs(os.path.dirname(figpath), exist_ok=True)
        plt.savefig(figpath, dpi=140, bbox_inches="tight")
        plt.close()
        results["figure"] = figpath
        print(f"Figure: {figpath}")
    except Exception as e:
        print(f"[figure skipped] {type(e).__name__}: {e}")

    print("\n==== GROUP RESULTS (N=%d) ====" % len(per))
    print(f"[spectral]   EC>EO posterior alpha: diff={alpha['diff_mean']:.2e} "
          f"t={alpha['t']:.2f} p={alpha['p']:.2e} dz={alpha['cohens_dz']:.2f} "
          f"| cluster sig={clu['n_significant']} min_p={clu['min_p']:.4f} -> PASS={results['spectral_recipe']['PASS']}")
    print(f"[complexity] EO>EC: LZC EC={lzc['ec_mean']:.3f} EO={lzc['eo_mean']:.3f} p={lzc['p']:.2e} "
          f"dz={lzc['cohens_dz']:.2f} | PE p={pe['p']:.2e} -> PASS={results['complexity_recipe']['PASS']}")
    print(f"[microstate] GEV={gev.mean():.3f}±{gev.std():.3f} dur_median={np.median(all_durs):.0f}ms "
          f"-> PASS={results['microstate_recipe']['PASS']}")
    print(f"\nSaved: {args.out}")


if __name__ == "__main__":
    main()
