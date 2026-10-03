# FIGURE_PLAN — `<study-name>`

> Maps each claim in `ANALYSIS_PLAN.md` to one or more paper-ready figures. The figure skill renders to `figure-stage/` in both SVG (editable) and PNG (preview).

## Figure list

| Fig ID | Tied to claim | Type | Panels | Source data | Output |
|---|---|---|---|---|---|
| F1 | C1 | ERP butterfly + topomap | (a) butterfly per condition, (b) difference wave with cluster mask, (c) topomap at peak | `erp-stage/`, `stats-stage/C1_cluster_perm.json` | `figure-stage/F1_C1_erp.svg` |
| F2 | C2 | TFR + topomap timeline | (a) TFR per condition, (b) TFR difference with cluster mask, (c) alpha-band topomap timeline | `tfr-stage/`, `stats-stage/C2_cluster_perm.json` | `figure-stage/F2_C2_tfr.svg` |
| F3 | C3 | Microstate template + transitions | (a) microstate maps A/B/C/D, (b) coverage per condition, (c) transition matrix | `microstate-stage/` | `figure-stage/F3_C3_microstate.svg` |
| F4 | C4 | Source localization | (a) sLORETA at peak time, (b) glass brain top-25 dipoles | `source-stage/` | `figure-stage/F4_C4_source.svg` |

## Style constraints (paper-ready by default)

- **Color map for difference plots:** `RdBu_r` symmetric around 0, vmin/vmax explicit (no auto-scaling).
- **Color map for power:** `viridis`, never `jet`.
- **Topomap interpolation:** `cubic`, head outline visible.
- **Significance masking:** non-significant samples shown but de-saturated (alpha=0.4); cluster outline drawn.
- **Font:** sans-serif, 8 pt min for labels, 10 pt for axis titles.
- **Figure size:** target single-column 89 mm or double-column 183 mm — declare per figure.
- **DPI for raster preview:** 300; SVG is the source of truth.
- **Colorblind-safe:** prefer Okabe-Ito for categorical; never red/green for opposing conditions.

## What NOT to do

- No 3D rotated topomaps without explicit user request (hard to read in print).
- No bar charts with SEM only — show distribution (violin/strip) + 95% CI.
- No "p = 0.000" — use `p < 0.001`.
- No horizontal lines connecting non-adjacent significant clusters as if continuous.
- No cherry-picked color limits to make small effects look large — limits must be symmetric and stated in the caption.

## Caption template (one per figure)

```
Figure F<n>. <plain-language claim>. (a) <panel a description>. (b) <panel b>.
Cluster permutation, n=<N>, <K> permutations, seed <S>, cluster-forming
threshold t=<t_thr>. Cluster p=<p>, t_obs=<sum>, channels {<...>}, time <a–b s>.
Effect size: <Cohen's dz = X>. Shaded region: <…>. Color limits: <vmin, vmax>.
```
