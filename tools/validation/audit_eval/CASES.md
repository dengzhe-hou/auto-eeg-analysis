# eeg-audit seeded-defect evaluation — test cases

Nine short ERP "Methods & Results" summaries: **1 clean control + 8 each carrying exactly one
well-known EEG methodological defect**. A blind auditor (given only the `eeg-audit` checklist and one
case, unaware a defect was seeded) writes a Reviewer-2 memo. We score whether it flags the seeded
defect (recall) and whether it fabricates a major flaw on the clean case (specificity). Ground truth
in `KEY.json`. Defects map to the `eeg-audit` SKILL.md checklist.

---

## C0 — CLEAN (control; no seeded major flaw)
Auditory oddball, 24 adults, 64-ch BioSemi, 0.1–30 Hz zero-phase FIR, average reference. ICA (ICLabel,
mean 8.2 components/subject removed). Epochs −200 to 800 ms, baseline −200 to 0 ms, ±100 µV rejection
(mean 11.8% rejected, comparable across conditions: target 12.1%, standard 11.5%). Primary contrast
target − standard at Cz/CPz/Pz, 250–500 ms, one planned contrast. Spatiotemporal cluster-based
permutation test (5000 permutations, seed 42, Delaunay adjacency, cluster-forming threshold p<.05
two-sided). Analysis plan pre-registered on OSF before data collection. Result: target > standard,
cluster p = .002. Backend: MNE-Python 1.6, reported.

## C1 — circular analysis (double dipping)
Visual N170 study, 20 adults, faces vs houses. We inspected the grand-average difference across all
electrodes and time points, **selected the electrode (PO8) and window (156–172 ms) showing the largest
face−house difference, and then tested that electrode/window**, finding p < .001. (Everything else
well-reported: 0.1–30 Hz, average ref, baseline −200–0, ICA, ±100 µV.)

## C2 — no multiple-comparisons correction
Emotion-word ERP, 28 adults. We compared pleasant vs neutral at **each of 64 channels and every time
point 0–1000 ms (500 samples) using pointwise t-tests at p < .05, uncorrected**, and report 428
significant channel×time points as evidence of an emotion effect. (Filtering 0.1–30 Hz, average ref,
baseline applied, rejection rates reported.)

## C3 — post-hoc exclusion based on the result
P300 oddball, 30 adults. After averaging, **6 participants were excluded because their target−standard
difference did not reach significance / went the "wrong" direction**, leaving 24 with a clear P300
(p = .004). No pre-registered exclusion criteria. (Otherwise well-reported: filter, reference,
baseline, cluster test with seed/adjacency.)

## C4 — inappropriate high-pass filter for a slow component
N400 semantic study, 26 adults, related vs unrelated words. Continuous EEG was **high-pass filtered at
1.0 Hz** (4th-order Butterworth) before epoching, then the N400 (a slow 300–600 ms negativity) was
measured. (Average reference, baseline −200–0, ICA, ±100 µV, one planned contrast, cluster test fully
specified.)

## C5 — no baseline correction
MMN passive oddball, 22 adults. Epochs −200 to 500 ms around standards and deviants. **No baseline
correction was applied**; the deviant−standard difference at Fz/FCz (100–250 ms) was −0.9 µV,
cluster p = .01. (Filter 0.1–30 Hz, average ref, ICA, ±100 µV rejection reported, adjacency + seed
reported.)

## C6 — cluster test underspecified (threshold/adjacency/perm not reported)
ERN flankers, 25 adults, error vs correct at FCz. Response-locked, 0–100 ms. **"A cluster-based
permutation test showed a significant ERN (p < .05)."** No cluster-forming threshold, no adjacency
definition, no permutation count, no seed, no tail reported. (Filter, reference, baseline, rejection
rates all fine; one planned contrast.)

## C7 — rejection rates omitted + large unequal N per condition unacknowledged
Face-inversion N170, 21 adults, upright vs inverted. After artifact rejection, condition ERPs were
averaged. **Rejection rate not reported; upright had ~180 trials retained, inverted ~55, and this
imbalance is not mentioned** (inverted trials were noisier). (Filter 0.1–30, average ref, baseline,
ICA, cluster test specified, one planned contrast.)

## C8 — reference not reported
Auditory P2 study, 23 adults, loud vs soft tones. Methods describe filtering (0.1–30 Hz FIR), ICA,
epoching (−200–600, baseline −200–0), ±100 µV rejection with rates, and a fully-specified cluster
test — but **the EEG reference (online and offline re-reference) is never stated** anywhere. P2 at Cz,
150–250 ms, cluster p = .008.
