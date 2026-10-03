---
name: eeg-connectivity
description: "Compute functional connectivity per condition: wPLI, PLV, coherence, imaginary coherence, Granger causality, or phase-amplitude coupling on sensor-space epochs (or source-space if eeg-source ran). Optional skill — only invoked if DATASET_BRIEF.md ticks Connectivity."
argument-hint: "[project-dir] [— metric: wpli|plv|coh|imcoh|gc|pac] [— space: sensor|source]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-connectivity: functional connectivity

## Context: $ARGUMENTS

## Constants

- **BACKEND = `mne_connectivity`** (Python). The primary backend for connectivity analysis.
- **ESTIMATOR FORK** — pick by design:
  - Resting / whole-epoch FC → `spectral_connectivity_epochs` (epochs are the averaging dimension → one value per band per pair).
  - Event-related / time-resolved task FC → `spectral_connectivity_time` (returns per-pair freq×time; phase consistency is computed *across trials* at each time-frequency point).
- **ANALYSIS_RANGE / SMOOTHING defaults** (when none specified): 1–30(–45) Hz, multitaper spectral smoothing ~1–2 Hz; crop epochs to the a-priori task window *before* FC; average within the hypothesis band (`faverage=True`). Band edges and time window MUST be fixed a priori to avoid double-dipping.
- **METRIC = `wpli`** by default (debiased wPLI; less volume-conduction-biased than coherence).
- **SPACE = `sensor`** unless `eeg-source` produced source estimates → `source`.
- **FREQ_BANDS = read from DATASET_BRIEF or default**: delta (1–4 Hz), theta (4–8 Hz), alpha (8–13 Hz), beta (13–30 Hz), gamma (30–45 Hz).
- **OUTPUT_DIR = `connectivity-stage/`** — Create if missing.
- **N_JOBS = `4`** — parallel jobs for spectral connectivity computation.
- **SEED = read from ANALYSIS_PLAN.md**, default `42`.

> Override: `/eeg-connectivity projects/my-study — metric: plv — space: source — backend: mne`

## Required Inputs

Before running, these must exist:

1. `ANALYSIS_PLAN.md` — frozen, with connectivity claims (if any). **Stop if missing or unfrozen.**
2. `epochs-stage/` — cleaned, epoched `.fif` files per subject per condition.
3. `ENVIRONMENT.json` — to resolve backend.
4. `channel_mapping.json` — if claim ROI uses 10-20 names but data uses numbered channels.
5. (Optional) `source-stage/` — source-space time courses if `— space: source`.

## Phase A — Metric selection and validation

1. Read ANALYSIS_PLAN.md for connectivity-related claims.
2. Validate the requested metric against the data:
   - **wPLI** (debiased weighted phase lag index): requires epoched data, insensitive to volume conduction.
   - **PLV** (phase-locking value): requires epoched data, sensitive to volume conduction — warn user.
   - **Coherence** (`coh`): magnitude-squared coherence, confounded by volume conduction at sensor level.
   - **Imaginary coherence** (`imcoh`): imaginary part of coherency, robust to volume conduction.
   - **Granger causality** (`gc`): directional, requires stationary time series, best via FieldTrip or SIFT.
   - **Phase-amplitude coupling** (`pac`): cross-frequency, requires long epochs — different pipeline (see Phase G).

### Metric coverage (course metric → MNE)

| Course metric | MNE method string / function | Directed? | VC-robust? | Notes |
|---|---|---|---|---|
| Magnitude-squared coherence (COH) | `coh` | no | **no** | confounded by VC; pair with `imcoh` on sensor data |
| Imaginary coherency | `imcoh` | no | **yes** | imaginary part only; Nolte 2004 |
| PLV / mean phase coherence | `plv`, `ciplv` (corrected imaginary PLV) | no | `plv` **no**, `ciplv` **yes** | `ciplv` discards zero-lag |
| Pairwise phase consistency | `ppc` | no | no | unbiased PLV-like (Vinck 2010) |
| PLI | `pli`, `pli2_unbiased` | no | **yes** | sign of phase lag only |
| wPLI | `wpli`, `wpli2_debiased` | no | **yes** | debiased version is the default headline metric |
| Phase slope index (PSI) | `mne_connectivity.phase_slope_index()` | **yes** | yes | directed phase metric; Nolte 2008 |
| Granger causality | `gc`, `gc_tr` (time-reversed control) | **yes** | no | needs stationarity/long data; prefer source space |
| Mutual information / transfer entropy | — | TE: yes | — | **NOT in MNE core** → external (e.g. IDTxl); do not silently claim |
| Synchronization Likelihood (nonlinear, multivariate) | — | no | — | **NOT in MNE** → state-space/embedding tool; see complexity skill |

Not every method string is available in both estimators: `imcoh`, `wpli2_debiased`, `pli2_unbiased`, and `ppc` are `spectral_connectivity_epochs`-only; `spectral_connectivity_time` supports `coh`, `plv`, `ciplv`, `pli`, `wpli`, `gc`, `gc_tr` (use these for time-resolved FC). Do not claim to compute MI, transfer entropy, or Synchronization Likelihood with `mne_connectivity` — they require external packages and are out of scope here.

3. If `SPACE = source` and `source-stage/` does not exist → STOP, instruct user to run `eeg-source` first.
4. If `SPACE = source`, apply signal leakage correction (orthogonalization) before computing connectivity (see Domain Knowledge: Colclough et al. 2015).

### Volume conduction — the central sensor-space pitfall

One brain source spreads instantaneously (zero phase lag) to many electrodes, so sensor-level coupling can reflect a *shared source* rather than true interaction; it is also reference-dependent. Two complementary mitigation routes ("double insurance"):

1. **Spatial filtering before FC** — either source localization (label/ROI time courses, see `eeg-source`) **or** the surface Laplacian / Current Source Density:
   ```python
   from mne.preprocessing import compute_current_source_density
   epochs_csd = compute_current_source_density(epochs)  # Perrin spherical-spline CSD
   ```
   CSD is **reference-independent** and suppresses VC with few assumptions, but lowers SNR (results "may be less significant"). Run it *before* spectral connectivity. Requires a montage with 3-D electrode positions.
   > **Exception — do NOT apply CSD/Laplacian before multivariate-MVAR DTF/PDC.** The CSD-before-FC recommendation here is for phase/coherence metrics. For MVAR-based directed measures (DTF, PDC) the correct preprocessing is *only* mean-removal, variance normalization, phase-preserving filtering and a neutral reference; a Laplacian/CSD spatial transform distorts the underlying MVAR model and yields misleading directed structure. (For the contested *bivariate* Granger case keep the time-reversed-Granger control instead.) Cite: Kamiński, M., & Blinowska, K. J. (2014). Directed transfer function is not influenced by volume conduction—inexpedient pre-processing should be avoided. Frontiers in Computational Neuroscience, 8, 61.
2. **Use a VC-insensitive metric** — `imcoh`, `pli`/`pli2_unbiased`, `wpli`/`wpli2_debiased`, `ciplv`, `ppc`.

Most defensible = **both**: CSD-or-source spatial filter *and* a VC-insensitive metric. On raw sensor data, treat `coh` and `plv` as VC-contaminated; they should not be the headline metric without source localization or CSD first.

Write `connectivity-stage/METRIC_SELECTION.md` documenting choice and justification.

## Phase B — Backend resolution

```
1. Read ENVIRONMENT.json
2. Verify mne_connectivity is available → generate MNE-Python code
3. Else → ERROR: mne-connectivity required (pip install mne-connectivity)
```

Write `connectivity-stage/BACKEND_RESOLUTION.md`.

## Phase C — Per-subject connectivity computation

For each subject + condition, write and execute a script:

### MNE-Python path (default)

```python
import mne
import mne_connectivity
import numpy as np

# Load epoched data
epochs = mne.read_epochs(epochs_fif_path, preload=True)

# Select condition
epochs_cond = epochs['condition_name']

# Compute spectral connectivity
con = mne_connectivity.spectral_connectivity_epochs(
    epochs_cond,
    method='wpli2_debiased',   # or 'plv', 'coh', 'imcoh'
    mode='multitaper',          # or 'cwt_morlet' for time-resolved
    sfreq=epochs_cond.info['sfreq'],
    fmin=(4, 8, 13, 30),       # band lower bounds
    fmax=(8, 13, 30, 45),      # band upper bounds
    faverage=True,              # average within bands
    n_jobs=4,
    verbose=False
)

# Extract connectivity matrix (n_channels x n_channels x n_bands)
conn_data = con.get_data(output='dense')

# Save per-subject
np.savez(output_path,
         conn_matrix=conn_data,
         ch_names=epochs_cond.ch_names,
         freq_bands=['theta', 'alpha', 'beta', 'gamma'],
         method='wpli2_debiased')
```

**Key MNE-connectivity parameters:**
- `method='wpli2_debiased'`: Use `wpli2_debiased` (not `wpli`) for the debiased estimator (Vinck et al. 2011).
- `method='plv'`: Phase-locking value — warn about volume conduction sensitivity.
- `method='coh'`: Magnitude-squared coherence.
- `method='imcoh'`: Imaginary part of coherency.
- `mode='multitaper'`: Recommended for broadband estimation. Use `'cwt_morlet'` for time-resolved connectivity.
- `faverage=True`: Average connectivity within each frequency band. Set `False` for frequency-resolved analysis.
- `mt_bandwidth=4.0`: Multitaper bandwidth — controls spectral smoothing (higher = smoother, more robust).

### Time-resolved task connectivity (`spectral_connectivity_time`)

For event-related FC where you want one value per *time* and *frequency* (across-trial phase consistency at each TF point), use `spectral_connectivity_time` — it treats trials as the averaging dimension at every (f, t):

```python
import numpy as np
from mne_connectivity import spectral_connectivity_time

freqs = np.arange(4, 31, 1)   # analysis grid (~1–30 Hz)
con = spectral_connectivity_time(
    epochs_cond,
    method='wpli',            # or 'plv', 'coh', 'pli', 'ciplv' (time estimator subset)
    mode='cwt_morlet',        # or 'multitaper'
    freqs=freqs,
    n_cycles=freqs / 2.0,     # Morlet cycles per freq
    average=False,            # keep per-epoch values; True → average over epochs
    faverage=False,           # set band tuples (fmin/fmax) + True to collapse to bands
    n_jobs=4,
)
# average=False → con.get_data() is (n_epochs, n_pairs, n_freqs, n_times)
```

**Rule of thumb:** `spectral_connectivity_epochs` for resting/whole-trial (epochs = sample dimension, one value per band); `spectral_connectivity_time` for time-resolved task FC. Task PLV/wPLI here = across-trial phase consistency, so it needs **many trials** to be stable (positively biased at low trial counts). Note `spectral_connectivity_time` accepts only `coh`, `plv`, `ciplv`, `pli`, `wpli`, `gc`, `gc_tr` (no `imcoh`/`wpli2_debiased`/`pli2_unbiased`/`ppc`).

### Resting-state workflow and band looping

- Epoch continuous resting data into fixed segments (~2 s) — coherence/PLV/wPLI need **many segments** to be meaningful (a single segment makes `coh` and `plv` trivially = 1).
- Loop **per band**: pass band tuples `fmin=(1,4,8,13,30), fmax=(4,8,13,30,45)` with `faverage=True`, or call per band. Each band can show a different network topology — never collapse across bands without justification.
- Filter/Hilbert edge artifacts argue for sufficiently long segments (or dropping the first/last ~10% of samples) before FC.

## Phase D — Graph theory metrics

After computing pairwise connectivity matrices, optionally compute graph-theoretic summaries:

```python
import networkx as nx
# Or: import bct  # Brain Connectivity Toolbox (Python)

# Threshold connectivity matrix (e.g., proportional threshold keeping top 20% edges)
threshold = np.percentile(conn_matrix, 80)
adj = (conn_matrix > threshold).astype(float)

# NetworkX graph metrics
G = nx.from_numpy_array(adj)

metrics = {
    'clustering_coefficient': nx.average_clustering(G),                 # local clustering
    'characteristic_path_length': nx.average_shortest_path_length(G)    # if connected
        if nx.is_connected(G) else float('inf'),
    'global_efficiency': nx.global_efficiency(G),
    'local_efficiency': nx.local_efficiency(G),
}

# Small-worldness (Humphries & Gurney 2008):
# sigma = (C / C_random) / (L / L_random)
# where C = clustering, L = path length, random = Erdos-Renyi with same N, K
n_nodes = len(G)
n_edges = G.number_of_edges()
G_random = nx.erdos_renyi_graph(n_nodes, n_edges / (n_nodes * (n_nodes - 1) / 2))
C_rand = nx.average_clustering(G_random) if nx.average_clustering(G_random) > 0 else 1e-10
L_rand = nx.average_shortest_path_length(G_random) if nx.is_connected(G_random) else float('inf')
metrics['small_worldness_sigma'] = (
    (metrics['clustering_coefficient'] / C_rand) /
    (metrics['characteristic_path_length'] / L_rand)
) if L_rand != float('inf') and metrics['characteristic_path_length'] != float('inf') else None

# Alternative: use bct-python for neuroscience-specific graph metrics
# import bct
# metrics['modularity'] = bct.modularity_und(conn_matrix)[1]
# metrics['betweenness'] = bct.betweenness_wei(1.0 / conn_matrix)  # weight inversion for distance
```

**Graph metric guidelines:**
- **Thresholding**: Always report the thresholding method (absolute, proportional, MST-based). Results are sensitive to threshold choice.
- **Prefer OMST over an arbitrary proportional/absolute threshold.** Orthogonal Minimal Spanning Trees (`dyconnmap.graphs.threshold_omst_global_cost_efficiency`) is **parameter-free**: it stacks successive orthogonal MSTs and keeps the topology that maximizes global cost-efficiency `(global_efficiency − cost) / cost`, guaranteeing a connected graph (no disconnection / infinite path length) and outperforming proportional and absolute thresholds for test–retest reliability and group classification. Use it as the default data-driven threshold; report proportional only as a sensitivity check. Cite: Dimitriadis, S. I. et al. (2017). Topological filtering of dynamic functional brain networks unfolds informative chronnectomics. Brain Connectivity, 7(10), 661–670.
- **Weight handling**: For weighted metrics, decide whether stronger connectivity = shorter path (invert weights) or longer path.
- **Small-worldness**: sigma > 1 indicates small-world topology. Use multiple random graph comparisons (n=100+).
- **BCT vs NetworkX**: Brain Connectivity Toolbox (bct-python) has neuroscience-specific metrics (modularity, rich-club, hub scores). NetworkX is more general.

Save `connectivity-stage/<sub>/<sub>-<cond>-<band>-graph_metrics.json`.

## Phase E — Group-level aggregation

1. Average connectivity matrices across subjects per condition per band.
2. Compute group-level graph metrics on the averaged matrix.
3. For between-condition comparisons: compute difference matrices and save for `eeg-stats`.
4. Save:
   - `connectivity-stage/group/group-<cond>-<band>-conn_avg.npz`
   - `connectivity-stage/group/group-<cond>-<band>-graph_metrics.json`
   - `connectivity-stage/group/conn_summary.csv` (one row per subject per condition per band with key metrics).

### Condition matching for source-space FC

When contrasting connectivity between two conditions/groups in source space, build **one** spatial filter / inverse on the **pooled** (combined) data, then apply that same filter to each condition separately before computing FC. Estimating a separate filter per condition lets condition differences in the filter itself bias the connectivity contrast.

- LCMV: `mne.beamformer.make_lcmv(info, fwd, data_cov_combined, noise_cov, reg=0.05, pick_ori='max-power', weight_norm='unit-noise-gain')`, then `apply_lcmv_epochs` per condition.
- DICS (frequency domain): `mne.beamformer.make_dics(info, fwd, csd_combined, reg=0.05, pick_ori='max-power')`.
- Then `mne.extract_label_time_course(stcs, labels, src)` with an atlas (e.g. `aparc`) and feed ROI time courses to `spectral_connectivity_epochs`. Compute FC on **parcellated ROI** time courses, not full source space, to control dimensionality.
- Regularization `reg≈0.05` (power) to `0.1` (connectivity); fixed/max-power orientation.

**Benchmarked source-FC pipeline (large realistic-leakage simulation).** Collapsing each ROI to a single `mean` time course can cancel distributed within-ROI coupling and bakes in ROI-size bias. The best-performing combination in a large simulation was: **LCMV beamformer** (beat eLORETA, DICS and Champagne) → reduce each ROI to a **fixed small number of PCA components (3–4)**, which removes ROI-size bias → **Multivariate Interaction Measure (MIM)** for undirected FC and **Time-Reversed Granger Causality (TRGC)** for directed FC. MIM maximizes the imaginary part of coherency over within-region linear combinations of the components, so it is leakage-robust *and* captures distributed coupling that simple voxel/label averaging cancels. **Avoid**: anything based on the absolute value of coherency, and the DICS + directed-measure combination — these were the worst performers. Prefer `mode='multivar'` MIM in `mne_connectivity` (or compute it via the imaginary-coherency formula of Ewald 2012) on the per-ROI PCA components rather than feeding a single mean ROI signal. Cite: Pellegrini, F., Delorme, A., Nikulin, V., & Haufe, S. (2023). Identifying good practices for detecting inter-regional linear functional connectivity from EEG. NeuroImage, 277, 120218. Ewald, A., Marzetti, L., Zappasodi, F., Meinecke, F. C., & Nolte, G. (2012). Estimating true brain connectivity from EEG/MEG data invariant to linear and static transformations in sensor space. NeuroImage, 60(1), 476–488 (MIM).

## Phase E3 — Group connectivity statistics

Connectivity matrices reduce to a vector over the **unique off-diagonal edges**. Edge counts (use the correct N for multiple-comparison correction):

- Undirected (coh/plv/pli/wpli/imcoh): `E*(E-1)/2` edges (upper triangle only).
- Directed (gc/psi): `E*(E-1)` edges (full off-diagonal).
- **Exclude the diagonal** from stats and from figure color scaling (diagonal is trivial: coh≈1, pli/wpli≈0; wPLI is NaN on the diagonal → set 0).

**Default — mass-univariate + FDR:**
```python
from scipy import stats
from mne.stats import fdr_correction
# X_cond1, X_cond2: (n_subjects, n_edges) over the upper triangle, one band
t, p = stats.ttest_rel(X_cond1, X_cond2)         # or ttest_ind for between-group
reject, p_fdr = fdr_correction(p, alpha=0.05)    # Benjamini-Hochberg (method='indep')
```

**Stronger control — network/cluster level:** per-edge p<0.05 thresholding is invalid given ~N² comparisons. Two field-standard options:
- **Cluster-based permutation** over the edge×band space (`mne.stats.permutation_cluster_test`).
- **NBS (Network-Based Statistic, Zalesky et al. 2010):** threshold edge t-values, find connected components in the graph, take the largest-component mass as the cluster statistic, build a null by permuting condition labels (within subject for paired designs). **NBS is not in MNE core** → implement as a custom permutation over connected components (or use an external NBS implementation).
- **NBS-TFCE — prefer it over plain NBS.** Plain NBS inherits an arbitrary cluster-forming threshold and reports only a *whole-component* verdict, so it cannot localize the effect to specific edges. The TFCE variant integrates each edge's topological component-size`^E` × height`^H` over a range of thresholds, removing the single-threshold dependence while restoring **edge-level localizability** (which individual edges drive the effect). Use NBS-TFCE as the default network-level test and reserve plain NBS for replicating prior single-threshold reports. Cite: Baggio, H. C. et al. (2018). Statistical inference in brain graphs using threshold-free network-based statistics. Human Brain Mapping, 39(6), 2289–2302.

When a hypothesis exists, restrict tests to a-priori ROI edges to cut the multiple-comparison burden. Match trial counts across conditions before computing per-subject connectivity (PLV/coh/wPLI are biased by N trials).

**Reliability-driven epoch granularity and the edge-vs-graph choice (longitudinal/biomarker FC).** For the same total data, **more, shorter epochs beat fewer, longer ones** for PLI/wPLI reliability — twelve 4 s epochs outperform four 12 s epochs. And derived **graph metrics are far less stable than the raw edge weights**: path length and small-worldness can have ICCs as low as ~0.12, whereas edge-level wPLI in theta/alpha is reasonably reliable. For clinical or longitudinal biomarker claims, prefer **edge weights over graph summaries**, and segment into many short epochs. Cite: Hardmeier, M. et al. (2014). Reproducibility of functional connectivity and graph measures based on the phase lag index (PLI) and weighted phase lag index (wPLI) derived from high-resolution EEG. PLoS ONE, 9(10), e108648.

## Phase F — Write outputs

For each subject, write:

### `connectivity-stage/<sub>/<sub>-<cond>-<band>-conn.npz`
Contains: `conn_matrix`, `ch_names` (or `roi_names` for source space), `freq_band`, `method`.

### `connectivity-stage/<sub>/<sub>-<cond>-<band>-graph_metrics.json`
```json
{
  "subject": "sub-01",
  "condition": "task",
  "freq_band": "alpha",
  "method": "wpli2_debiased",
  "threshold_method": "proportional_top20pct",
  "clustering_coefficient": 0.42,
  "characteristic_path_length": 2.13,
  "global_efficiency": 0.51,
  "small_worldness_sigma": 1.87,
  "n_channels": 64
}
```

### Append to `FINDINGS.md`
```markdown
## Connectivity: [condition] [band]
- Method: [wPLI / PLV / ...], backend: mne-connectivity
- Mean connectivity (ROI): [value ± SD]
- Graph metrics: clustering = [C], path length = [L], small-worldness = [sigma]
```

## Phase G — Phase-amplitude coupling (PAC)

PAC is a cross-frequency metric requiring a separate pipeline. `pactools` and `tensorpac` are **OPTIONAL** (not in the `aeais` core env) — guard the import, and if neither is present fall back to the pure-NumPy Tort Modulation Index below (which has no extra dependencies). **Never** crash the stage because a PAC backend is missing.

```python
# pactools is OPTIONAL — guard the import and degrade gracefully
try:
    from pactools import Comodulogram
    HAVE_PACTOOLS = True
except ImportError:
    HAVE_PACTOOLS = False   # pip install pactools  → fall back to numpy Tort MI below

# Define phase and amplitude frequency ranges
low_fq_range = np.arange(2, 20, 1)    # phase frequencies
high_fq_range = np.arange(30, 100, 5)  # amplitude frequencies

if HAVE_PACTOOLS:
    # Compute comodulogram per channel
    estimator = Comodulogram(
        fs=epochs.info['sfreq'],
        low_fq_range=low_fq_range,
        high_fq_range=high_fq_range,
        method='duprelatour',  # or 'tort', 'ozkurt', 'canolty'
        n_surrogates=200,      # permutation surrogates for significance
        progress_bar=True
    )
    estimator.fit(signal)  # 1D signal per channel
```

**PAC notes:**
- Requires long continuous segments (>10 s) for reliable estimation.
- Common frequency pairs: theta (4–8 Hz) phase × gamma (30–100 Hz) amplitude.
- Always test against surrogate distribution (time-shifted or trial-shuffled).
- Report: method, frequency ranges, number of surrogates, z-score threshold.

### G.1 — The comodulogram grid (low phase-freq × high amp-freq)

A single phase-band × amplitude-band PAC value answers one a-priori hypothesis; a **comodulogram** scans the whole `(f_phase, f_amplitude)` plane so the coupling band-pair is *discovered*, not assumed. It is a 2-D matrix `MI[n_phase, n_amp]` where each cell is the PAC of the slow phase at `f_phase` against the fast amplitude at `f_amplitude`.

- **Phase axis** (`low_fq_range`): narrow, slow bands, e.g. `np.arange(2, 20, 1)` Hz with bandwidth ~1–2 Hz. The phase filter must be **narrow-band** — phase is only meaningful for a near-sinusoidal signal.
- **Amplitude axis** (`high_fq_range`): faster bands, e.g. `np.arange(30, 120, 5)` Hz. **Constraint (Aru et al. 2015, Berman et al. 2012):** the amplitude-filter *bandwidth* must be ≥ 2× the phase frequency, otherwise the amplitude envelope cannot track the modulating cycle (the sidebands fall outside the passband) and true coupling is missed. Scale amplitude bandwidth with `f_phase`, e.g. `amp_bw = max(10.0, 2.2 * f_phase)`.
- Because the comodulogram is a grid, it produces **`n_phase × n_amp` simultaneous tests** — every cell needs surrogate normalization (G.3) and the grid as a whole needs multiple-comparison correction (G.5). A raw comodulogram heatmap is *exploratory only*; the headline claim must be the corrected one.

Pure-NumPy Tort Modulation Index (the dependency-free fallback; also the reference implementation `method='tort'` in pactools). MI is the Kullback–Leibler divergence of the amplitude-by-phase distribution from uniform, normalized by `log(n_bins)`:

```python
import numpy as np
from scipy.signal import hilbert
import mne

def _bandpass(x, sfreq, f_lo, f_hi):
    return mne.filter.filter_data(x, sfreq, f_lo, f_hi, verbose=False)

def tort_mi(phase, amp, n_bins=18):
    """Tort et al. 2010 Modulation Index from a phase series and an amplitude series."""
    edges = np.linspace(-np.pi, np.pi, n_bins + 1)
    idx = np.digitize(phase, edges) - 1
    idx = np.clip(idx, 0, n_bins - 1)
    m = np.array([amp[idx == b].mean() if np.any(idx == b) else 0.0
                  for b in range(n_bins)])
    m = m / m.sum()                              # mean amplitude per phase bin → distribution
    m = np.clip(m, 1e-12, None)
    kl = np.log(n_bins) + np.sum(m * np.log(m))  # KL(P || uniform)
    return kl / np.log(n_bins)                   # normalized to [0, 1]

def comodulogram_mi(sig, sfreq, low_fq_range, high_fq_range, n_bins=18):
    """Pure-NumPy comodulogram, MI[n_phase, n_amp]; no pactools/tensorpac needed."""
    mi = np.zeros((len(low_fq_range), len(high_fq_range)))
    phases = {}
    for i, fp in enumerate(low_fq_range):
        ph = np.angle(hilbert(_bandpass(sig, sfreq, fp - 1.0, fp + 1.0)))
        phases[i] = ph
        for j, fa in enumerate(high_fq_range):
            amp_bw = max(10.0, 2.2 * fp)         # amp bandwidth ≥ 2·f_phase (Aru 2015)
            amp = np.abs(hilbert(_bandpass(sig, sfreq, fa - amp_bw, fa + amp_bw)))
            mi[i, j] = tort_mi(phases[i], amp, n_bins=n_bins)
    return mi, phases
```

### G.2 — Preferred-phase extraction

The MI scalar says *how much* the amplitude is modulated; the **preferred phase** says *where* in the slow cycle the fast amplitude peaks (e.g. gamma riding the theta trough vs. peak). It is the circular mean of the slow phase weighted by the fast amplitude:

```python
def preferred_phase(phase, amp):
    """Mean slow-cycle phase at which the fast amplitude is maximal."""
    z = np.sum(amp * np.exp(1j * phase)) / np.sum(amp)
    return np.angle(z), np.abs(z)   # (preferred_phase_rad, concentration R in [0,1])
```

- Report the preferred phase **only at band-pairs that survive surrogate testing (G.3)** — it is uninterpretable where there is no significant coupling.
- The concentration `R` is the basis of the across-trial/across-subject consistency test in G.4.
- Equivalently, take the argmax phase-bin of the Tort amplitude-by-phase distribution `m` from G.1; the vector form above is preferred because it is continuous and feeds the Rayleigh test directly.

**Rayleigh vs. v-test — uniformity vs. directional concentration.** The Rayleigh test asks "are these phases non-uniform at all?" (omnibus). When you have an **a-priori predicted angle** μ₀ (e.g. "gamma should peak at the theta trough, π rad"), the **v-test** is more powerful because it tests concentration *toward that specific direction*, not just any: with `v = R·cos(mean_phase − μ₀)` and `u = v·√(2n)`, `u` is ~N(0,1) under the null for large n (one-sided). Use the v-test for confirmatory preferred-phase / ITPC-direction claims and the Rayleigh test when no angle is predicted. Cite: Cohen, M. X. (2014). *Analyzing Neural Time Series Data*, Ch. 26/31 (phase concentration statistics); Berens (2009) CircStat.

### G.3 — Surrogate schemes and z-scored MI

Raw MI is **always positive and biased upward** by filtering, autocorrelation, and finite data; an MI value is meaningless without a surrogate null. Build a null by destroying the *phase–amplitude timing relationship* while preserving each signal's own spectro-temporal structure, then z-score:

`MI_z = (MI_observed − mean(MI_surrogate)) / std(MI_surrogate)`

Three schemes, in rough order of preference:

```python
def surrogate_mi(phase, amp, scheme='block_shift', n_surr=200, rng=None):
    rng = np.random.default_rng(rng)
    n = len(amp)
    null = np.empty(n_surr)
    for k in range(n_surr):
        if scheme == 'block_shift':
            # (2) time-splice / block-shift: cut amp at a random point and swap halves.
            # Best general-purpose surrogate — preserves amp autocorrelation, breaks
            # only the cross-signal timing. Use a large minimum offset to avoid trivial shifts.
            s = rng.integers(int(0.1 * n), int(0.9 * n))
            amp_s = np.concatenate([amp[s:], amp[:s]])
            null[k] = tort_mi(phase, amp_s)
        elif scheme == 'fft_scramble':
            # (1) FFT phase-scramble: randomize Fourier phases of amp, keep its power spectrum.
            # WARNING: can be UNRELIABLE — it destroys non-sinusoidal/sharp-edge structure
            # and can both inflate and deflate the null; do NOT rely on it alone.
            f = np.fft.rfft(amp)
            ph_rand = np.exp(1j * rng.uniform(0, 2 * np.pi, len(f)))
            ph_rand[0] = 1.0
            amp_s = np.fft.irfft(np.abs(f) * ph_rand, n=n)
            null[k] = tort_mi(phase, amp_s)
        elif scheme == 'trial_shuffle':
            # (3) trial-shuffle: pair this trial's phase with a DIFFERENT trial's amplitude.
            # Requires epoched data (phase/amp are lists over trials); strongest null for
            # task data because it preserves within-trial structure entirely.
            raise NotImplementedError("operate over trial lists; see note below")
    return null

# z-score one comodulogram cell:
# mi_obs = tort_mi(phase, amp)
# null   = surrogate_mi(phase, amp, scheme='block_shift', n_surr=200, rng=SEED)
# mi_z   = (mi_obs - null.mean()) / null.std()
# p_perm = (1 + np.sum(null >= mi_obs)) / (1 + len(null))   # one-sided permutation p
```

- **(1) FFT phase-scramble** — randomize the Fourier phases of the amplitude time series, keeping its power spectrum. Cheap, but **can be unreliable**: it assumes a stationary, sinusoidal signal and destroys exactly the sharp-edge/non-sinusoidal structure that produces spurious PAC, so it neither models nor controls that confound. Never use it as the *only* surrogate.
- **(2) Time-splice / block-shift** — cut the amplitude (or phase) series at a random offset and swap the two halves. Preserves each signal's autocorrelation and waveform shape; breaks only the inter-signal timing. The recommended default for continuous data.
- **(3) Trial-shuffle** — for epoched data, pair each trial's slow phase with a *different* trial's fast amplitude. Preserves all within-trial structure and is the strongest null for task/ERP data; build it over the trial lists rather than within a single concatenated segment.
- Report **z-scored (or permutation-p) MI**, never raw MI, as the headline quantity, plus the surrogate scheme and `n_surr` (≥200; 1000 for publication).

### G.4 — Preferred-phase consistency: pure-NumPy circular Rayleigh test

A single subject's preferred phase is just an angle; to claim a **consistent** preferred phase across trials (or across subjects) test the angles against the null of a uniform circular distribution with the **Rayleigh test** — implementable in pure NumPy with no `scipy.stats` circular module:

```python
def rayleigh_test(phases):
    """Rayleigh test for non-uniformity of circular data. phases: 1-D array (radians)."""
    n = len(phases)
    R = np.abs(np.mean(np.exp(1j * phases)))      # mean resultant length, [0, 1]
    z = n * R**2                                   # Rayleigh's z statistic
    # Zar (1999) small-sample correction for the p-value:
    p = np.exp(-z) * (1 + (2 * z - z**2) / (4 * n))
    return R, z, float(np.clip(p, 0.0, 1.0))
```

- Feed it the per-trial (or per-subject) preferred phases from G.2; a small `p` rejects uniformity ⇒ the coupling occurs at a **reproducible** slow-cycle phase, which is much stronger evidence than a single MI value.
- `R` near 1 = tightly clustered preferred phases; `R` near 0 = scattered (no consistent phase).
- The same `R = |mean(exp(1j·phases))|` machinery underlies PLV/ITC elsewhere in this skill (see Closed-form definitions) — here the "observations" are preferred phases rather than per-trial phase differences.
- If available, `pingouin.circ_rtest` or `astropy.stats.rayleightest` give the same statistic (both **OPTIONAL**); the NumPy version above is the dependency-free reference and matches them to small-sample order.

### G.5 — Multiple-comparison correction across the comodulogram

A comodulogram of `n_phase × n_amp` cells is `n_phase · n_amp` simultaneous significance tests; an uncorrected heatmap *will* show "significant" cells by chance. Correct the per-cell p-values (from the G.3 permutation null) across the whole grid:

```python
from scipy.stats import false_discovery_control  # SciPy ≥1.11; else mne.stats.fdr_correction

p_grid = ...                       # (n_phase, n_amp) one-sided permutation p-values
flat = p_grid.ravel()

# Holm–Bonferroni (strong FWER control, step-down — less conservative than plain Bonferroni)
order = np.argsort(flat)
m = flat.size
p_holm = np.empty(m)
running = 0.0
for rank, idx in enumerate(order):
    val = (m - rank) * flat[idx]
    running = max(running, val)           # enforce monotonicity
    p_holm[idx] = min(running, 1.0)
p_holm = p_holm.reshape(p_grid.shape)
reject_holm = p_holm < 0.05

# Plain Bonferroni (simplest, most conservative):
reject_bonf = p_grid < (0.05 / m)
```

- Use **Holm–Bonferroni** (or Bonferroni) for FWER control when the claim is "this specific band-pair couples"; FDR (`false_discovery_control` / `mne.stats.fdr_correction`) is acceptable when reporting a *set* of coupled pairs. State which, and the grid size `m`, in `FINDINGS.md`.
- Adjacent comodulogram cells are correlated (overlapping filters), so cluster-based permutation over the `(f_phase, f_amplitude)` plane is a valid stronger alternative — analogous to the edge-cluster correction in Phase E3.
- Apply the correction **once over the full grid**, then report only surviving cells with their z-scored MI and (G.4) preferred-phase consistency.

## Phase H — Sanity checks

All must pass before declaring success:

- [ ] Every subject has connectivity matrices for all conditions and frequency bands.
- [ ] Matrix dimensions match: (n_channels × n_channels × n_bands) or (n_rois × n_rois × n_bands).
- [ ] Diagonal of connectivity matrices is handled correctly (self-connections = NaN or excluded).
- [ ] If source-space: orthogonalization was applied before computing connectivity.
- [ ] Graph metrics are within plausible ranges (0 ≤ clustering ≤ 1, path length ≥ 1).
- [ ] BACKEND_RESOLUTION.md exists.
- [ ] Group-average files exist in `connectivity-stage/group/`.
- [ ] If PAC was requested: MI is z-scored against a surrogate null (not raw), the surrogate scheme + `n_surr` are logged, and comodulogram p-values are corrected across the grid (Phase G.3/G.5).

## Critical Rules

- **Never** compute coherence or PLV in sensor space and interpret as "brain region A connects to region B" — volume conduction confounds this interpretation. Use wPLI, imaginary coherence, or source-space analysis.
- **Never** use Granger causality on non-stationary data without stationarity checks (ADF test or windowed approach).
- **Never** interpret graph metrics from a single threshold. Report sensitivity to threshold choice or use MST-based approaches.
- **Never** average connectivity across frequency bands without justification — each band may show different network topology.
- **Never** compare connectivity matrices with different numbers of epochs across conditions — subsample to match trial counts.
- **Never** report coherence or PLV computed from a single segment/epoch — both are degenerate (=1) without averaging over multiple segments/trials.
- **Never** include the diagonal in connectivity statistics or in figure color scaling, and use the correct edge count for multiple-comparison correction (`E*(E-1)/2` undirected, `E*(E-1)` directed).
- **Never** threshold connectivity edges at p<0.05 independently — correct across the ~N² edges (FDR, cluster permutation, or NBS).
- **Never** estimate a separate source spatial filter per condition when contrasting conditions in source space — use one common filter on pooled data, then apply per condition.
- **Never** apply CSD/Laplacian before MVAR-based DTF/PDC — it distorts the MVAR model and yields misleading directed structure (CSD-before-FC is only for phase/coherence metrics).
- **Never** report PDC without stating the variant — standard column-normalized PDC is not scale-invariant and drops when a source drives multiple targets; prefer scale-invariant gPDC.
- **Never** claim mutual information, transfer entropy, or Synchronization Likelihood from `mne_connectivity` — they are not in MNE core and require external tools.
- **Never** report raw (un-normalized) PAC / Modulation Index — z-score it against a surrogate null (block-shift / trial-shuffle), since raw MI is always positively biased.
- **Never** rely on the FFT phase-scramble surrogate alone for PAC — it cannot control the sharp-edge/non-sinusoidal artifact that most often produces spurious coupling; prefer time-splice/block-shift or trial-shuffle.
- **Never** read significance off a raw comodulogram — correct the per-cell p-values across the full `n_phase × n_amp` grid (Holm/Bonferroni, FDR, or cluster permutation).
- **Never** crash the stage when `pactools`/`tensorpac` are absent — they are optional; fall back to the pure-NumPy Tort MI / Rayleigh implementations.

## Domain Knowledge (distilled from EEG connectivity methodology literature)

### Debiased wPLI (Vinck et al. 2011, NeuroImage)

- The weighted phase lag index (wPLI) weights the contribution of each observation by the magnitude of the imaginary component of the cross-spectrum.
- **Why wPLI over PLI**: Standard PLI is discontinuous around zero phase lag, making it noisy for weak coupling. wPLI smooths this discontinuity by weighting.
- **Why debiased wPLI**: The standard wPLI estimator has a positive bias for finite samples. The debiased version (`wpli2_debiased` in MNE) corrects this, giving an unbiased estimator with lower MSE.
- Volume conduction produces zero-phase-lag signals; wPLI is insensitive to these because it ignores contributions at zero lag.
- Limitation: wPLI cannot detect true zero-lag interactions (which can exist in neural data due to common subcortical input).
- Cite: Vinck, M., Oostenveld, R., van Wingerden, M., Battaglia, F., & Pennartz, C. M. (2011). An improved index of phase-synchronization for electrophysiological data in the presence of volume-conduction, noise and sample-size bias. NeuroImage, 55(4), 1548–1565.

### Phase-locking value (Lachaux et al. 1999, Human Brain Mapping)

- PLV measures the consistency of phase differences between two signals across trials or time.
- PLV = |mean(exp(j * (phase_A - phase_B)))| across trials. Ranges from 0 (no synchrony) to 1 (perfect synchrony).
- **Limitation**: PLV is sensitive to volume conduction — two electrodes picking up the same source will show high PLV (zero-lag, in-phase or anti-phase). This is NOT neural connectivity.
- PLV is also biased by trial count: fewer trials → higher PLV due to finite-sample effects. Always match trial counts across conditions.
- For sensor-space analysis, PLV should only be interpreted for non-zero phase lags, or replaced with wPLI/imaginary coherence.
- Cite: Lachaux, J. P., Rodriguez, E., Martinerie, J., & Varela, F. J. (1999). Measuring phase synchrony in brain signals. Human Brain Mapping, 8(4), 194–208.

### Closed-form definitions (for verifying MNE output)

Given per-segment/per-trial phase difference `rp = phase_x - phase_y` and cross-spectrum `Sxy = X·conj(Y)` (analytic signals), the MNE method strings compute:
- **PLV** = `|mean(exp(1j·rp))|`, range [0,1]. 0 = uniform phase diffs (no sync); 1 = fixed phase diff.
- **PLI** = `|mean(sign(imag(Sxy)))|`, range [0,1]. 0 = phase-lag sign ± equally often; 1 = always one sign. Insensitive to zero-lag (VC).
- **wPLI** = `|mean(imag(Sxy))| / mean(|imag(Sxy)|)`, range [0,1]; the debiased variant (`wpli2_debiased`) removes finite-sample positive bias.
- **Coherence (MSC)** = `|mean(Sxy)|² / (mean(Sxx)·mean(Syy))`, range [0,1] — the average is over segments/trials **before** the magnitude ratio, so a single segment gives a trivial `|coh|=1`. `imcoh` uses the `imag` part of coherency (VC-robust).
- **ITC / inter-trial phase consistency** (same machinery, single channel vs reference) = `|mean over trials of exp(1j·angle(coef))|`; PLV is exactly this applied to the phase *difference* between two channels. ITC needs the per-trial complex coefficients, is amplitude-independent, and is positively biased at low trial counts.

These match MNE's `plv`/`pli`/`wpli`/`coh`/`imcoh`, so hand-computed values can be used to sanity-check `spectral_connectivity_*` output.

### Tutorial on connectivity methods (Bastos & Schoffelen 2016, NeuroImage)

- Comprehensive tutorial covering coherence, imaginary coherence, PLV, wPLI, Granger causality, and directed transfer function.
- **Key recommendations**:
  - Use directed measures (Granger, PDC, DTF) only when directionality is the research question and data quality supports it (long, stationary epochs).
  - For undirected functional connectivity, wPLI or imaginary coherence is preferred over coherence or PLV at the sensor level.
  - At the source level, signal leakage is the primary concern — apply orthogonalization or use leakage-robust metrics.
  - Always simulate known connectivity patterns to validate the pipeline before applying to real data.
- Cite: Bastos, A. M., & Schoffelen, J. M. (2016). A tutorial review of functional connectivity analysis methods and their interpretational pitfalls. Frontiers in Systems Neuroscience, 9, 175.

### Imaginary coherency (Nolte et al. 2004, Clinical Neurophysiology)

- The imaginary part of coherency is zero for instantaneous (zero-lag) mixing, so it cannot be produced by volume conduction of a single source to multiple electrodes — only by genuinely lagged (time-delayed) interaction.
- In MNE this is `method='imcoh'`; pair it with `coh` whenever coherence is requested on sensor data so the VC-robust reading is always available alongside the contaminated one.
- Limitation: like wPLI/PLI, it is blind to true zero-lag coupling and its sign/magnitude depends on the interaction's phase lag.
- Cite: Nolte, G., Bai, O., Wheaton, L., Mari, Z., Vorbach, S., & Hallett, M. (2004). Identifying true brain interaction from EEG data using the imaginary part of coherency. Clinical Neurophysiology, 115(10), 2292–2307.

### Granger causality: model order and the time-reversed control

- Bivariate spectral Granger asks whether adding y's past reduces the residual variance of predicting x: `GC = log(var_restricted / var_full) > 0` ⇒ y Granger-causes x.
- **Always test both directions** (x→y and y→x); cause vs effect is not known a priori.
- **Report the time-reversed control** (`method='gc_tr'` alongside `'gc'`): genuine GC should reverse under time reversal, whereas spurious GC driven by SNR/amplitude asymmetry or volume conduction does not — the net (gc − gc_tr) guards against false directionality.
- For any explicit-MVAR path (e.g. statsmodels VAR — note statsmodels is an optional dependency not present in `aeais`), **model order p must be selected first** via AIC/BIC; requires stationary, sufficiently long, well-SNR data.
- Granger on sensor data is highly susceptible to volume conduction → prefer source space.
- **PDC normalization — report the variant.** Standard column-normalized PDC is *not* scale-invariant and, perversely, **decreases** when one source drives several targets (the column normalization splits the outflow among targets). Use **generalized PDC (gPDC)**, which normalizes by the innovation (residual) variance and restores scale-invariance, and always state which variant you computed. Cite: Baccalá, L. A., & Sameshima, K. (2021). Partial directed coherence: twenty years on some history and an appraisal. Biological Cybernetics, 115(3), 195–204 (gPDC).
- Cite: Haufe, S., Nikulin, V. V., Müller, K. R., & Nolte, G. (2013). A critical assessment of connectivity measures for EEG data: A simulation study. NeuroImage, 64, 120–133 (time-reversed Granger control). Barnett, L., & Seth, A. K. (2014). The MVGC multivariate Granger causality toolbox. Journal of Neuroscience Methods, 223, 50–68 (model-order/spectral GC).

### Cross-frequency coupling (Palva & Palva 2012, Trends in Cognitive Sciences)

- Phase-amplitude coupling (PAC) is the most studied cross-frequency interaction: the phase of a slow oscillation modulates the amplitude of a faster oscillation.
- Common examples: theta-phase × gamma-amplitude coupling in hippocampus and cortex during memory tasks.
- **Methods**: Modulation Index (Tort et al. 2010), Mean Vector Length (Canolty et al. 2006), General Linear Model (Dupre la Tour et al. 2017).
- **Pitfalls**:
  - Sharp transients (e.g., epileptic spikes) create artifactual PAC due to harmonic content — filter carefully.
  - PAC estimates require long data segments; short epochs produce unreliable estimates.
  - Always test against surrogate distributions to establish significance.
- Cite: Palva, S., & Palva, J. M. (2012). Discovering oscillatory interaction networks with M/EEG: challenges and breakthroughs. Trends in Cognitive Sciences, 16(4), 219–230.

### Modulation Index and the comodulogram (Tort et al. 2010, J. Neurophysiol.)

- The **Modulation Index (MI)** quantifies PAC as the Kullback–Leibler divergence between the observed mean-amplitude-by-phase distribution and a uniform distribution, normalized by `log(n_bins)` so MI ∈ [0, 1] (0 = no coupling, larger = stronger phase modulation of amplitude). It is robust to amplitude scaling and to the number of phase bins (≈18 is standard).
- **Comodulogram**: computing MI over a grid of slow phase-frequencies × fast amplitude-frequencies maps where in the spectrum coupling lives, rather than assuming a band-pair a priori. The paper also formalizes the **filter-bandwidth constraint**: the amplitude filter must be wide enough (bandwidth ≳ 2× the modulating phase frequency) for the envelope to carry the slow rhythm — too-narrow amplitude filters destroy detectable PAC.
- **Preferred phase**: the phase bin (or amplitude-weighted circular mean of phase) at which the fast amplitude is maximal; comparable across conditions and the target of circular consistency tests (Rayleigh).
- **Surrogates are mandatory**: MI is positively biased, so significance must come from a surrogate null (block-shift / trial-shuffle / phase-scramble) and a z-score or permutation p, not the raw MI. The paper compares MI favourably to mean-vector-length and the GLM-PAC in robustness to noise and to the amplitude distribution.
- **Spurious PAC**: non-sinusoidal waveforms and sharp edges (spikes, ERPs, square-ish rhythms) inject harmonics that masquerade as PAC; inspect the raw waveform and never interpret MI without surrogate control.
- Cite: Tort, A. B. L., Komorowski, R., Eichenbaum, H., & Kopell, N. (2010). Measuring phase-amplitude coupling between neuronal oscillations of different frequencies. Journal of Neurophysiology, 104(2), 1195–1210.

### Signal leakage in source-space connectivity (Colclough et al. 2015, NeuroImage)

- Source reconstruction introduces artificial correlations between nearby sources due to the ill-posed inverse problem (spatial leakage).
- **Orthogonalization**: Symmetric multivariate orthogonalization removes instantaneous (zero-lag) correlations between all source pairs simultaneously, suppressing leakage while preserving lagged interactions.
- This is critical: computing connectivity (even wPLI) on source-space signals without leakage correction will show spurious local connectivity patterns.
- **Implementation**: `mne_connectivity` supports `method='plv'` on orthogonalized signals. Alternatively, compute envelope correlations after orthogonalization.
- Cite: Colclough, G. L., Brookes, M. J., Smith, S. M., & Woolrich, M. W. (2015). A symmetric multivariate leakage correction for MEG connectomes. NeuroImage, 117, 439–448.

### Leakage-corrected amplitude-envelope correlation (AEC-c) — the concrete recipe

The "compute envelope correlations after orthogonalization" line above needs a recipe, because AEC indexes slow band-power *co-fluctuation* and recovers a **different** network than wPLI/phase metrics — offer it alongside the phase metric, never as a substitute. Per ROI pair: band-pass both signals → pairwise-orthogonalize (regress out the real part of B from A) → Hilbert envelope → log → Pearson correlation. The Hipp/Brookes pairwise orthogonalization is **asymmetric** (`orth(A|B) ≠ orth(B|A)`), so you MUST symmetrize — average the upper and lower triangles of the AEC matrix before any graph analysis, or the network is direction-of-regression-dependent.

```python
def aec_corrected_pair(a, b):
    """Pairwise leakage-corrected AEC for one ROI pair (already band-passed)."""
    from scipy.signal import hilbert
    b_orth = b - (np.real(np.vdot(b, a)) / np.real(np.vdot(a, a))) * a  # regress real(A) out of B
    ea = np.log(np.abs(hilbert(a)))
    eb = np.log(np.abs(hilbert(b_orth)))
    return np.corrcoef(ea, eb)[0, 1]
# Build full matrix both ways, then: aec = 0.5 * (M + M.T)  # symmetrize (asymmetric orth)
```

- **Reliability-paradox Critical Rule:** do NOT justify skipping leakage correction by citing the high test–retest reliability of uncorrected AEC/PLV/COH. Uncorrected envelope/phase metrics are dominated by a *shared-leakage* signal that is itself highly stable across sessions, so their reliability (≈0.97) is artifactually inflated and not evidence of validity — leakage-corrected metrics legitimately show lower but trustworthy reliability.
- Cite: Hipp, J. F., Hawellek, D. J., Corbetta, M., Siegel, M., & Engel, A. K. (2012). Large-scale cortical correlation structure of spontaneous oscillatory activity. Nature Neuroscience, 15(6), 884–890 (pairwise orthogonalized AEC). Nagy, B. et al. (2024). The reliability paradox in EEG/MEG connectivity. Human Brain Mapping, 45, e26747 (inflated reliability of uncorrected metrics).

## Failure Modes

| Symptom | Action |
|---|---|
| ANALYSIS_PLAN missing or unfrozen | Stop. Ask user to fill and freeze the plan. |
| `mne_connectivity` not installed | `pip install mne-connectivity`. Log in BACKEND_RESOLUTION.md. |
| Memory error on source-space connectivity | Reduce number of ROIs (use aparc labels instead of full source space), or compute band-by-band. |
| Granger causality model does not converge | Check stationarity (ADF test). Reduce model order. Switch to non-parametric Granger. |
| PLV shows high connectivity everywhere | Volume conduction artifact. Switch to wPLI or imaginary coherence. Warn user. |
| Unequal trial counts across conditions | Subsample the condition with more trials to match. Log the subsampling. |
| Graph is disconnected (infinite path length) | Use global efficiency instead of path length. Report disconnection. |
| Source-space without orthogonalization | STOP. Apply leakage correction before computing connectivity. |
| Coherence/PLV ≈ 1 everywhere | Likely computed on a single segment. Re-epoch (~2 s resting) so the estimator averages over many segments/trials. |
| User asks for time-resolved task FC | Use `spectral_connectivity_time` (Morlet/multitaper, returns freq×time per pair), not `spectral_connectivity_epochs`. |
| Sensor `coh`/`plv` requested as headline metric | Warn: VC-contaminated. Add `imcoh`/`wpli`, or apply `compute_current_source_density` / source-space first. |
| Per-edge p-values look significant everywhere | No multiple-comparison correction. Apply FDR (`mne.stats.fdr_correction`) or NBS over the correct edge count. |
| Directed (Granger) result reverses meaning under controls | Report `gc_tr` (time-reversed) net GC; spurious GC from SNR/VC does not reverse. Prefer source space. |
| User requests MI / transfer entropy / Sync. Likelihood | Not in MNE core. Use external tools (e.g. IDTxl for TE); do not silently substitute another metric. |
| `pactools` / `tensorpac` not installed | Both OPTIONAL. `pip install pactools` (or `tensorpac`); otherwise fall back to the pure-NumPy Tort MI / comodulogram in Phase G.1. Never crash the stage. |
| PAC reported as raw MI (no surrogate) | Uninterpretable — raw MI is positively biased. Build a surrogate null (block-shift default; trial-shuffle for epoched), report z-scored MI / permutation p (Phase G.3). |
| Sharp transients / non-sinusoidal waveform → strong PAC everywhere | Harmonic artifact (spikes, ERPs, square rhythms create spurious PAC). Inspect raw waveform; narrow the phase filter; verify against block-shift surrogate, not FFT phase-scramble. |
| FFT phase-scramble surrogate gives implausible null | Phase-scramble is unreliable for non-sinusoidal data. Switch to time-splice/block-shift or trial-shuffle surrogates (Phase G.3). |
| Comodulogram shows many "significant" cells | No multiple-comparison correction over the `n_phase × n_amp` grid. Apply Holm–Bonferroni / Bonferroni (or FDR / cluster permutation) once over the whole grid (Phase G.5). |
| Amplitude filter too narrow → PAC vanishes | Amplitude bandwidth must be ≥ 2× the phase frequency (Aru 2015 / Tort 2010). Scale `amp_bw = max(10, 2.2·f_phase)`. |
| Preferred phase scattered across trials/subjects | Run the Rayleigh test (Phase G.4); high p ⇒ no consistent preferred phase — do not claim a phase relationship. Report `R` and `z`. |

## Cross-references

- Inputs: `ANALYSIS_PLAN.md`, `epochs-stage/`, `ENVIRONMENT.json`, `channel_mapping.json`, `source-stage/` (optional)
- Outputs: `connectivity-stage/*.npz`, `connectivity-stage/*-graph_metrics.json`, `connectivity-stage/BACKEND_RESOLUTION.md`, `connectivity-stage/METRIC_SELECTION.md`, `FINDINGS.md`
- Next: `eeg-stats` for statistical comparison of connectivity between conditions. `eeg-figure` for connectivity matrix plots and circle plots. `eeg-methods-text` for the connectivity paragraph.
