## Constants

- **BACKEND = `mne`** — MNE-Python is the computation backend; `statsmodels` is the optional factorial/mixed-model backend (see Phase D).
- **DESIGN = `within`** — `within` (all subjects see all conditions), `between` (independent groups), or `mixed` (one within factor × one between factor). Read from `ANALYSIS_PLAN.md`.
- **DEFAULT_PERMS = `5000`** — must match `ANALYSIS_PLAN.md`. Override `— perms: 1000` for development only; never lower it to chase significance.
- **SEED = read from ANALYSIS_PLAN.md `RNG seeds > Cluster permutation`**, default `42`.
- **ALPHA = read from ANALYSIS_PLAN.md claim table `α` column**, default `0.05`.
- **CI_LEVEL = `0.95`** — confidence level for grand-average bands and effect-size CIs.
- **EFFECT_SIZE = inferred from test** — Cohen's d / dz (t-contrasts), partial eta-squared (ANOVA effects).
- **OUTPUT_DIR = `group-stage/`** — create if missing.

> Override: `/eeg-group-compare projects/my-study — design: between — groups: patient,control — test: cluster — perms: 5000`

## Phase A — Parse design and assemble the second-level array

1. From `ANALYSIS_PLAN.md`, read each claim's `design`, `factors`, `groups`, `channels/ROI`, `time_window`, `freq_band`, `direction`, `alpha`, `covariates`.
2. Load one first-level summary per subject per condition. **Never** mix trials and subjects in the same array — the observation unit is the subject.
3. Build the second-level array:
   - Within / paired: `X` shape `(n_subjects, n_times, n_channels)` of the per-subject difference `A − B`.
   - Between: a list `[X_group1, X_group2]`, each `(n_subjects_g, n_times, n_channels)`.
   - Mixed / factorial: a **list of `n_cells` arrays**, each `(n_subjects, n_features)`, with `n_cells = prod(factor_levels)` ordered so the first factor varies slowest (the layout `f_mway_rm` documents, e.g. A1B1, A1B2, A2B1, A2B2).
4. Constrain to the planned ROI + time window + band before testing.
5. **Check N per group.** Report `n` per group; cluster permutation tolerates unequal N (it permutes group labels), but parametric ANOVA assumes balanced cells — flag imbalance for Phase D.

Write `group-stage/GROUP_PLAN.json` (design, factor levels, group Ns, ROI, window, test, seed) before executing.

## Phase B — Group grand-averages with confidence intervals

```python
import mne, numpy as np
# Per-condition / per-group grand average + CI band
evokeds = {cond: [mne.read_evokeds(f"{s}-ave.fif", condition=cond)[0] for s in subs]
           for cond in conditions}
grand = {cond: mne.grand_average(evokeds[cond]) for cond in conditions}      # mean across subjects
# 95% CI band for a butterfly/ROI plot via bootstrap over subjects (MNE built-in):
mne.viz.plot_compare_evokeds(evokeds, picks=roi, combine="mean", ci=0.95)    # bootstrap CI by default
```

- Report CIs as **across-subject** variability (the second-level error term), not across-trial. Cite Luck (2014) on why standard error must reflect the random effect that licenses the inference.
- For between-group plots, overlay each group's grand average with its own CI band; do not pool.

## Phase C — Spatio-temporal cluster permutation (the nonparametric workhorse)

Cluster-based permutation solves the massive multiple-comparison problem across channels × time without parametric assumptions, by building a single max-cluster null distribution (Maris & Oostenveld 2007).

```python
from mne.stats import (spatio_temporal_cluster_test,        # between-group / one-way independent
                       spatio_temporal_cluster_1samp_test)  # within / paired (X = A − B)
import scipy.stats

adjacency, ch_names = mne.channels.find_ch_adjacency(info, ch_type="eeg")  # spatial neighbours

# --- Within / paired: one-sample test on the difference array (subjects, times, channels) ---
df = X.shape[0] - 1
thr = -scipy.stats.t.ppf(1 - alpha, df) if tail == -1 else scipy.stats.t.ppf(1 - alpha, df)
t_obs, clusters, cluster_p, H0 = spatio_temporal_cluster_1samp_test(
    X, threshold=thr, tail=tail, n_permutations=N, adjacency=adjacency,
    seed=SEED, out_type="mask")

# --- Between-group (≥2 independent groups): F-threshold, list of arrays ---
f_thr = scipy.stats.f.ppf(1 - alpha, dfn=len(groups) - 1,
                          dfd=sum(g.shape[0] for g in groups) - len(groups))
t_obs, clusters, cluster_p, H0 = spatio_temporal_cluster_test(
    [Xg1, Xg2], threshold=f_thr, n_permutations=N, adjacency=adjacency,
    seed=SEED, out_type="mask")  # default stat_fun = F (ANOVA); permutes group labels
```

- Between-group is **two-sided by construction** (F-statistic) unless you supply a one-sided `stat_fun`; record this.
- Significant clusters are those with `cluster_p < alpha`. Report the cluster p-value, the search space (ROI + window), and the cluster-forming threshold.
- **Interpretation guard (Sassenhagen & Draschkow 2019):** a significant cluster means "an effect exists somewhere in the tested space" — it does NOT license claims about precise onset, offset, or peak channel. Never write "the groups differed from 180–240 ms"; write "a significant cluster spanned the 180–240 ms, central window."

## Phase D — Factorial / repeated-measures and mixed designs

For 2+ factors (e.g., Condition × Group), run a repeated-measures or mixed model rather than many t-tests, which inflate Type I error (Luck & Gaspelin 2017).

### Mass-univariate rmANOVA inside cluster permutation (MNE)

```python
from mne.stats import f_mway_rm, f_threshold_mway_rm
factor_levels = [2, 2]            # e.g., 2 conditions × 2 time-on-task levels (within)
effects = "A:B"                   # 'A', 'B', 'A:B', or 'A*B' for all

# Pass X as a LIST of per-cell arrays, each (n_subjects, n_features); features = times*channels.
# The cluster routine calls stat_fun(*X_list), so args is a tuple of those per-cell arrays.
X_list = [data[:, c, :] for c in range(np.prod(factor_levels))]   # cell order matches factor_levels
def stat_fun(*args):
    # stack -> (n_cells, subjects, feat); swap -> (subjects, n_cells, feat) for f_mway_rm
    return f_mway_rm(np.swapaxes(np.array(args), 1, 0), factor_levels,
                     effects=effects, return_pvals=False)[0]
f_thr = f_threshold_mway_rm(n_subjects=n, factor_levels=factor_levels,
                            effects=effects, pvalue=alpha)
t_obs, clusters, cluster_p, H0 = spatio_temporal_cluster_test(
    X_list, stat_fun=stat_fun, threshold=f_thr, n_permutations=N,
    adjacency=adjacency, seed=SEED, out_type="mask")
```

`f_mway_rm` uses a Greenhouse–Geisser-style correction option (`correction=True`) for sphericity violations — enable it for within factors with >2 levels.

### Scalar / ROI-collapsed ANOVA (statsmodels — optional)

When the claim is on a single ROI×window scalar per subject (not mass-univariate), use a proper model on the long table:

```python
import statsmodels.api as sm
from statsmodels.stats.anova import AnovaRM                       # pure within rmANOVA
aov = AnovaRM(long_df, depvar="amp", subject="subject",
              within=["condition"]).fit()                          # F, p, partial-eta via SS
# Mixed (within × between) or unbalanced / covariate → mixed linear model:
md = sm.MixedLM.from_formula("amp ~ C(condition)*C(group) + age",
                             groups="subject", data=long_df)        # subject random intercept
mdf = md.fit()
```

- `AnovaRM` requires balanced data; for **unequal N or covariates use `MixedLM`** (subject as random effect), which handles missing cells and continuous covariates natively.
- `pingouin` (optional, `pip install pingouin`) gives `pingouin.mixed_anova`, `pingouin.rm_anova`, and effect sizes (`np2`, generalized eta) in one call; if absent, fall back to `statsmodels` and compute partial eta-squared by hand (Phase F). Log the substitution to `group-stage/BACKEND_RESOLUTION.md`.

## Phase E — TFCE (threshold-free cluster enhancement)

TFCE removes the arbitrary cluster-forming threshold by integrating cluster support over all thresholds, giving voxel-/point-level corrected p-values (Smith & Nichols 2009).

```python
# Pass a dict instead of a scalar threshold; works for both _test and _1samp_test
t_obs, clusters, p_values, H0 = spatio_temporal_cluster_1samp_test(
    X, threshold=dict(start=0, step=0.2), n_permutations=N,
    adjacency=adjacency, seed=SEED, out_type="mask")
# p_values is per-point (same shape as t_obs); significant points: p_values < alpha
```

- TFCE returns a **p-value per time-channel point**, so you may report the spatial/temporal extent of significance more honestly than cluster-sum (but onset bias caveats still apply; Sassenhagen & Draschkow 2019).
- `start`/`step` trade sensitivity vs runtime; defaults `start=0, step=0.2` are standard for t-stat maps. Record them.

## Phase F — Effect sizes with confidence intervals

Always pair a p-value with a standardized effect size **and its CI** (Lakens 2013; COBIDAS, Pernet et al. 2020).

- **Paired/within:** Cohen's `dz = mean(diff) / std(diff)` over subjects in the ROI+window.
- **Between-group:** Cohen's `d = (mean1 − mean2) / pooled_sd`; use Hedges' `g` (small-sample bias correction `× (1 − 3/(4*(n1+n2)−9))`) when any group N < 20.
- **ANOVA effects:** partial eta-squared `ηp² = SS_effect / (SS_effect + SS_error)`.
- **CIs:** bootstrap over subjects (resample subjects with replacement, recompute the effect size, take the 2.5/97.5 percentiles) — robust and design-agnostic. For d, a noncentral-t CI is the parametric alternative.

```python
rng = np.random.default_rng(SEED)
boot = [cohens_dz(diff[rng.integers(0, len(diff), len(diff))]) for _ in range(5000)]
d_ci = np.percentile(boot, [2.5, 97.5])
```

Report the metric, its formula, N, and the CI. A CI that crosses 0 means the effect is not distinguishable from null at that level even if a cluster was "significant" elsewhere in the space.

### Equivalence testing (TOST) — affirming a null

A non-significant NHST result is *not* evidence of absence. To support a claim like "patients did not differ from controls" or "the manipulation had no effect," run **two one-sided tests** (TOST) against a **pre-registered** smallest effect size of interest (SESOI) — either a standardized bound (e.g., `dz = 0.3`) or a raw bound (e.g., ±0.5 µV) declared in `ANALYSIS_PLAN.md`. TOST tests whether the observed effect lies significantly *inside* `[−SESOI, +SESOI]`; a significant TOST combined with a non-significant NHST licenses a positive equivalence conclusion. This reuses the same per-subject ROI×window scores and pairs directly with the effect-size CI computed above (equivalence holds when the CI falls entirely within the SESOI bounds).

```python
# Paired/within: TOST against an effect-size SESOI (dz), n subjects, df = n-1
import scipy.stats as st
diff = X.mean(axis=(1, 2))                 # per-subject ROI×window difference
t = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff)))
df = len(diff) - 1
ncp = sesoi_dz * np.sqrt(len(diff))        # noncentrality for the bound
p_lower = st.nct.cdf(t,  df,  ncp)         # H0: effect ≤ −SESOI
p_upper = st.nct.sf(t,  df, -ncp)          # H0: effect ≥ +SESOI
p_tost = max(p_lower, p_upper)             # equivalent if p_tost < alpha
```

Record the SESOI, its origin (literature/clinical/prereg), `p_tost`, and the NHST p together. `pingouin.tost` (optional) gives a raw-units TOST in one call. Report the joint NHST×TOST outcome: significant difference, supported equivalence, or *inconclusive* (both non-significant — under-powered, not evidence of absence). Cite: Lakens, Scheel & Isager (2018). Equivalence testing for psychological research. *Advances in Methods and Practices in Psychological Science*, 1(2), 259–269.

## Phase G — Forest plot and outputs

A forest plot summarizes per-group / per-condition / per-subgroup effect sizes with CIs on one axis — the standard second-level visual for clinical/developmental contrasts.

- Build a table: rows = subgroups (or studies/sites), columns = `effect_size, ci_low, ci_high, n`. Plot each as a point + horizontal CI line; add a vertical line at 0 and (optionally) a pooled random-effects estimate. Render in `eeg-figure` (pass the table) or with matplotlib here.

Write per-claim:

### `group-stage/<claim_id>_group.json`
```json
{
  "claim_id": "C1", "design": "between", "groups": ["patient", "control"],
  "n_per_group": {"patient": 22, "control": 25}, "balanced": false,
  "test": "spatio_temporal_cluster_test", "stat": "F", "tail": 0,
  "n_permutations": 5000, "threshold": 3.94, "threshold_kind": "F(1,45) at p=.05",
  "seed": 42, "window": [0.18, 0.24], "roi_1020": ["Cz","CPz","Pz"],
  "window_matches_plan": true, "roi_matches_plan": true,
  "n_clusters": 2,
  "significant": [{"id": 0, "p": 0.008, "stat_sum": 812.4, "time_ms": [184, 236]}],
  "effect_size": {"metric": "hedges_g", "value": 0.61, "ci": [0.18, 1.03], "formula": "..."},
  "covariates": ["age"], "covariate_method": "MixedLM residualization",
  "adjacency": "Delaunay triangulation from digitized positions",
  "alpha": 0.05, "mc_correction": "cluster-FWER", "verdict": "supports"
}
```

### `group-stage/<claim_id>_arrays.npz`
Save `t_obs`/`f_obs`, `cluster_p` (or per-point `p_values` for TFCE), and `H0`.

### Append to `FINDINGS.md`
```markdown
## C1: [claim text]
- Result: [supports / does_not_support / partial]
- Test: [between cluster perm / mixed ANOVA], cluster p = [v], [N] perms, seed [S]
- Effect size: Hedges g = [v], 95% CI [lo, hi]
- Groups: patient N=22, control N=25 (unequal N; labels permuted)
- ROI: [channels], window: [time]
```

## Phase H — Sanity checks

- [ ] Observation unit is the subject, not the trial (array first dim == n_subjects).
- [ ] Between-group design has a `group_membership.csv`; group Ns reported.
- [ ] Every claim has `<claim_id>_group.json` with `window_matches_plan` and `roi_matches_plan` true.
- [ ] Every significant result reports an effect size **with CI**.
- [ ] `n_permutations` and `seed` match `ANALYSIS_PLAN.md`.
- [ ] Covariate handling documented when covariates are present.
- [ ] `FINDINGS.md` and `BACKEND_RESOLUTION.md` updated.

## Failure Modes

| Symptom | Action |
|---|---|
| `ANALYSIS_PLAN.md` missing/unfrozen or has placeholders | Stop. Ask user to fill and freeze the plan. |
| Between-group design, no `group_membership.csv` | Stop. Group labels are required; do not guess. |
| Severely unequal N (ratio > 3:1) | Proceed with cluster permutation (permutes labels) but warn; for ANOVA use `MixedLM`, not `AnovaRM`. |
| Only 1 subject per group | Stop. No population inference possible; report as single-subject, fixed-effects only. |
| `f_mway_rm` shape error | Pass `X` as a list of `prod(factor_levels)` per-cell arrays each `(subjects, features)`; inside `stat_fun` re-stack to `(subjects, cells, features)` via `np.swapaxes(np.array(args), 1, 0)`. Cell order: first factor slowest. |
| No significant clusters | Report as does_not_support. Do NOT rerun with new thresholds/perms. |
| Cluster spans the entire window | Report but warn: effect hits the analysis boundary — widen the window or note temporal non-specificity. |
| Groups differ on a covariate (e.g., age) | Add the covariate to `MixedLM` or residualize before the cluster test; document the method. |
| `pingouin` not installed | `pip install pingouin`, or fall back to `statsmodels` + hand-computed partial eta-squared. Log the substitution. |
| `statsmodels` unavailable | Use MNE `f_mway_rm` mass-univariate path; log that the scalar-ANOVA path was unavailable. |
| MNE-Python unavailable | Stop. MNE-Python is required for the cluster/TFCE tests. |
