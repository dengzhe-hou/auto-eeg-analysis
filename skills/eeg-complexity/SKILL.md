---
name: eeg-complexity
description: "Nonlinear / complexity & entropy analysis of EEG: Lempel-Ziv complexity (LZC/PLZC, multichannel spatiotemporal LZc/ACE/SCE), sample/approximate/permutation/dispersion/multiscale (MSE/RCMSE)/Shannon/wavelet/Hilbert-Huang entropy, recurrence quantification analysis (RQA), scale-free dynamics (aperiodic 1/f slope, DFA, Hurst, LRTC), criticality (neuronal avalanches, edge-of-chaos), perturbational complexity (PCI/PCIst, TMS-gated), and spatial complexity (Omega / normalized SC / LCD). Computes per-channel windowed complexity time courses and per-condition contrasts. Optional skill — only invoked if DATASET_BRIEF.md / ANALYSIS_PLAN.md ticks Complexity (entropy, nonlinear dynamics, criticality, anesthesia/consciousness-depth). Trigger words: 'complexity', 'entropy', 'Lempel-Ziv', 'LZC', 'sample entropy', 'permutation entropy', 'dispersion entropy', 'multiscale entropy', 'MSE', 'RQA', 'recurrence', 'DFA', 'Hurst', 'LRTC', 'criticality', 'avalanche', 'PCI', 'perturbational complexity', 'scale-free', '1/f', 'spatial complexity'."
argument-hint: "[project-dir] [— metric: lzc|plzc|lzc_st|ace|sce|sampen|apen|pe|dispen|mse|rcmse|shannon|wavelet_en|hhse|rqa|dfa|lrtc|avalanche|pcist|spatial] [— window: 5] [— overlap: 3]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-complexity: nonlinear / entropy / complexity analysis

## Context: $ARGUMENTS

> **OPTIONAL skill.** Only run if `DATASET_BRIEF.md` (or `ANALYSIS_PLAN.md`) ticks Complexity / entropy / nonlinear dynamics / criticality / consciousness-depth tracking. If no complexity claim exists, **do not run** — return control to the dispatcher.
>
> **Every external library in this skill is an OPTIONAL dependency.** None of `antropy`, `neurokit2`, `EntropyHub`, `nolds`, `mne-features`, `pywt`, `PyEMD`/`emd`, `specparam`/`fooof` are guaranteed to be installed. **Every** code path MUST guard its import, log availability to the stage JSON, surface missing libs in `BACKEND_RESOLUTION.md`, and degrade gracefully (skip the metric with a clear message + `pip install` hint — never crash the stage). Only `numpy`/`scipy`/`scikit-learn`/`mne` are assumed present.

## Constants

- **METRIC = `pe`** by default (permutation entropy — amplitude-blind, noise-robust, cheapest reliable default). Override with any metric below.
- **WINDOW = `5.0`** s — sliding-window length for time-domain metrics (LZC/PLZC, SampEn/ApEn, PE, Shannon, wavelet entropy, HHSE, RQA). Complexity is computed per window per channel to yield a time course tracking state.
- **OVERLAP = `3.0`** s — window overlap (5 s window / 2 s step ⇒ 3 s overlap).
- **SCALE_WINDOW = `16.0`** s, **SCALE_OVERLAP = `12.0`** s (75 %) — longer windows for scale-free / DFA / Hurst / aperiodic-slope metrics, which need many more samples than entropy.
- **Embedding defaults**: `m = 2` for SampEn/ApEn; `order = 3` for permutation entropy; `m = 3, tau = 1` for RQA; PLZC `dimension = 4, delay = 1`. Set `tau` from the first minimum of mutual information and `m` from false-nearest-neighbours when data permit.
- **TOLERANCE r = `0.2 * SD`** for SampEn/ApEn (Richman–Moorman default). Some EEG studies use `0.15 * SD` — make this configurable; `r` is recomputed from **each window's own SD**, never a global SD.
- **RQA_THRESHOLD = `0.5 * SD`** (fixed-fraction-of-SD); `Lmin = 2` for DET/ENTR.
- **SHANNON_BINS = `20`** (fixed across all compared epochs/conditions).
- **WAVELET = `db4`**, **WAVELET_LEVEL = `round(log2(fs)) - 3`** (ties decomposition depth to sampling rate).
- **BACKENDS** — chosen per metric (see Phase B table), all OPTIONAL: `antropy`, `neurokit2`, `EntropyHub`, `nolds`, `mne-features`, `pywt`, `PyEMD`/`emd`, `specparam`.
- **OUTPUT_DIR = `complexity-stage/`** — create if missing.
- **N_JOBS = `4`**.
- **SEED = read from ANALYSIS_PLAN.md**, default `42`.

> Override: `/eeg-complexity projects/my-study — metric: sampen — window: 5 — overlap: 3`

## Required Inputs

Before running, these must exist:

1. `ANALYSIS_PLAN.md` — frozen, with the complexity/entropy claim(s). **Stop if missing or unfrozen.**
2. `DATASET_BRIEF.md` — must tick Complexity (otherwise this skill should not have been invoked); also gives the paradigm and condition labels (e.g. awake vs deep anesthesia, eyes-open vs eyes-closed).
3. Preprocessed data: `preprocess-stage/` or `ica-stage/` (continuous, for windowed time courses) or `epoch-stage/` (already-epoched).
4. `ENVIRONMENT.json` — to resolve which complexity backend is available.
5. `channel_mapping.json` — if claim ROI uses 10-20 names but data uses numbered channels.

## Phase A — Metric selection and validation

1. Read `ANALYSIS_PLAN.md` for complexity-related claims and the requested `METRIC`. If `DATASET_BRIEF.md` does not tick Complexity → STOP (skill out of scope).
2. Classify the metric and validate against the data:
   - **Temporal entropy/complexity** (per-channel, per-window 1-D series): `lzc`, `plzc`, `sampen`, `apen`, `pe`, `dispen`, `mse`/`rcmse`, `shannon`, `wavelet_en`, `hhse`, `rqa`. Use `WINDOW`/`OVERLAP`.
   - **Multichannel signal diversity** (`lzc_st`, `ace`, `sce`): spatiotemporal LZ/coalition metrics across channels — Hilbert-binarized, surrogate-normalized (Phase D); distinct from per-channel `lzc`.
   - **Scale-free / criticality** (`dfa`, `hurst`, aperiodic slope, `lrtc`, `avalanche`): `dfa`/`hurst`/slope need `SCALE_WINDOW` (≥16 s) and z-scoring per window; `lrtc` is DFA on a *narrow-band amplitude envelope*; `avalanche` needs long recordings (Phase F).
   - **Perturbational complexity** (`pci`/`pcist`): consciousness biomarker — **requires a TMS/perturbation tick**, runs on the evoked response, not spontaneous data (Phase F).
   - **Spatial complexity** (`spatial`: Omega / NSC / LCD): a *multivariate* metric across channels — **requires average reference** (Phase G). One value per window across all channels (or per ROI).
3. Sample-size guard: temporal metrics need `N >> alphabet^m` (rule of thumb `N ≥ 10^m` to `30^m`). For SampEn/ApEn m=2 ⇒ a 5 s window at fs=250 (1250 pts) is ample; flag windows shorter than `~100 * (m+1)` points.
4. Amplitude vs amplitude-blind: if amplitude differs across conditions/electrodes (e.g. impedance, montage), prefer **PE or PLZC** (amplitude-independent) over amplitude-thresholded LZC / Shannon-amplitude entropy.
5. Note the resampling: many published complexity pipelines downsample to fs=100–250 Hz before windowing — record the effective `fs` because `WAVELET_LEVEL`, `r`, and embedding behaviour depend on it.

Write `complexity-stage/METRIC_SELECTION.md` documenting the metric, parameters, window scheme, and backend.

## Phase B — Backend resolution

```
1. Read ENVIRONMENT.json.
2. Resolve the backend for the chosen metric from the table below.
3. Probe the backend by attempting its import (see check_backend()).
4. If the required package is missing → record the exact `pip install ...` in
   BACKEND_RESOLUTION.md, mark the metric SKIPPED in the stage JSON, surface it
   in AUDIT, and continue with the remaining (available) metrics. Do NOT crash.
```

**Availability probe — run once at stage start and write the result to `BACKEND_RESOLUTION.md`:**

```python
import importlib.util, json

OPTIONAL_LIBS = [
    "antropy", "neurokit2", "EntropyHub", "nolds",
    "mne_features", "pywt", "PyEMD", "emd", "specparam", "fooof",
    "powerlaw", "PCIst",   # neuronal avalanches (powerlaw) / perturbational complexity (PCIst)
]

def check_backend(name):
    """True only if the module actually IMPORTS. `find_spec` passes for an
    installed-but-broken package (e.g. the nolds 0.6.3 'nolds.datasets is not a
    package' bug on Python 3.11) that then crashes at the real import — so attempt
    the import, not just spec resolution. NEVER raises."""
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False

availability = {lib: check_backend(lib) for lib in OPTIONAL_LIBS}
with open("complexity-stage/BACKEND_RESOLUTION.md", "w") as f:
    f.write("# Complexity backend availability\n\n")
    for lib, ok in availability.items():
        f.write(f"- {lib}: {'available' if ok else 'MISSING (pip install %s)' % lib}\n")
# Persist into the stage JSON so eeg-stats / AUDIT can see what was skipped.
```

Wrap every metric call in a guard, e.g.:

```python
if not check_backend("neurokit2"):
    log_skip("sampen", "neurokit2 not installed (pip install neurokit2)")
else:
    import neurokit2 as nk
    ...
```

**Library selection — pick the backend per metric (coverage is non-overlapping). All libraries are OPTIONAL:**

| Metric | Recommended backend | Documented call | Caveat / degradation |
|---|---|---|---|
| Permutation entropy | `antropy` | `ant.perm_entropy(x, order=3, delay=1, normalize=True)` | lightest dependency; if missing, PE is computable from `scipy` (ordinal histogram → Shannon) as a numpy fallback |
| LZC | `antropy` (+ manual binarize) / `neurokit2` | `ant.lziv_complexity(bin, normalize=True)` or `nk.complexity_lempelziv(x, symbolize='median')` | antropy expects an **already-binarized** 0/1 sequence; the LZ parse is short enough to implement in numpy if neither lib is present |
| PLZC | `neurokit2` | `nk.complexity_lempelziv(x, dimension=4, delay=1, permutation=True)` | normalization base must be `m!`, **not 2** |
| SampEn / ApEn (tunable r) | `neurokit2` or `EntropyHub` | `nk.entropy_sample(x, dimension=2, tolerance=0.2*np.std(x))` / `EH.SampEn(x, m=2, r=0.2*np.std(x))` | **`antropy` hardcodes r=0.2*SD and cannot change it**; if you need another `r`, you MUST use neurokit2/EntropyHub |
| Dispersion entropy (DispEn) | `EntropyHub` | `EH.DispEn(x, m=2, tau=1, c=6, Typex='ncdf')` | amplitude-aware, `O(N)`; if missing, fall back to PE (loses amplitude info) |
| Multiscale entropy (MSE / RCMSE) | `EntropyHub` / `neurokit2` | `EH.rcMSEn(x, EH.MSobject('SampEn', m=2, r=0.15*np.std(x)), Scales=...)` | hold `r` fixed across scales; **default RCMSE** on AEA's 5 s windows (plain MSE → undefined SampEn at coarse scales) |
| Neuronal avalanches | `powerlaw` (+ numpy event detection) | `powerlaw.Fit(sizes, xmin=1)` then KS goodness-of-fit | ML fit only — never log-log least-squares; bin at the mean inter-event interval |
| Perturbational complexity (PCI / PCIst) | `PCIst` (renzocom/PCIst) | `pci_st.calc_PCIst(evoked, times, **par)` | **requires a TMS/perturbation tick**; not computable from spontaneous EEG |
| Spectral / SVD entropy | `antropy` / `mne-features` | `ant.spectral_entropy(x, sf=fs, method='welch', normalize=True)` | spectral entropy also derivable from `mne.time_frequency.psd_array_welch` + numpy |
| Shannon (amplitude) | `numpy`/`scipy` (no optional dep) | histogram → `-Σ p log p` | bin-count dependent — fix bins; pure-numpy, always available |
| Wavelet entropy | `pywt` | `pywt.wavedec(x, 'db4', level=...)` then energy entropy | antropy has no DWT wavelet entropy; if `pywt` missing, skip (no clean numpy DWT fallback) |
| Hilbert-Huang spectral entropy | `PyEMD` / `emd` | `EMD()(x)` → Hilbert marginal spectrum → Shannon | slow, mode-mixing prone; if missing, fall back to db4 wavelet entropy |
| RQA | `neurokit2` / `pyrqa` / `pyunicorn` | `nk.complexity_rqa(x, dimension=3, delay=1, tolerance='sd')` | nk is lightest; recurrence matrix is `O(N^2)` |
| DFA / Hurst | `nolds` / `antropy` | `nolds.dfa(x)`, `nolds.hurst_rs(x)`, `ant.detrended_fluctuation(x)` | two libs cover this; if both missing, skip scale-free metrics |
| Aperiodic 1/f exponent | `specparam` (FOOOF) | `SpectralModel().fit(freqs, psd, [1,40])` | modern standard for slope (see eeg-spectral); package may be `specparam` or legacy `fooof` |
| Corr-dim / Lyapunov | `nolds` | `nolds.corr_dim(x, emb_dim)`, `nolds.lyap_r(x)` | sensitive to noise; long data only; surrogate-test required |
| Fractal dim, Hjorth, line length | `antropy` / `mne-features` | `ant.higuchi_fd`, `ant.katz_fd`, mne_features feature funcs | feeds eeg-decoding feature matrix |
| Spatial complexity (Omega/NSC/LCD) | pure `numpy` (no optional dep) | eigvals of channel covariance (Phase G) | requires average reference; always available |

Default to `neurokit2`/`EntropyHub` whenever a specific tolerance `r` is required, because `antropy` cannot set it. Use `mne-features` when integrating into an MNE/sklearn pipeline (see eeg-decoding).

Write `complexity-stage/BACKEND_RESOLUTION.md` with the availability map and the per-metric choice.

## Phase C — Windowing (shared helper for temporal metrics)

Slice continuous data into fixed windows, compute the chosen metric per window per channel, return a `(n_channels, n_windows)` time course. This is a thin wrapper over `mne.make_fixed_length_epochs` (verified signature: `duration` and `overlap` kwargs, both in seconds).

```python
import mne, numpy as np

raw = mne.io.read_raw_fif(preprocessed_path, preload=True)
fs = raw.info['sfreq']

# 5 s windows, 3 s overlap → 2 s step
win_epochs = mne.make_fixed_length_epochs(
    raw, duration=WINDOW, overlap=OVERLAP, preload=True)
data = win_epochs.get_data()        # (n_windows, n_channels, n_times)
n_win, n_ch, n_t = data.shape

def metric_per_window(x, fs):
    # x is one channel within one window (1-D)
    return COMPUTE_METRIC(x, fs)    # see Phase D–G

tc = np.full((n_ch, n_win), np.nan)
for w in range(n_win):
    for c in range(n_ch):
        tc[c, w] = metric_per_window(data[w, c], fs)
# tc → per-channel complexity time course; aggregate (mean) per condition.
```

For scale-free metrics use `duration=SCALE_WINDOW, overlap=SCALE_OVERLAP` and z-score each window first.

## Phase D — Temporal entropy & Lempel-Ziv

Every subsection below is gated by `check_backend(...)` from Phase B; if the backend is unavailable, log a skip and move on.

### Lempel-Ziv complexity (LZC)

Binarize the 1-D signal to a 0/1 string, count distinct substrings via the LZ parse, then normalize by `n / log2(n)` (values ≈ [0,1], comparable across window lengths).

```python
import antropy as ant   # OPTIONAL — guard with check_backend("antropy")
import numpy as np

# Default binarization: MEDIAN threshold (amplitude/outlier robust, literature default)
binseq = (x > np.median(x)).astype(int)
lzc = ant.lziv_complexity(binseq, normalize=True)   # n/log2(n) normalization
```

Binarization rules (default = median):
- **median** (default) — `x > median(x)`; robust to amplitude outliers.
- **mean** — `x > mean(x)`; sensitive to skew/outliers.
- **midpoint** — `x > (max+min)/2`; very outlier-sensitive.
- **kmeans** — two centroids near the mean; data-adaptive but slowest.

Compute LZC **per channel on the 1-D series**, never across channels. Use fixed-length windows — `c(n)` grows with `n` even after normalization for short `n`, so window length must match across compared segments.

### Permutation LZC (PLZC)

Permutation-symbolize first (ordinal patterns, `m=4, tau=1` ⇒ 24 motifs), then run the LZ parse normalized by `log_{m!}(n)` (i.e. base `m! = 24`, **not 2**).

```python
import neurokit2 as nk   # OPTIONAL — guard with check_backend("neurokit2")
plzc, _ = nk.complexity_lempelziv(x, dimension=4, delay=1, permutation=True)
```

PLZC is **amplitude-independent** (preferred when amplitude differs across conditions/electrodes) and more noise-robust than amplitude-thresholded LZC. Default `m=4`; `m=3` also common. If you build the ordinal sequence manually and feed `antropy.lziv_complexity`, it assumes 2 symbols — you **must renormalize** by `log2 / log(m!)` yourself.

### Multichannel signal diversity: spatiotemporal LZc, ACE, SCE

Distinct from the strictly-per-channel LZC above: for consciousness/anesthesia/psychedelic contrasts, compute LZc on the **whole channels-by-time matrix** to index spatiotemporal signal diversity. Hilbert-binarize each channel by its instantaneous amplitude (above/below its own mean), then column-wise concatenate the binarized channels into one string before the LZ parse. Two companion coalition measures: **ACE** (amplitude coalition entropy) tracks the variability of the *set of active channels* (a differentiation index), **SCE** (synchrony coalition entropy) tracks the variability of the set of *pairwise-synchronous* channels (an integration index). All three drop under propofol and rise under psychedelics.

```python
from scipy.signal import hilbert
import numpy as np
amp = np.abs(hilbert(data, axis=-1))                 # data: (n_channels, n_times)
binmat = (amp > amp.mean(axis=-1, keepdims=True)).astype(int)
seq = binmat.flatten(order='F')                      # column-wise (time-major) concatenation
lzc_st = ant.lziv_complexity(seq, normalize=True)    # OPTIONAL antropy; or manual LZ parse
```

- **Critical caveat:** normalize each subject's raw value by the value of its own **phase-shuffled surrogate** before comparing across montages/channel counts (raw LZc/ACE/SCE scale with channel number and spectral content). Treat this as mandatory whenever the contrast spans different montages.
- This is a *multichannel* metric — it is an exception to the per-channel LZC rule and must operate across channels by construction.
- Cite: Schartner, M., Seth, A., Noirhomme, Q., Boly, M., Bruno, M.-A., Laureys, S., & Barrett, A. (2015). Complexity of multi-dimensional spontaneous EEG decreases during propofol-induced general anaesthesia. PLoS ONE, 10(8), e0133532.

### Sample & Approximate entropy (SampEn / ApEn)

```python
import neurokit2 as nk      # OPTIONAL — neurokit2 / EntropyHub expose tolerance; antropy does NOT
r = 0.2 * np.std(x)         # recompute PER WINDOW from this window's SD
sampen, _ = nk.entropy_sample(x, dimension=2, tolerance=r)        # Chebyshev distance, excludes self-matches
apen,   _ = nk.entropy_approximate(x, dimension=2, tolerance=r)   # includes self-matches
```

- Default `m=2`; `r ∈ [0.15, 0.2] * SD` (Richman–Moorman default 0.2) — keep configurable.
- **Prefer SampEn over ApEn**: SampEn excludes self-matches (`-1` terms) and uses strict `< r`, so it is bias-free and (largely) length-independent; ApEn includes self-matches and is biased toward regularity, especially for short series.
- `r` must scale with **each window's** SD, not a global SD.
- If only `antropy` is available you CANNOT honor a non-default `r` — log this and either accept antropy's fixed `r=0.2*SD` or skip the metric.

### Permutation entropy (PE)

```python
pe = ant.perm_entropy(x, order=3, delay=1, normalize=True)   # H / ln(m!) → [0,1]
```

- Default `order=3`; `3–7` typical, with the hard constraint `m! << window length`.
- `delay=1`; always `normalize=True`.
- PE is amplitude-blind and robust to noise/artifacts; it **decreases under deep anesthesia** and is higher eyes-open than eyes-closed. Shares ordinal symbolization with PLZC.
- Numpy fallback if `antropy` missing: build the ordinal-pattern histogram over all `m!` orderings and take `-Σ p log p / log(m!)`.

### Dispersion entropy (DispEn)

A fast, amplitude-*aware* alternative that fills the gap between amplitude-blind PE/PLZC and bin-fragile Shannon-amplitude entropy. Map each sample through the normal CDF into `c` classes, embed (`m`, `delay`), then count the frequency of each of the `c^m` dispersion patterns and take their Shannon entropy. Cost is `O(N)` (vs `O(N^2)` for SampEn) and it is more noise-tolerant than SampEn, while — unlike PE — it **retains amplitude information** that PE discards.

```python
import EntropyHub as EH   # OPTIONAL — guard with check_backend("EntropyHub")
dispen, _ = EH.DispEn(x, m=2, tau=1, c=6, Typex='ncdf')   # normal-CDF mapping, 6 classes
```

- Defaults `c=6`, `m=2–3`, `delay=1`. For long EEG the multiscale form **RCMDE** (refined composite multiscale dispersion entropy) is the efficient replacement for multiscale SampEn.
- Backend: `EntropyHub` (optional, graceful-degrade per Phase B); if missing, log a skip and fall back to PE.
- Cite: Rostaghi, M., & Azami, H. (2016). Dispersion entropy: a measure for time-series analysis of complexity. IEEE Signal Processing Letters, 23(5), 610–614.

### Multiscale entropy (MSE / RCMSE)

Single-scale SampEn/PE see only one time scale; multiscale entropy coarse-grains the series at scales `tau = 1..N` (non-overlapping averaging) and computes SampEn per scale, with the **complexity index defined as the area under the SampEn-vs-scale curve**. EEG often shows reduced *fine*-scale entropy with scale-specific group effects.

```python
import EntropyHub as EH   # OPTIONAL — guard with check_backend("EntropyHub")
r = 0.15 * np.std(x)                                   # compute ONCE on scale-1 SD; HOLD FIXED across scales
mobj = EH.MSobject('SampEn', m=2, r=r)
mse, ci = EH.rcMSEn(x, mobj, Scales=max_scale)         # RCMSE → robust on short windows
```

Encodable pitfalls:
- Recompute `r` **once** from the scale-1 SD and **hold it fixed** across all coarse-grained scales — do NOT recompute `r` per scale (coarse-graining lowers the SD and would silently inflate entropy at high scales).
- Cap `max_scale` because coarse-graining shortens the series: a scale-`tau` series has only `N/tau` points.
- On AEA's 5 s windows, plain MSE yields **undefined SampEn at coarse scales** (no `m+1` matches) — **default to RCMSE** (refined composite MSE: average the `m` and `m+1` match *counts* across all coarse-grained sub-sequences before taking the log ratio) and report `scales-defined`.
- Backend: `EntropyHub` or `neurokit2` (optional, graceful-degrade).
- Cite: Costa, M., Goldberger, A. L., & Peng, C.-K. (2002). Multiscale entropy analysis of complex physiologic time series. Physical Review Letters, 89(6), 068102. Wu, S.-D., Wu, C.-W., Lin, S.-G., Wang, C.-C., & Lee, K.-Y. (2014). Time series analysis using composite multiscale entropy. Physics Letters A, 378(20), 1369–1374 (RCMSE).

### Shannon entropy (amplitude)

Histogram-bin the signal with a **fixed** bin count identical across all compared epochs, then `-Σ p log p` normalized by `log(n_occupied_bins)`. Pure numpy — always available.

```python
hist, _ = np.histogram(x, bins=20)          # fixed bins (default 20)
p = hist[hist > 0] / hist.sum()
H = -np.sum(p * np.log(p))
H_norm = H / np.log(len(p))                  # bounded, comparable
```

Absolute value is meaningless without a fixed binning scheme. This is amplitude-histogram entropy — distinct from spectral/wavelet entropy.

### Wavelet entropy

Discrete db4 decomposition; sub-band relative energies → Shannon entropy of the energy distribution.

```python
import pywt   # OPTIONAL — guard with check_backend("pywt")
level = round(np.log2(fs)) - 3              # e.g. fs=100 → 4 levels
coeffs = pywt.wavedec(x, 'db4', level=level)
energies = np.array([np.sum(c**2) for c in coeffs])
p = energies / energies.sum()
WE = -np.sum(p[p > 0] * np.log(p[p > 0]))
WE_norm = WE / np.log(len(p))               # bound to [0,1] for cross-study comparison
```

`level = round(log2(fs)) - 3` ties decomposition depth to sampling rate so sub-bands roughly map to canonical EEG bands. High WE = flat (disordered) spectrum across sub-bands. Always report the (fixed) decomposition level.

### Hilbert-Huang spectral entropy (HHSE)

EMD → Hilbert marginal spectrum → Shannon entropy over a frequency band. **Mitigate EMD edge effects by tripling the signal and keeping the middle third.**

```python
from PyEMD import EMD     # OPTIONAL — guard with check_backend("PyEMD")
from scipy.signal import hilbert
x3 = np.concatenate([x, x, x])              # triple to reduce EMD end-effects
imfs = EMD()(x3)
# instantaneous amplitude/frequency per IMF → marginal spectrum
amp = np.abs(hilbert(imfs, axis=-1))
inst_freq = (np.diff(np.unwrap(np.angle(hilbert(imfs, axis=-1)), axis=-1))
             / (2*np.pi) * fs)
# build marginal spectrum over f_bin (default [1, 30] Hz, df ≈ fs/1000),
# restrict to the MIDDLE THIRD (the original signal), then Shannon entropy.
```

EMD is data-adaptive (no fixed basis) but slow and mode-mixing-prone — use HHSE only when fixed-band wavelet entropy is insufficient. If `PyEMD`/`emd` is missing, **fall back to db4 wavelet entropy** and log the substitution. Default `f_bin = [1, 30]` Hz, frequency resolution `df = fs/1000`.

## Phase E — Recurrence Quantification Analysis (RQA)

Phase-space reconstruction `x_i = (u_i, u_{i+tau}, ..., u_{i+(m-1)tau})`; recurrence point `R_ij = 1` if distance ≤ threshold.

```python
import neurokit2 as nk   # OPTIONAL — guard with check_backend("neurokit2")
rqa, _ = nk.complexity_rqa(x, dimension=3, delay=1, tolerance='sd')
# RR = recurrence rate; DET = % recurrence points on diagonals length >= Lmin;
# ENTR = Shannon entropy of diagonal-line-length distribution; L = mean diagonal length.
```

Defaults: embedding `m=3`, delay `tau=1`, threshold `= 0.5 * SD` of the segment (fixed-fraction-of-SD; alternative is fixed recurrence rate, e.g. 5–10 %), `Lmin=2` for DET/ENTR.

Outputs and meaning:
- **RR** — recurrence rate (density of recurrent states); **increases** under deep anesthesia.
- **DET** — determinism (fraction of recurrences on diagonal lines): predictability of the dynamics.
- **ENTR** — Shannon entropy of diagonal-line lengths: complexity of deterministic structure.
- **L** — mean diagonal line length: average prediction horizon.

Set `delay` from mutual information (first minimum) and `dimension` from false-nearest-neighbours (FNN). `nolds` has no FNN — use `pyunicorn` for FNN, or `neurokit2.complexity_delay` / `complexity_dimension` (MI-delay and FNN-dimension estimators). If `neurokit2` is missing and no RQA backend is available, skip RQA with a `pip install neurokit2` hint.

## Phase F — Scale-free dynamics / criticality

Present **both** complementary routes; report whichever the claim requires and convert via `H = (beta - 1) / 2` (with `beta ∈ [1, 3]`).

```python
# (1) Aperiodic 1/f slope — modern standard (see eeg-spectral for the full path).
# Import name differs by version: FOOOF 2.x = `specparam.SpectralModel`, legacy 1.x = `fooof.FOOOF`.
# VERIFIED: `get_params('aperiodic','exponent')` returns the exponent in BOTH versions, whereas the
# `aperiodic_params_` attribute exists ONLY in fooof 1.x and raises AttributeError on specparam 2.x.
try:
    from specparam import SpectralModel as SpecModel   # FOOOF 2.x
except ImportError:
    from fooof import FOOOF as SpecModel               # legacy 1.x
sm = SpecModel(aperiodic_mode='fixed')                 # 'knee' for longer / low-freq ranges
sm.fit(freqs, psd, freq_range=[1, 40])
beta = sm.get_params('aperiodic', 'exponent')          # aperiodic exponent ≈ spectral-slope beta

# (2) DFA / Hurst — z-score each (long) window first
import nolds   # OPTIONAL — guard with check_backend("nolds")
xz = (x - x.mean()) / x.std()
dfa_alpha = nolds.dfa(xz)
hurst = nolds.hurst_rs(xz)                     # or ant.detrended_fluctuation(xz)
H_from_beta = (beta - 1) / 2.0
```

Scaling analyses need **longer epochs** (`SCALE_WINDOW` ≥ 16 s vs 5 s for entropy) and z-scoring per window. Operationalize criticality as spectral-slope fitting `S(f) = alpha * f^(-beta)`, deriving Hurst `H = (beta-1)/2`.

**DFA on broadband ≠ LRTC — run DFA on the narrow-band amplitude envelope.** The DFA route above (broadband z-scored signal) conflates the aperiodic 1/f slope with long-range temporal correlations and is **not** the canonical neuroscience criticality measure. LRTC (long-range temporal correlations) is DFA on the **amplitude envelope of a narrow-band-filtered oscillation**: band-pass (e.g. alpha 8–13 Hz) → Hilbert envelope → DFA on that envelope. Use this whenever the claim is LRTC/criticality of a rhythm rather than aperiodic 1/f.

```python
from scipy.signal import hilbert
import nolds, numpy as np   # OPTIONAL — guard with check_backend("nolds")
band = mne.filter.filter_data(x, fs, l_freq=8, h_freq=13)   # narrow-band, e.g. alpha
env = np.abs(hilbert(band))                                   # amplitude envelope
# window-size fit range: ~5 s (≥6 cycles at the low edge) up to 0.1 × recording length;
lrtc_alpha = nolds.dfa(env)                                   # verify log-log linearity of the fit
```

- Fit-range lower bound ≥ ~5 s **and** ≥ 6 cycles of the band's low edge; upper bound ≤ 0.1 × recording length; verify the log–log fluctuation plot is linear before trusting the exponent.
- Healthy alpha LRTC exponent is ~0.6–0.8 (broadband DFA is a different quantity — do not interpret them interchangeably).
- Cite: Hardstone, R., Poil, S.-S., Schiavone, G., Jansen, R., Nikulin, V. V., Mansvelder, H. D., & Linkenkaer-Hansen, K. (2012). Detrended fluctuation analysis: a scale-free view on neuronal oscillations. Frontiers in Physiology, 3, 450.

### Neuronal avalanches and edge-of-chaos criticality

A concrete avalanche-detection recipe for scalp/MEG (this skill previously shipped none): z-score each channel, threshold at ±2.5–3 SD to produce point events, **bin at the mean inter-event interval** (not an arbitrary bin width), define an avalanche as a run of consecutive non-empty bins, and characterize the size and duration distributions.

```python
import numpy as np
z = (data - data.mean(axis=-1, keepdims=True)) / data.std(axis=-1, keepdims=True)
events = np.abs(z) > 2.75                              # ±2.75 SD point events, (n_ch, n_times)
times = np.where(events.any(axis=0))[0]
bin_w = int(round(np.mean(np.diff(times))))           # bin = mean inter-event interval (IEI)
# bin into bin_w, runs of non-empty bins = avalanches; collect size (#events) and duration (#bins)
```

- Fit size (`P(s) ∝ s^-1.5`) and duration (`P(d) ∝ d^-2.0`) distributions by **maximum likelihood with a Clauset KS goodness-of-fit** (`powerlaw` package) — **never** log-log least-squares, which biases exponents.
- Estimate the branching ratio `sigma = events_{t+1} / events_t` (`sigma ≈ 1` at criticality) and check the crackling-noise scaling relation between the size, duration, and average-size-given-duration exponents as a self-consistency test.
- Pair with an **edge-of-chaos** chaoticity estimate (modified 0–1 test, `K ∈ [0, 1]`) as a complementary criticality notion to the avalanche/branching view.
- Backend: `powerlaw` (optional, graceful-degrade per Phase B).
- Cite: Shriki, O., Alstott, J., Carver, F., Holroyd, T., Henson, R. N. A., Smith, M. L., Coppola, R., Bullmore, E., & Plenz, D. (2013). Neuronal avalanches in the resting MEG of the human brain. Journal of Neuroscience, 33(16), 7079–7090. Toker, D., Pappas, I., Lendner, J. D., et al. (2022). Consciousness is supported by near-critical slow cortical electrodynamics. PNAS, 119(7), e2024455119 (edge-of-chaos).

If neither `specparam`/`fooof` nor `nolds` is available, skip the scale-free route and log it.

### Perturbational complexity index (PCI / PCIst) — consciousness biomarker

The field-standard consciousness biomarker, fundamentally different from the per-channel 1-D LZC above because it quantifies the complexity of the brain's *response to a perturbation*. **Gate it strictly on a TMS/perturbation tick in `ANALYSIS_PLAN.md`** — it is not computable from spontaneous EEG and must not be run on resting data. Classic PCI: deliver single-pulse TMS, average the TMS-evoked potential, source-model it, build a space-by-time binary matrix of significantly-active sources (bootstrap vs pre-stimulus baseline), Lempel-Ziv-compress that 2-D matrix, and normalize by the source entropy (empirical consciousness cutoff `PCI* ≈ 0.31`).

```python
# Prefer the dependency-light PCIst variant (renzocom/PCIst): no source modelling required.
# SVD dimensionality reduction of the evoked response → per-component state-transition
# quantifiers summed over a post-stimulus window, divided by the baseline window value.
from PCIst import pci_st          # OPTIONAL — guard with check_backend; orders of magnitude faster than PCI
par = {'baseline_window': (-400, -50), 'response_window': (0, 300), 'k': 1.2, 'min_snr': 1.1}
pci = pci_st.calc_PCIst(evoked_data, times, **par)   # evoked_data: (n_channels, n_times)
```

- Prefer **PCIst** over classic PCI: SVD-based, no source model, orders of magnitude faster, and it generalizes beyond TMS to sensory and intracranial responses.
- Backend: `PCIst` (renzocom/PCIst, optional, graceful-degrade per Phase B).
- Cite: Casali, A. G., Gosseries, O., Rosanova, M., Boly, M., Sarasso, S., Casali, K. R., Casarotto, S., Bruno, M.-A., Laureys, S., Tononi, G., & Massimini, M. (2013). A theoretically based index of consciousness independent of sensory processing and behavior. Science Translational Medicine, 5(198), 198ra105. Comolatti, R., Pigorini, A., Casarotto, S., et al. (2019). A fast and general method to empirically estimate the complexity of brain responses to transcranial and intracranial stimulations. Brain Stimulation, 12(5), 1280–1289 (PCIst).

## Phase G — Spatial complexity (Omega / NSC / LCD)

A multivariate metric over the PCA variance spectrum of the channel covariance. Pure numpy — no optional dependency. **Average reference is mandatory.**

```python
import numpy as np
raw.set_eeg_reference('average', projection=False)
data = raw.get_data()                          # (n_channels, n_times), per window
C = np.cov(data)                               # channels as variables
ev = np.linalg.eigvalsh(C)
ev = ev[ev > 0]
p = ev / ev.sum()                              # normalized eigenvalue spectrum (prob. dist.)
H = -np.sum(p * np.log(p))                     # guard log(0): drop/clip zero eigenvalues
omega = np.exp(H)                              # Omega complexity (Wackermann 1996)
nsc = H / np.log(data.shape[0])                # normalized spatial complexity ∈ [0, 1]

# LCD: leave-one-channel-out contribution of channel i
lcd = np.array([nsc - nsc_without_channel(data, i) for i in range(data.shape[0])])
```

- **Omega** = `exp(eigenvalue-entropy)`; **NSC** = `entropy / log(M)` bounded `[0,1]` (M = #channels).
- **LCD** (local complexity differential) = whole-head SC minus SC-without-channel-i; quantifies one electrode's contribution. Can be computed per ROI (frontal / occipital / parietal / L-R hemisphere) or whole-head.
- Interpretation: **high spatial complexity ⇒ many mutually-independent processes ⇒ low global functional connectivity.** A useful complement to coherence/PLV/wPLI in eeg-connectivity, which are degraded by reference choice, volume conduction, and redundancy.
- Out of scope but conceptually here: **Synchronization Likelihood (SL)**, a multivariate state-space coupling measure (eeg-connectivity points here). It shares the embedding machinery and requires: embedding dimension, time delay (first AMI minimum / autocorrelation), Theiler window (exclude temporally close points), `k` nearest neighbours, and `Pref` (range `[Pref, 1]`). Not in MNE core — document with these hyperparameters if implemented.

## Phase H — Outputs and sanity checks

### Per-subject files
- `complexity-stage/<sub>/<sub>-<cond>-<metric>-timecourse.npz` — `tc` (n_channels × n_windows), `times`, `ch_names`, `metric`, params.
- `complexity-stage/<sub>/<sub>-<cond>-<metric>-summary.json` — per-channel mean ± SD across windows, plus condition-level grand mean.
- `complexity-stage/<sub>/<sub>-spatial.json` — Omega / NSC / LCD per window (if `spatial`).

### Group summary
- `complexity-stage/group/complexity_summary.csv` — one row per subject × condition × channel (or ROI) with the metric value, for `eeg-stats`.

### Append to FINDINGS.md
```markdown
## Complexity: [metric] [condition contrast]
- Metric: [PE / SampEn / LZC / ...], backend: [neurokit2 / antropy / ...]
- Window: 5 s / 3 s overlap; m=2, r=0.2*SD (per window)
- [condition A] = [mean ± SD] vs [condition B] = [mean ± SD]
- Direction: [e.g. complexity decreases under deep anesthesia / higher eyes-open]
- Skipped metrics (missing backend): [list with pip-install hints, if any]
```

### Sanity checks — all must pass
- [ ] `DATASET_BRIEF.md` ticks Complexity (skill was correctly invoked).
- [ ] `BACKEND_RESOLUTION.md` lists each optional lib as available / missing; every skipped metric is logged with a `pip install` hint.
- [ ] Every subject has a complexity time course for all conditions and channels (for metrics whose backend was available).
- [ ] Normalized metrics (PE, LZC, PLZC, NSC) are within `[0, 1]`; SampEn/ApEn ≥ 0.
- [ ] No NaN/Inf (guard `log(0)`; drop empty histogram bins / zero eigenvalues).
- [ ] `r` (SampEn/ApEn) was recomputed per window from that window's SD — not a global SD.
- [ ] PLZC normalization base is `m!` (not 2); LZC base is 2.
- [ ] Spatial complexity used **average reference**.
- [ ] Scale-free metrics used the longer (≥16 s) windows and z-scored input.
- [ ] **Built-in validation**: eyes-open resting EEG shows higher temporal complexity (PE/LZC/SampEn) than eyes-closed; if the data has this contrast, confirm the expected direction.
- [ ] BACKEND_RESOLUTION.md and METRIC_SELECTION.md exist.

## Critical Rules

- **Never** crash the stage on a missing optional library — guard every external import with `check_backend(...)`, log the skip, surface it in AUDIT, and continue with the available metrics.
- **Never** use `antropy.sample_entropy`/`app_entropy` when a specific tolerance is required — antropy hardcodes `r = 0.2 * SD`. Use `neurokit2` or `EntropyHub` to set `r`.
- **Never** compute `r` for SampEn/ApEn from a global SD — recompute it from each window's own SD, inside the window loop.
- **Never** normalize PLZC (or any >2-symbol LZC) with base 2 — the normalization base must be `m!`. Mismatched base silently produces uninterpretable values.
- **Never** compute LZC/PLZC/SampEn across channels — these are per-channel 1-D time-series metrics. Only spatial complexity (Omega/NSC) operates across channels.
- **Never** compare a complexity value across windows/conditions of different length — `c(n)`, RR, and entropy estimates all depend on `n`. Hold window length fixed.
- **Never** compute spatial complexity without an average reference first.
- **Never** report Shannon-amplitude or wavelet entropy without stating the (fixed) bin count / decomposition level — both are bin/level dependent.
- **Never** run DFA/Hurst/aperiodic-slope on short (≤5 s) entropy-sized windows — use ≥16 s windows; scaling exponents are unstable otherwise.
- **Never** call broadband DFA an LRTC/criticality measure — LRTC is DFA on the **narrow-band amplitude envelope** (band-pass → Hilbert → DFA); broadband DFA conflates the aperiodic 1/f slope with LRTC.
- **Never** recompute the SampEn tolerance `r` per scale in MSE — compute it once on the scale-1 SD and hold it fixed; on AEA's 5 s windows default to **RCMSE** (plain MSE is undefined at coarse scales).
- **Never** fit avalanche size/duration distributions by log-log least-squares — use maximum likelihood with a Clauset KS test, and bin at the mean inter-event interval (not an arbitrary bin width).
- **Never** run PCI/PCIst on spontaneous EEG — it is gated on a TMS/perturbation tick and operates on the evoked response.
- **Never** compare multichannel LZc/ACE/SCE across montages without per-subject phase-shuffled-surrogate normalization — raw values scale with channel count and spectral content.
- **Never** trust correlation dimension or Lyapunov exponents on short or noisy EEG without surrogate-data testing.

## Domain Knowledge (distilled from EEG complexity / nonlinear-dynamics literature)

### Lempel-Ziv complexity (Lempel & Ziv 1976; Aboy et al. 2006)
- Coarse-grain the signal to a binary string (median threshold is the amplitude-robust default), parse into the minimal set of distinct substrings, count `c(n)`, normalize `LZC = c(n) / (n / log2(n))` so values are ≈ `[0,1]` and comparable across epoch lengths.
- LZC tracks the rate of new-pattern generation — it drops under anesthesia/loss of consciousness and rises in alert, complex states.
- Cite: Lempel, A., & Ziv, J. (1976). On the complexity of finite sequences. IEEE Transactions on Information Theory, 22(1), 75–81. Aboy, M., Hornero, R., Abásolo, D., & Álvarez, D. (2006). Interpretation of the Lempel-Ziv complexity measure in the context of biomedical signal analysis. IEEE Transactions on Biomedical Engineering, 53(11), 2282–2288.

### Permutation entropy and PLZC (Bandt & Pompe 2002; Bai et al. 2015)
- Permutation entropy replaces amplitude values with ordinal patterns (rank order of `m` consecutive samples), making it amplitude-blind and robust to monotonic noise; `PE = H / ln(m!)`.
- PLZC = ordinal symbolization + LZ parse, normalized by `log_{m!}(n)`; combines PE's amplitude-independence with LZC's pattern-novelty sensitivity and is more noise-robust than amplitude-thresholded LZC.
- Default `order/m`: PE order 3 (3–7 typical), PLZC `m=4`; both require `m! ≪ window length`.
- Cite: Bandt, C., & Pompe, B. (2002). Permutation entropy: a natural complexity measure for time series. Physical Review Letters, 88(17), 174102. Bai, Y., Liang, Z., & Li, X. (2015). A permutation Lempel-Ziv complexity measure for EEG analysis. Biomedical Signal Processing and Control, 19, 102–114.

### Sample vs approximate entropy (Richman & Moorman 2000; Pincus 1991)
- ApEn counts self-matches and is biased toward regularity, with strong dependence on record length. SampEn excludes self-matches (`B_{m+1}/B_m` ratio, strict `< r`), removing this bias and giving more consistent estimates across data lengths — prefer SampEn.
- Standard parameters: `m = 2`, `r = 0.2 * SD` (Richman–Moorman); some EEG studies use `0.15 * SD`. Chebyshev (max-norm) distance. `r` must be expressed relative to the SD of the same segment.
- Cite: Richman, J. S., & Moorman, J. R. (2000). Physiological time-series analysis using approximate entropy and sample entropy. American Journal of Physiology - Heart and Circulatory Physiology, 278(6), H2039–H2049. Pincus, S. M. (1991). Approximate entropy as a measure of system complexity. Proceedings of the National Academy of Sciences, 88(6), 2297–2301.

### Wavelet entropy (Rosso et al. 2001)
- Compute relative energies of DWT sub-bands, then Shannon entropy of that distribution; quantifies spectral disorder (flat spectrum across sub-bands ⇒ high wavelet entropy). db4 with depth tied to `fs` maps sub-bands onto canonical EEG bands.
- Cite: Rosso, O. A., Blanco, S., Yordanova, J., Kolev, V., Figliola, A., Schürmann, M., & Başar, E. (2001). Wavelet entropy: a new tool for analysis of short duration brain electrical signals. Journal of Neuroscience Methods, 105(1), 65–75.

### Hilbert-Huang transform (Huang et al. 1998)
- EMD decomposes a signal into Intrinsic Mode Functions adaptively (no fixed basis); the Hilbert transform of each IMF yields instantaneous amplitude/frequency, summed over time into a marginal spectrum whose Shannon entropy is HHSE. EMD suffers end-effects and mode mixing — pad (e.g. triple) the signal and discard boundary thirds.
- Cite: Huang, N. E., Shen, Z., Long, S. R., Wu, M. C., Shih, H. H., Zheng, Q., Yen, N.-C., Tung, C. C., & Liu, H. H. (1998). The empirical mode decomposition and the Hilbert spectrum for nonlinear and non-stationary time series analysis. Proceedings of the Royal Society of London A, 454(1971), 903–995.

### Recurrence quantification analysis (Marwan et al. 2007)
- A recurrence plot marks when a trajectory revisits a neighbourhood in reconstructed phase space; RQA quantifies its texture: RR (density), DET (diagonal structure ⇒ determinism), L (mean diagonal length ⇒ predictability), ENTR (diagonal-length entropy ⇒ complexity). Set embedding dimension via FNN and delay via mutual information; threshold via fixed-fraction-of-SD or fixed recurrence rate.
- Cite: Marwan, N., Romano, M. C., Thiel, M., & Kurths, J. (2007). Recurrence plots for the analysis of complex systems. Physics Reports, 438(5–6), 237–329.

### Scale-free dynamics, DFA, and the slope-Hurst relation (Peng et al. 1994; He 2014; Donoghue et al. 2020)
- EEG power spectra follow `S(f) ∝ f^(-beta)`; the aperiodic exponent (specparam/FOOOF) is the modern, oscillation-corrected way to estimate `beta`. DFA gives the scaling exponent `alpha`; for fractional Gaussian/Brownian processes Hurst `H = (beta - 1) / 2` with `beta ∈ [1, 3]`. Scaling estimates require long segments and (for DFA) detrending; z-score each window.
- Cite: Peng, C.-K., Buldyrev, S. V., Havlin, S., Simons, M., Stanley, H. E., & Goldberger, A. L. (1994). Mosaic organization of DNA nucleotides. Physical Review E, 49(2), 1685–1689. He, B. J. (2014). Scale-free brain activity: history, mechanisms, cognition, and disease. Trends in Cognitive Sciences, 18(9), 480–487. Donoghue, T., Haller, M., Peterson, E. J., et al. (2020). Parameterizing neural power spectra into periodic and aperiodic components. Nature Neuroscience, 23(12), 1655–1665.

### Dispersion and multiscale entropy (Rostaghi & Azami 2016; Costa et al. 2002; Wu et al. 2014)
- Dispersion entropy maps amplitudes through the normal CDF into `c` classes and counts `c^m` dispersion patterns: `O(N)`, noise-tolerant, and amplitude-aware (PE discards amplitude). Multiscale entropy coarse-grains across scales `tau` and reports the area under the SampEn-vs-scale curve; the tolerance `r` is fixed at the scale-1 SD across all scales, and RCMSE (composite match-count averaging) is the robust short-window variant. RCMDE is the dispersion-entropy multiscale form for long EEG.
- Cite: Rostaghi, M., & Azami, H. (2016). Dispersion entropy: a measure for time-series analysis of complexity. IEEE Signal Processing Letters, 23(5), 610–614. Costa, M., Goldberger, A. L., & Peng, C.-K. (2002). Multiscale entropy analysis of complex physiologic time series. Physical Review Letters, 89(6), 068102. Wu, S.-D., et al. (2014). Time series analysis using composite multiscale entropy. Physics Letters A, 378(20), 1369–1374.

### Multichannel signal diversity and perturbational complexity (Schartner et al. 2015; Casali et al. 2013; Comolatti et al. 2019)
- Spatiotemporal LZc (Hilbert-binarized channels-by-time matrix) plus ACE (differentiation: variability of active-channel sets) and SCE (integration: variability of synchronous-channel sets) drop under propofol and rise under psychedelics; normalize against phase-shuffled surrogates before cross-montage comparison. PCI perturbs the cortex (TMS), compresses the source-space spatiotemporal response, and normalizes by source entropy as an explicit consciousness biomarker; PCIst is the source-model-free SVD variant.
- Cite: Schartner, M., et al. (2015). Complexity of multi-dimensional spontaneous EEG decreases during propofol-induced general anaesthesia. PLoS ONE, 10(8), e0133532. Casali, A. G., et al. (2013). A theoretically based index of consciousness independent of sensory processing and behavior. Science Translational Medicine, 5(198), 198ra105. Comolatti, R., et al. (2019). A fast and general method to empirically estimate the complexity of brain responses to transcranial and intracranial stimulations. Brain Stimulation, 12(5), 1280–1289.

### Criticality: LRTC and neuronal avalanches (Hardstone et al. 2012; Shriki et al. 2013; Toker et al. 2022)
- Long-range temporal correlations are quantified by DFA on the *amplitude envelope of a narrow-band oscillation* (e.g. alpha 8–13 Hz, exponent ~0.6–0.8) — not broadband DFA, which conflates the aperiodic slope with LRTC. Neuronal avalanches are runs of supra-threshold point events binned at the mean inter-event interval; criticality is evidenced by power-law size (~-1.5) and duration (~-2.0) distributions (ML-fit + Clauset KS), a branching ratio `sigma ≈ 1`, and the crackling-noise scaling relation. Edge-of-chaos chaoticity (0–1 test) is a complementary criticality view.
- Cite: Hardstone, R., et al. (2012). Detrended fluctuation analysis: a scale-free view on neuronal oscillations. Frontiers in Physiology, 3, 450. Shriki, O., et al. (2013). Neuronal avalanches in the resting MEG of the human brain. Journal of Neuroscience, 33(16), 7079–7090. Toker, D., et al. (2022). Consciousness is supported by near-critical slow cortical electrodynamics. PNAS, 119(7), e2024455119.

### Spatial complexity: Omega complexity and multichannel complexity (Wackermann 1996; Saito et al. 1998)
- Treat channels as variables, take the covariance eigenvalue spectrum, normalize to a probability vector and compute its entropy. Omega `= exp(entropy)`; NSC `= entropy / log(M)` ∈ `[0,1]`. High spatial complexity = many independent processes = low global functional connectivity — a reference/volume-conduction-robust complement to pairwise connectivity. Average reference is required so the spectrum reflects topography, not the reference choice.
- Cite: Wackermann, J. (1996). Beyond mapping: estimating complexity of multichannel EEG recordings. Acta Neurobiologiae Experimentalis, 56(1), 197–208. Saito, N., Kuginuki, T., Yagyu, T., Kinoshita, T., Koenig, T., Pascual-Marqui, R. D., Kochi, K., Wackermann, J., & Lehmann, D. (1998). Global, regional, and local measures of complexity of multichannel electroencephalography in acute, neuroleptic-naive, first-break schizophrenics. Biological Psychiatry, 43(11), 794–802.

### Clinical/validation conventions (anesthesia depth; eyes-open/closed)
- Across LZC, PLZC, SampEn, PE, wavelet/HHT entropy and RQA-DET/ENTR, complexity **decreases** (and RR **increases**) under deep anesthesia vs awake — the canonical demonstration. Eyes-open resting EEG should show **higher** complexity than eyes-closed; use this as a built-in sanity check.
- Window convention: 5 s windows with overlap (e.g. 2 s step) for entropy/LZC/RQA; ≥16 s for scale-free/Hurst.
- Cite: Zhang, X.-S., Roy, R. J., & Jensen, E. W. (2001). EEG complexity as a measure of depth of anesthesia for patients. IEEE Transactions on Biomedical Engineering, 48(12), 1424–1433.

## Failure Modes

| Symptom | Action |
|---|---|
| `ANALYSIS_PLAN.md` missing or unfrozen | Stop. Ask user to fill and freeze the plan. |
| `DATASET_BRIEF.md` does not tick Complexity | Skill out of scope — return to dispatcher without running. |
| `antropy` not installed | `pip install antropy`. Log in BACKEND_RESOLUTION.md; for PE/LZC fall back to the numpy implementation, else skip metric. |
| `neurokit2` not installed | `pip install neurokit2`. SampEn/ApEn with custom `r`, PLZC, and RQA are unavailable — log skip + hint. |
| `EntropyHub` not installed | `pip install EntropyHub`. Use as the alternative tunable-`r` backend; if also missing, skip tunable-`r` SampEn/ApEn. |
| `nolds` not installed | `pip install nolds`. DFA/Hurst/corr-dim/Lyapunov unavailable; use `antropy.detrended_fluctuation` for DFA if antropy present, else skip scale-free. |
| `mne-features` not installed | `pip install mne-features`. Fractal/Hjorth/line-length features for eeg-decoding skipped — log and continue. |
| `pywt` not installed | `pip install pywt`. Wavelet entropy skipped (no clean numpy DWT fallback). |
| `PyEMD`/`emd` not installed | `pip install EMD-signal`. HHSE skipped — fall back to db4 wavelet entropy and log the substitution. |
| `specparam`/`fooof` not installed | `pip install specparam`. Aperiodic-slope route skipped; use DFA/Hurst (nolds) for scale-free instead. |
| `EntropyHub` not installed (DispEn / MSE) | `pip install EntropyHub`. DispEn skipped (fall back to PE, losing amplitude info); MSE/RCMSE skipped — log + hint. |
| `powerlaw` not installed | `pip install powerlaw`. Avalanche size/duration ML fit skipped — do NOT substitute log-log least-squares; log skip. |
| `PCIst` not installed | `pip install PCIst` (renzocom/PCIst). PCI/PCIst skipped — log + hint; never approximate with per-channel LZC. |
| `pci`/`pcist` requested but no perturbation tick | Out of scope — PCI needs a TMS/sensory perturbation; do not run on spontaneous EEG. |
| MSE/RCMSE entropy `inf`/undefined at coarse scales | Plain MSE on short windows has no `m+1` matches. Switch to RCMSE and report scales-defined. |
| LRTC exponent equals broadband DFA / implausible | DFA was run on broadband, not the narrow-band amplitude envelope. Band-pass → Hilbert envelope → DFA. |
| SampEn/ApEn give identical results regardless of `r` | You are using `antropy` (hardcoded r=0.2*SD). Switch to `neurokit2`/`EntropyHub`. |
| PLZC values look wrong / out of range | Normalization base is 2 instead of `m!`. Use `nk.complexity_lempelziv(..., permutation=True)` or renormalize by `log2/log(m!)`. |
| `nan`/`inf` in entropy | A histogram/eigenvalue/probability bin is 0 → `log(0)`. Drop empty bins, clip zero eigenvalues (e.g. to 1e-20). |
| SampEn = `inf` or `nan` | No template matches at `m+1` (window too short or `r` too small). Lengthen window or raise `r`. |
| Complexity differs across conditions but so does amplitude/montage | Amplitude confound. Switch to PE or PLZC (amplitude-blind) and re-test. |
| Complexity drifts with window length | Window lengths differ across conditions. Fix `WINDOW`; resample to a common `fs`. |
| DFA/Hurst exponent unstable or implausible (<0 or >1.5) | Window too short or not detrended/z-scored. Use ≥16 s windows, z-score, check fit linearity. |
| Spatial complexity dominated by one channel / looks reference-driven | Average reference not applied, or a bad channel inflates a covariance eigenvalue. Re-reference; interpolate/drop the bad channel. |
| EMD extremely slow / mode mixing | HHSE is expensive — downsample, limit IMFs, or fall back to db4 wavelet entropy. |
| RQA out of memory (large recurrence matrix) | Reduce window length or downsample; recurrence matrix is `O(N^2)`. |

## Cross-references

- Inputs: `ANALYSIS_PLAN.md`, `DATASET_BRIEF.md`, `preprocess-stage/` / `ica-stage/` / `epoch-stage/`, `ENVIRONMENT.json`, `channel_mapping.json`
- Outputs: `complexity-stage/<sub>/*-timecourse.npz`, `complexity-stage/<sub>/*-summary.json`, `complexity-stage/group/complexity_summary.csv`, `complexity-stage/BACKEND_RESOLUTION.md`, `complexity-stage/METRIC_SELECTION.md`, `FINDINGS.md`
- Related: `eeg-spectral` (aperiodic 1/f slope via specparam — shared scale-free path), `eeg-connectivity` (spatial complexity is a global-state complement to pairwise connectivity; multivariate nonlinear coupling / Synchronization Likelihood documented here), `eeg-tfr` (wavelet/HHT time-frequency), `eeg-decoding` (entropy/fractal/Hjorth features via `mne-features` feed the tabular feature matrix)
- Next: `eeg-stats` for group comparison of complexity values/time courses, `eeg-figure` for complexity time-course plots and topomaps, `eeg-methods-text` for the complexity paragraph, `eeg-recipe` for a ready "complexity-tracking" recipe (preprocess → average reference for spatial SC → windowed metrics → condition contrast)
