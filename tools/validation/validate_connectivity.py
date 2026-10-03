"""B5 follow-up: benchmark the wPLI connectivity path of resting-spectral-connectivity.

The recipe is named "...-connectivity" but only its alpha-power half was validated; wPLI was
API-smoke-tested only (audit item #2). Here we compute debiased wPLI per subject on eegbci
eyes-closed vs eyes-open (2 s epochs, alpha 8-13 Hz) and test the posterior alpha-band
connectivity contrast across subjects — moving connectivity from "API runs" to "shows the
expected EC>EO posterior alpha synchrony".

  python tools/validation/validate_connectivity.py --subjects 15
"""
from __future__ import annotations
import argparse, json, sys, warnings
from pathlib import Path
import numpy as np

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_resting_recipes import load_run, EO_RUN, EC_RUN, POSTERIOR  # noqa: E402


def wpli_posterior(raw):
    """Mean debiased-wPLI among posterior channels, alpha band, from 2 s epochs."""
    import mne
    from mne_connectivity import spectral_connectivity_epochs
    r = raw.copy().filter(1, 45, verbose="ERROR")
    ep = mne.make_fixed_length_epochs(r, duration=2.0, overlap=0.0, preload=True, verbose="ERROR")
    post = [c for c in POSTERIOR if c in r.ch_names]
    post_idx = [r.ch_names.index(c) for c in post]
    con = spectral_connectivity_epochs(
        ep, method="wpli2_debiased", mode="multitaper",
        fmin=8.0, fmax=13.0, faverage=True, n_jobs=1, verbose="ERROR")
    M = con.get_data(output="dense")[:, :, 0]          # (ch, ch) lower-triangular
    M = M + M.T                                          # symmetrize for indexing
    # mean wPLI over posterior-posterior edges (upper triangle, no diagonal)
    sub = M[np.ix_(post_idx, post_idx)]
    iu = np.triu_indices(len(post_idx), k=1)
    return float(np.mean(np.abs(sub[iu])))


def main():
    from scipy import stats
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", type=int, default=15)
    ap.add_argument("--out", default="tools/validation/connectivity_results.json")
    args = ap.parse_args()

    ec, eo, per = [], [], []
    for s in range(1, args.subjects + 1):
        try:
            ec_raw = load_run(s, EC_RUN, sfreq=250.0, do_ica=True)
            eo_raw = load_run(s, EO_RUN, sfreq=250.0, do_ica=True)
            e_c, e_o = wpli_posterior(ec_raw), wpli_posterior(eo_raw)
            ec.append(e_c); eo.append(e_o)
            per.append({"subject": s, "ec_wpli": round(e_c, 4), "eo_wpli": round(e_o, 4)})
            print(f"  subj {s:2d}: EC wPLI={e_c:.4f}  EO wPLI={e_o:.4f}", flush=True)
        except Exception as e:
            print(f"  subj {s:2d}: SKIP {type(e).__name__}: {str(e)[:60]}", flush=True)

    ec, eo = np.array(ec), np.array(eo)
    d = ec - eo
    t, p = stats.ttest_rel(ec, eo)
    res = {
        "metric": "debiased wPLI (wpli2_debiased), posterior-posterior edges, alpha 8-13 Hz",
        "dataset": "eegbci EC vs EO, ICA-cleaned, N=%d" % len(ec),
        "ec_mean": round(float(ec.mean()), 4), "eo_mean": round(float(eo.mean()), 4),
        "diff_ec_minus_eo": round(float(d.mean()), 4),
        "t": round(float(t), 2), "p": float(p),
        "cohens_dz": round(float(d.mean() / d.std(ddof=1)), 3) if d.std(ddof=1) > 0 else 0.0,
        "n": int(len(ec)),
        "PASS": bool(d.mean() > 0 and p < 0.05),
        "per_subject": per,
    }
    import os
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(res, open(args.out, "w", encoding="utf-8"), indent=2)
    print(f"\n[connectivity] posterior alpha wPLI EC={ec.mean():.4f} EO={eo.mean():.4f} "
          f"diff={d.mean():+.4f} t={t:.2f} p={p:.2e} dz={res['cohens_dz']} -> PASS={res['PASS']}")
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()
