# ANALYSIS_PLAN — `<study-name>`

> Frozen before any analysis runs. The agent must NOT edit this file after a stage has executed. Negative or contradictory results go in `FINDINGS.md`, not back into the plan.

## Plan version

- **Plan version:** `v1`
- **Frozen at:** `<YYYY-MM-DD HH:MM>`
- **Frozen by:** `<user name>`
- **Reason for any later revision:** `<append below — never overwrite>`

## Claim → contrast → test mapping

Every claim in the eventual paper must trace to one row here. The audit skill enforces this.

| Claim ID | Plain-language claim | Contrast | Channels / ROI | Time window | Freq band (if TFR) | Test | Direction predicted | α |
|---|---|---|---|---|---|---|---|---|
| C1 | `<valid-cue elicits stronger N1 vs invalid>` | `valid - invalid` | `PO7, PO8, O1, O2` | `0.10 – 0.20 s` | n/a | `cluster perm, paired t` | `valid more negative` | `0.05` |
| C2 | `<alpha desync larger for valid in 0.4–0.8s>` | `valid - invalid` | `Pz, P3, P4, POz` | `0.40 – 0.80 s` | `8–13 Hz` | `cluster perm, paired t (TFR)` | `valid more negative log-power change` | `0.05` |
| C3 | … | … | … | … | … | … | … | … |

## Multiple-comparisons strategy

- **Across claims:** `<Bonferroni N=3 | hierarchical primary→secondary | …>`
- **Within a claim (cluster perm):** `permutation test handles family-wise within the cluster space — no further correction inside`
- **Reporting standard:** report `cluster t_obs, cluster p, n_permutations, RNG seed, cluster-forming threshold`. No exception.

## Subgroup / interaction analyses (if any)

| Analysis | Pre-registered? | Justification |
|---|---|---|
| `<sex × condition interaction on C1>` | Yes / No | `<…>` |

> Subgroup analyses NOT pre-registered are exploratory and must be labeled as such in the report.

## Exclusion criteria (subject-level)

- More than `<30%>` of epochs rejected after AutoReject → exclude subject.
- ICA failed to converge after `<3>` re-runs → exclude subject.
- Behavioral accuracy below chance + `<2 SD>` → exclude subject.
- ≤ `<10>` retained trials in any analyzed condition → exclude subject for that contrast only.

## Backend overrides for this study

- `eeg-stats: BACKEND = mne`

## RNG seeds

- ICA: `<42>`
- AutoReject: `<42>`
- Cluster permutation: `<42>`
- Microstate k-means: `<42>`

> The audit skill verifies every `*-stage/` output records the seed it actually used.

---

## Revision log

> Append-only. Each revision must say *why* and what stages need re-run.

- `v1 (2026-MM-DD)` — initial freeze.
