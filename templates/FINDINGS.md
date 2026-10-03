# FINDINGS — `<study-name>`

> Append-only running log. Every stage adds a block; no edits to prior blocks. The audit skill cross-checks `FINDINGS.md` against `stats-stage/` outputs.

## Format per entry

Each entry: timestamp, stage, claim ID it relates to (if any), one-line headline, supporting numbers, location of artifacts. Negative and unexpected results get their own entries.

---

## `2026-MM-DD HH:MM` — eeg-preprocess complete

- **N subjects in:** `<32>` / **N out:** `<30>` (2 dropped: `<sub-014: 38% bad-channel reconstruction; sub-021: HEOG saturated>`)
- **Mean bad channels per subject:** `<2.4 / 64>` (range `<0–7>`)
- **Line noise after notch:** `<–18 dB attenuation>`
- **Artifact path:** `preprocess-stage/`

---

## `2026-MM-DD HH:MM` — eeg-ica complete

- **N components retained per subject (mean ± SD):** `<48 ± 6>`
- **Components auto-rejected (eye/muscle/heart/line) per subject:** `<eye 2.1, muscle 1.4, heart 0.3, line 0.2>` (mne-icalabel)
- **Subjects flagged for manual ICA review:** `<sub-003 (frontal eye comp ambiguous)>`
- **Artifact path:** `ica-stage/`

---

## `2026-MM-DD HH:MM` — C1 (valid vs invalid N1) tested

- **Test:** cluster permutation, paired t, 5000 permutations, seed 42, cluster-forming threshold t=2.05
- **Result:** `<largest negative cluster p=0.018, t_obs sum=–142.3, channels {PO7, PO8, O1}, time 0.118–0.176 s>`
- **Direction:** `<matches predicted direction>`
- **Effect size:** `<Cohen's dz = 0.62>`
- **Verdict relative to plan:** ✅ Supports C1.
- **Artifact path:** `stats-stage/C1_cluster_perm.json`

---

## `2026-MM-DD HH:MM` — C2 (alpha desync) tested

- **Test:** cluster permutation TFR, paired t, 5000 perms, seed 42
- **Result:** `<no cluster reached p<0.05; smallest cluster p=0.21>`
- **Direction:** n/a (no significant cluster)
- **Verdict relative to plan:** ❌ Does not support C2 at α=0.05. Plan unchanged. Reported as null result.
- **Artifact path:** `stats-stage/C2_cluster_perm.json`

---

## Exploratory observations (NOT pre-registered)

> Tagged so the audit skill can flag them as exploratory in any downstream report.

- `<exploratory: theta-band increase 0.3–0.5s in central electrodes — followup in next study>`

---

## Re-runs / corrections

> If a stage was re-run with different parameters, log the diff and the reason. Never delete the old entry.
