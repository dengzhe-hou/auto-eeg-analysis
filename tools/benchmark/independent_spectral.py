"""Non-ERP numeric validation: spectral band power (resting eegbci), MNE vs independent DSP.

Extends the cross-tool numeric benchmark beyond ERP to AEA's spectral measures (`eeg-spectral`).
For each subject's resting EEG (PhysioNet eegbci, eyes-closed), per-channel band power
(delta/theta/alpha/beta) is computed from the SAME data three ways:

  (A) MNE Welch          — mne.time_frequency.psd_array_welch
  (B) from-scratch Welch — numpy rfft, manual segmenting/hamming/one-sided density scaling
                           (genuinely independent of MNE; note scipy.signal.welch shares MNE's path so
                            is NOT independent — hence the hand-rolled version)
  (C) MNE multitaper     — mne.time_frequency.psd_array_multitaper (a DIFFERENT estimator)

Two questions, honestly separated:
 * (A vs B) IMPLEMENTATION independence — does AEA's band power match an independent Welch? Welch is a
   deterministic formula (no kernel choice like an ERP filter), so tight agreement is expected and
   *confirms correctness* rather than probing sensitivity.
 * (A vs C) ESTIMATOR sensitivity — how much does the band power move if you swap Welch for multitaper?
   This is the spectral analog of the ERP filter-kernel sensitivity in BENCHMARK.md §4g.

  python tools/benchmark/independent_spectral.py --subjects 12
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
from scipy import stats
import mne
from mne.datasets import eegbci
from mne.time_frequency import psd_array_welch, psd_array_multitaper

mne.set_log_level("ERROR")
BANDS = {"delta": (1, 4), "theta": (4, 8), "alpha": (8, 13), "beta": (13, 30)}
FMIN, FMAX = 1.0, 30.0
_trapz = np.trapz if hasattr(np, "trapz") else np.trapezoid


def _bandpower(psd, freqs):
    out = {}
    for b, (lo, hi) in BANDS.items():
        m = (freqs >= lo) & (freqs <= hi)
        out[b] = _trapz(psd[:, m], freqs[m], axis=1)
    return out


LEGACY_CONVENTIONS = False   # --legacy-conventions: symmetric window, no demeaning (the 2026-08 baseline)
WINDOW = "hamming"           # --window hann certifies the eeg-spectral skill's released default (Hann, review 2026-09-15)


def welch_scratch(x, sf, n_per_seg, n_overlap):
    """Hand-rolled Welch PSD (density, one-sided), independent of MNE/scipy."""
    # Conventions pinned to what MNE's psd_array_welch actually does (external review, 2026-09-14):
    # a PERIODIC Hamming window (scipy get_window default, fftbins=True) -- np.hamming(n) is the
    # symmetric one -- and per-segment demeaning (remove_dc=True -> detrend="constant"). The first
    # version used the symmetric window without demeaning and then attributed the 0.4% residual to
    # "segment-boundary/count handling", which was unsupported: that residual WAS the convention gap.
    wfn = np.hanning if WINDOW == "hann" else np.hamming
    win = wfn(n_per_seg) if LEGACY_CONVENTIONS else wfn(n_per_seg + 1)[:-1]   # symmetric (legacy) / periodic
    scale = 1.0 / (sf * (win ** 2).sum())          # density scaling
    step = n_per_seg - n_overlap
    starts = range(0, x.shape[1] - n_per_seg + 1, step)
    freqs = np.fft.rfftfreq(n_per_seg, 1.0 / sf)
    acc = np.zeros((x.shape[0], freqs.size)); k = 0
    for s0 in starts:
        seg = x[:, s0:s0 + n_per_seg]
        if not LEGACY_CONVENTIONS:
            seg = seg - seg.mean(axis=1, keepdims=True)         # demean each segment (MNE: remove_dc)
        seg = seg * win
        P = (np.abs(np.fft.rfft(seg, axis=1)) ** 2) * scale
        P[:, 1:-1] *= 2.0                          # one-sided (not DC/Nyquist)
        acc += P; k += 1
    return acc / k, freqs


def subject_bp(sub):
    fn = eegbci.load_data(sub, runs=[2], update_path=False)      # eyes-closed baseline
    raw = mne.io.read_raw_edf(fn[0], preload=True, verbose="ERROR")
    raw.pick_types(eeg=True, verbose="ERROR")
    x, sf = raw.get_data(), raw.info["sfreq"]
    nps = int(round(2.0 * sf)); nov = nps // 2
    pa, fa = psd_array_welch(x, sfreq=sf, fmin=FMIN, fmax=FMAX, n_fft=nps, n_per_seg=nps,
                             n_overlap=nov, window=WINDOW, average="mean", verbose="ERROR")
    pb, fb = welch_scratch(x, sf, nps, nov); m = (fb >= FMIN) & (fb <= FMAX); pb, fb = pb[:, m], fb[m]
    pc, fc = psd_array_multitaper(x, sfreq=sf, fmin=FMIN, fmax=FMAX, adaptive=False,
                                  normalization="full", verbose="ERROR")
    return _bandpower(pa, fa), _bandpower(pb, fb), _bandpower(pc, fc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", type=int, default=12)
    ap.add_argument("--out", default="tools/benchmark/SPECTRAL_KERNEL_INDEP_RESULT.json")
    ap.add_argument("--window", choices=["hamming", "hann"], default="hamming",
                    help="Welch taper for both implementations; hann is the eeg-spectral skill's released default")
    ap.add_argument("--legacy-conventions", action="store_true",
                    help="reproduce the original scratch Welch (symmetric Hamming, no segment demeaning) "
                         "so the pre-correction 0.44%% residual is an evidence file, not a memory")
    args = ap.parse_args()
    global LEGACY_CONVENTIONS, WINDOW
    LEGACY_CONVENTIONS = args.legacy_conventions
    WINDOW = args.window
    if args.window == "hann" and args.out == "tools/benchmark/SPECTRAL_KERNEL_INDEP_RESULT.json":
        args.out = "tools/benchmark/SPECTRAL_KERNEL_INDEP_RESULT_hann.json"

    ind_rel = {b: [] for b in BANDS}      # A vs B (implementation)
    est_rel = {b: [] for b in BANDS}      # A vs C (estimator)
    va, vb = {b: [] for b in BANDS}, {b: [] for b in BANDS}
    n = 0
    for s in range(1, args.subjects + 1):
        try:
            A, B, C = subject_bp(s)
            for b in BANDS:
                d = np.where(A[b] != 0, A[b], np.nan)
                ind_rel[b].append(float(np.nanmax(np.abs(A[b] - B[b]) / np.abs(d))))
                est_rel[b].append(float(np.nanmedian(np.abs(A[b] - C[b]) / np.abs(d))))
                va[b].extend(A[b].tolist()); vb[b].extend(B[b].tolist())
            n += 1
            print(f"  S{s:03d}: A-vs-B max rel {max(ind_rel[b][-1] for b in BANDS):.1e} | "
                  f"A-vs-C(multitaper) median rel alpha={est_rel['alpha'][-1]:.3f}", flush=True)
        except Exception as e:
            print(f"  S{s:03d}: SKIP {type(e).__name__}: {str(e)[:50]}", flush=True)

    summary = {
        "check": "non-ERP band power (resting eegbci eyes-closed): MNE Welch vs (B) independent from-scratch Welch, (C) MNE multitaper",
        "bands": {b: list(v) for b, v in BANDS.items()}, "n_subjects": n,
        "implementation_independence_A_vs_B": {
            b: {"max_rel_err": float(np.max(ind_rel[b])),      # unrounded: 12 dp turned ~5e-16 into 0.0 (review, 2026-09-14)
                "pearson_r": round(float(stats.pearsonr(va[b], vb[b])[0]), 8)} for b in BANDS},
        "estimator_sensitivity_A_vs_C_multitaper": {
            b: {"median_rel_diff": round(float(np.median(est_rel[b])), 4),
                "max_rel_diff": round(float(np.max(est_rel[b])), 4)} for b in BANDS},
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(summary, open(args.out, "w", encoding="utf-8"), indent=2)
    print("\n  band   A-vs-B max-rel(impl)   A-vs-C median-rel(estimator)")
    for b in BANDS:
        i = summary["implementation_independence_A_vs_B"][b]["max_rel_err"]
        e = summary["estimator_sensitivity_A_vs_C_multitaper"][b]["median_rel_diff"]
        print(f"  {b:6}  {i:.2e}              {e:.3f}")
    print(f"  N={n}  saved {args.out}")


if __name__ == "__main__":
    main()
