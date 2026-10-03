# Certifying the cluster-permutation test

> **Correction (2026-09-13, from external review).** The first version of this document attributed
> the 18-vs-14 cluster discrepancy to "MNE's two-tailed default versus FieldTrip's one-tailed
> `clusteralpha`". That attribution was **wrong**. MNE's own default for a one-sided test
> (`threshold=None`, `tail=±1`) is `t.ppf(0.95, df)` = 1.729 at df 19 — the *same* convention as
> FieldTrip's one-tailed `clusteralpha=0.05`. The 2.093 threshold on the MNE side was supplied
> **explicitly by our certification script** (`t.ppf(0.975, df)`, an author-side reading of
> "α = 0.05"), not by the toolbox. The experiment therefore shows (i) that the two implementations
> agree exactly when given the same threshold and (ii) how sensitive cluster count and extent are to
> that one number — a *controlled threshold-sensitivity and conformance experiment*, not a
> disagreement between toolbox defaults. It is still an instance of "a phrase is not a numerical
> specification": "cluster-forming α = 0.05, one-sided" was implemented two ways *by us*.
> Second correction: this certification ran on the full epoch, whereas the shipped validation
> scripts test a component window (N400 300–500 ms, ERN 0–100 ms, N170 130–200 ms, P3 300–500 ms)
> at the one-sided default threshold. The **Shipped-configuration certification** section below
> re-runs the comparison at exactly that configuration.

**Why this one matters more than the amplitudes.** Every AEA recipe ends in a cluster-permutation
p-value. The ERP amplitudes feeding it were certified to nanovolts across three toolboxes — but the
number a paper actually *reports* had never been checked against a second implementation.
`tools/env/backends.json` said so in as many words: `stats.cluster_permutation` / `fieldtrip` /
`"measured": false`, with the note *"cluster tests are RNG- and threshold-sensitive; equivalence
must be measured, not assumed."*

This is that measurement.

## Design: what is comparable, and what is not

Two implementations of a permutation test **cannot** agree exactly on a p-value — they draw
different random permutations. Reporting a p-value match as success would be the same category
error as declaring two toolboxes equivalent because their grand means agree. So the comparison is
split before any number is looked at:

| | quantity | standard |
|---|---|---|
| **deterministic** | observed t-map; cluster count; each cluster's summed-t and extent | must match to numerical precision — a mismatch is a defect |
| **stochastic** | the p-values | can only agree within Monte Carlo error, `sqrt(p(1-p)/n)` |
| **the conclusion** | how many clusters are significant | this is what a paper reports |

**One adjacency graph, used by both.** MNE builds channel adjacency by Delaunay triangulation of
the montage; FieldTrip builds it from `cfg.neighbours`. Letting each pick its own would measure
montage geometry rather than the test, so the adjacency is computed once, exported, and both sides
cluster over the identical 30-channel / 78-edge graph.

Data: ERP CORE N400, 20 subjects × 30 channels × 257 samples, `reject=None`, 5000 permutations.

## Result

### Historical: at the two thresholds originally run (superseded — see the correction at the top)

> *This subsection is kept as the record of what was run. Its original heading called the two
> thresholds "each toolbox's own reading"; that was wrong — the 2.093 threshold was supplied by our
> script, and MNE's own default equals FieldTrip's. Read it as a threshold-sensitivity experiment.*

| | MNE-Python | FieldTrip |
|---|---:|---:|
| observed t-map, `sum|t|` | 13832.4844 | **13832.4844** |
| observed t-map, `min t` | −8.3007 | **−8.3007** |
| clusters | 14 | **18** |
| leading cluster summed-t | −4577.61 | **−4865.79** (6.3% larger) |
| leading cluster extent | 1268 | **1419** points |
| significant clusters | 1 | 1 |

**The t-statistic agrees to machine precision (max |Δ| 1.8×10⁻¹⁵ — not bit-identical, see ELEMENTWISE_*.json). The clustering is not.**

### The cause: "alpha = 0.05" does not say which tail

MNE forms clusters at the **two-tailed** critical value; FieldTrip's `cfg.clusteralpha` with
`cfg.tail = -1` is **one-tailed**:

```
MNE        t.ppf(0.975, 19) =  2.0930
FieldTrip  t.ppf(0.050, 19) = -1.7291     <- 83% as strict, so more samples survive
```

Both are defensible readings. They are not the same test.

### With the tail convention pinned (`clusteralpha = 0.025`)

| | MNE-Python | FieldTrip | difference |
|---|---:|---:|---:|
| clusters | 14 | **14** | — |
| leading cluster summed-t | −4577.6083 | **−4577.6083** | **0.00e+00** |
| leading cluster extent | 1268 | **1268** | — |
| significant clusters | 1 | 1 | same |

> **With the cluster-forming tail pinned, the two implementations produce exactly identical
> cluster partitions** (elementwise Boolean membership equality, all four components), **with
> observed t-maps equal to machine precision** (max |Δ| = 1.8×10⁻¹⁵ ≈ 2 ulp; the two toolboxes sum
> in different orders, so the last floating-point bit differs) **and summed-t statistics agreeing
> to every printed digit.** "Bit-identical" was the first draft's wording; the elementwise
> evidence (ELEMENTWISE_*.json) shows machine-precision equality, which is the claim the data
> support.

### Generalization: four components, both tails (added 2026-08-19)

The original run was N400 only. Re-run with the tail parameterized (P3b is a *positive*
deflection — the `tail = +1` branch's first real execution) and the cluster-forming threshold
pinned at `clusteralpha = alpha/2`:

| component | tail | leading summed-t (MNE = FieldTrip) | extent | significant | leading p (MNE / FT) |
|---|:---:|---:|---:|:---:|---:|
| N400 | −1 | −4577.6083 | 1268 | 1 = 1 | 0.0002 / 0.0002 |
| ERN  | −1 | −3714.0887 | 1175 | 1 = 1 | 0.0004 / 0.0004 |
| P3b  | **+1** | +1741.5953 | 516 | 2 = 2 | 0.0002 / 0.0004 |
| N170 | −1 | −584.3781  | 198 | 2 = 2 | **0.0124 / 0.0128** |

Every leading summed-t matches to relative difference **0.00e+00** (printed precision), in both
effect directions — and the committed elementwise evidence (`ELEMENTWISE_{N400,P3,N170,ERN}.json`)
shows the full t-maps equal to machine precision (max |Δ| 1.8×10⁻¹⁵) with **exactly identical
cluster partitions** in all four.

N170 also supplies what the original design admitted it lacked: a leading cluster **away from the
permutation floor**. Its p of 0.0124 vs 0.0128 differs by 0.0004 ≈ 0.25 Monte Carlo SE at n = 5000
— the stochastic half of the comparison finally has room to discriminate, and still agrees.

## Shipped-configuration certification (added 2026-09-13)

The runs above used the full epoch and an author-supplied `t.ppf(0.975, df)` threshold. The shipped
validation scripts (`tools/validation/validate_*_group.py`) test a component window at the
one-sided default threshold. This section certifies **exactly that configuration**: both scripts
crop to the identical samples (exact sample times passed to both), MNE runs with `threshold=None`
(its one-sided default), FieldTrip with `clusteralpha=0.05` one-tailed — the same number.

| component | window (s) / samples | threshold | clusters MNE / FT | leading summed-t (MNE = FT) | extent | p MNE / FT | partitions | t-map max \|Δ\| |
|---|---|---|---|---|---|---|---|---|
| N400 | 0.301–0.500 / 52 | −1.729 (df 19) | 1 / 1 | −2102.7135 | 518 | 0.0002 / 0.0002 | identical | 1.8×10⁻¹⁵ |
| ERN | 0.000–0.098 / 26 | −1.771 (df 13) | 1 / 1 | −1014.8257 | 257 | 0.0004 / 0.0006 | identical | 1.8×10⁻¹⁵ |
| N170 | 0.133–0.199 / 18 | −1.729 (df 19) | 1 / 1 | −645.1424 | 166 | 0.0002 / 0.0004 | identical | 1.8×10⁻¹⁵ |
| P3 | 0.301–0.500 / 52 | +1.729 (df 19) | 2 / 2 | +1368.8935 | 415 | 0.0002 / 0.0004 | identical | 1.8×10⁻¹⁵ |

Two things this closes. First, the MNE side of this run reproduces the committed validation
results **to the digit** — cluster counts (1, 1, 1, 2) and p-values (0.0002, 0.0004, 0.0002, 0.0002)
equal `tools/validation/*_results.json` — so the certified configuration *is* the shipped analysis,
not a proxy for it. Second, FieldTrip agrees at that configuration exactly as it did on the full
epoch: partitions identical (Boolean equality after canonical matching), t-maps at machine
precision, summed-t to every printed digit; only the Monte-Carlo p-values differ, within their
sampling error. Evidence: `cluster_cert/{mne,fieldtrip}_<C>_shipped.json`,
`ELEMENTWISE_shipped_<C>.json`, and the raw t-map / label-map dumps `cluster_cert/dumps_shipped/`.
The two runs are different experiments and their p-values must not be blended: the full-epoch run
gives N170 p = 0.0124 (MNE) vs 0.0128 (FieldTrip); the shipped-window run gives 0.0002 vs 0.0004.
The FieldTrip p-values in this table come from a re-run made to record the analysed dimension in
the JSON metadata; the FieldTrip side is not seeded, and its p-values moved by one or two
permutation counts between runs (e.g. N400 0.0004 → 0.0002) while every deterministic quantity
stayed identical — which is exactly why p-values are excluded from all exactness claims.
MMN is absent because no cluster input was exported for it (its rejection step makes the
subject-level contrast waves toolbox-dependent); this is a stated gap, not an omission.

## Findings

**1. The statistic AEA's conclusions rest on is now certified, at machine precision.** Cluster
partitions are exactly identical (Boolean equality after canonical matching, four components,
committed elementwise evidence); observed t-maps agree to ≈2 ulp; summed-t statistics agree to all
printed digits.

**2. This is the seventh instance of the project's recurring pattern, and the most consequential.**
The previous six were about preprocessing — RANSAC on/off, the reference scheme, window-edge sample
alignment, "±100 µV" peak-to-peak vs absolute, the filter cutoff convention, the transition width.
This one is in **the inferential statistic itself**. `alpha = 0.05` appears in thousands of EEG
papers, and for a cluster-forming threshold it does not say one-tailed or two-tailed — an 83%
difference in strictness, and here a 12% difference in the extent of the reported cluster.

**3. The conclusion was robust anyway.** One significant cluster either way, p at the permutation
floor. Consistent with everything else measured in this project: group conclusions survive an
under-specified pipeline; the reported *details* — cluster extent, summed-t, which samples are in
the cluster — do not. A paper quoting "a significant cluster from 300–500 ms" is quoting the part
that moves.

## Honest limitations

1. **Four components (N400, P3b, N170, ERN), one dataset.** Both effect directions covered; all
   four with exactly identical partitions and machine-precision t-maps once the threshold is pinned. MMN was not run — nothing prevents it, the exported
   input is per-subject difference waves either way — so the count is four, not five.
2. **The FieldTrip arm is not 100% third-party code.** FieldTrip's `clusterstat`/`findcluster`
   call `spm_bwlabel`, and the bundled SPM8 ships only MATLAB MEX binaries that Octave cannot load.
   A pure-Octave connected-component labeller is supplied in `octave_shims/`, verified against
   `scipy.ndimage.label` on 12 random 3-D inputs (12/12). It is a utility with no free parameters;
   FieldTrip still contributes the t-statistic, the threshold, the maxsum cluster statistic, the
   permutation scheme and the p-value. But "independent implementation" now has an asterisk, and
   this is it.
3. ~~p-values at the permutation floor~~ **Resolved by the extension:** N170's leading cluster sits
   off the floor (0.0124 vs 0.0128, ≈0.25 Monte Carlo SE apart), so the stochastic comparison now
   discriminates — and agrees.
4. **Only the one-sample/paired case** was compared; between-groups and F-tests were not.

## Reproduce

Shipped configuration (component window at the one-sided default threshold; both sides cropped to
the identical samples — pass exact sample times):

```bash
# MNE side (threshold=None == one-sided t.ppf(0.95, df))
python tools/benchmark/cluster_cert_mne.py --input tools/benchmark/cluster_cert/cluster_input_N400.mat \
  --tail -1 --threshold auto --tmin 0.30078125 --tmax 0.5 \
  --out tools/benchmark/cluster_cert/mne_N400_shipped.json --dump /tmp/mne_N400.mat
# FieldTrip side (clusteralpha 0.05 one-tailed == the same number)
INPUT=$PWD/tools/benchmark/cluster_cert/cluster_input_N400.mat OUTFILE=tools/benchmark/cluster_cert/fieldtrip_N400_shipped.json \
  DUMP=/tmp/ft_N400.mat CLUSTERALPHA=0.05 TAIL=-1 NPERM=5000 LATENCY="0.30078125 0.5" \
  $OCTAVE_HOME/bin/octave-cli --no-gui --quiet tools/benchmark/cluster_cert_fieldtrip.m
python tools/benchmark/compare_cluster_elementwise.py --mne /tmp/mne_N400.mat --fieldtrip /tmp/ft_N400.mat \
  --component N400 --tail -1 --out tools/benchmark/cluster_cert/ELEMENTWISE_shipped_N400.json
```
Windows: N400 0.30078125–0.5, ERN 0.0–0.09765625, N170 0.1328125–0.19921875, P3 0.30078125–0.5 (tail +1).

Historical full-epoch configuration (author-supplied `t.ppf(0.975, df)`; FieldTrip `CLUSTERALPHA=0.025`):

```bash
python tools/benchmark/export_cluster_input.py --component N400
python tools/benchmark/cluster_cert_mne.py \
    --input tools/benchmark/cluster_cert/cluster_input_N400.mat \
    --out   tools/benchmark/cluster_cert/mne_N400.json

export OCTAVE_HOME=$HOME/miniconda3/envs/octave FT_DIR=/path/to/fieldtrip
INPUT=$PWD/tools/benchmark/cluster_cert/cluster_input_N400.mat \
OUTFILE=$PWD/tools/benchmark/cluster_cert/fieldtrip_N400_a025.json CLUSTERALPHA=0.025 \
  $OCTAVE_HOME/bin/octave-cli --no-gui --quiet tools/benchmark/cluster_cert_fieldtrip.m

python tools/benchmark/compare_cluster_cert.py \
    --a tools/benchmark/cluster_cert/mne_N400.json \
    --b tools/benchmark/cluster_cert/fieldtrip_N400_a025.json
```
