# ANALYSIS_PLAN — `mne-sample-audvis`

> Frozen before any analysis runs.

## Plan version

- **Plan version:** v1
- **Frozen at:** 2026-05-22 22:15
- **Frozen by:** AEA case study

## Claim → contrast → test mapping

| Claim ID | Plain-language claim | Contrast | Channels / ROI | Time window | Freq band | Test | Direction predicted | α |
|---|---|---|---|---|---|---|---|---|
| C1 | Auditory stimuli elicit larger N100 than visual | auditory_avg − visual_avg | Fz, Cz, FC1, FC2, F3, F4 | 0.08 – 0.15 s | n/a | cluster perm, paired within-subject (1-sample on difference) | auditory more negative | 0.05 |

## Multiple-comparisons strategy

- **Across claims:** single claim, no correction needed
- **Within a claim:** permutation test handles family-wise within cluster space

## Exclusion criteria (subject-level)

- More than 30% of epochs rejected → exclude
- ≤ 10 retained trials in any condition → exclude

## RNG seeds

- ICA: 42
- AutoReject: 42
- Cluster permutation: 42

---

## Revision log

- v1 (2026-05-22) — initial freeze. Single claim: auditory N100 > visual.
