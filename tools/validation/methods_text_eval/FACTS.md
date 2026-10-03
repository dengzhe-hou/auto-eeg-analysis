# Ground-truth pipeline facts for the methods-text evaluation

Exact parameters of three validated AEA pipelines (from `tools/validation/validate_*_group.py` +
recipe specs). These are the facts a correct COBIDAS-MEEG methods paragraph must report — and the
key against which coverage (did it report the item?) and accuracy (right value? nothing fabricated?)
are scored. **Deliberate gaps** are marked ⚠️ ABSENT — a faithful generator must say "not reported"
/ omit, NOT invent a value.

## P-MMN — ERP CORE Mismatch Negativity
- Sample: ERP CORE MMN dataset; enrolled N=40, analyzed N=38, excluded 2 (sub-007, sub-012: <50 retained deviants).
- Demographics: ⚠️ ABSENT (not provided).
- Acquisition: BioSemi ActiveTwo; 30 scalp EEG + 3 EOG (33 channels); online reference CMS/DRL; online filter ⚠️ ABSENT (DC recording, not stated); sampling rate 1024 Hz.
- Preprocess: MNE-Python 1.11.0; band-pass 0.1–30 Hz, FIR, zero-phase; notch ⚠️ ABSENT (none applied); resample to 256 Hz; re-reference to average (30 EEG; 3 EOG dropped); bad-channel detection ⚠️ ABSENT (not run).
- ICA: ⚠️ NOT RUN (n/a).
- Epoch: −0.2 to 0.5 s; baseline −0.2 to 0 s; artifact rejection peak-to-peak 100 µV (MNE); min-trial rule ≥50 deviants & ≥150 standards.
- Stats: contrast deviant−standard; ROI Fz/FCz/Cz; window 100–250 ms; second-level spatiotemporal cluster-permutation (MNE `spatio_temporal_cluster_1samp_test`); 5000 permutations; seed 42; cluster-forming threshold = t at p<0.05; adjacency Delaunay (`find_ch_adjacency`); alpha 0.05; tail −1 (one-sided, MMN negative); effect size Cohen's dz. Result: −0.840 µV, t(37)=−7.87, p=2.0×10⁻⁹, cluster p=0.0002, dz=−1.28.
- Source stage: none (items 27–31 = n/a).

## P-P3 — ERP CORE P3b
- Sample: ERP CORE P3; enrolled N=20, analyzed N=20, excluded 0.
- Demographics: ⚠️ ABSENT.
- Acquisition: BioSemi ActiveTwo; 30 EEG + 3 EOG; online reference CMS/DRL; online filter ⚠️ ABSENT; sampling rate 1024 Hz.
- Preprocess: MNE-Python 1.11.0; band-pass 0.1–30 Hz FIR zero-phase; notch ⚠️ ABSENT; resample 256 Hz; average reference (30 EEG); bad-channel ⚠️ ABSENT.
- ICA: NOT RUN.
- Epoch: −0.2 to 0.8 s; baseline −0.2 to 0 s; artifact rejection NONE (reject=None — all epochs averaged); min-trial rule ≥30 target & ≥100 standard.
- Stats: contrast target−standard; ROI Fz/Cz/Pz/CPz; window 300–500 ms; second-level cluster-permutation; 5000 permutations; seed 42; threshold t at p<0.05; Delaunay adjacency; alpha 0.05; tail +1 (P3 positive); Cohen's dz. Result: +1.683 µV, t(19)=+4.15, p=5.4×10⁻⁴, cluster p=0.0002, dz=+0.93.
- Source stage: none.

## P-N170 — ERP CORE N170 (face selectivity)
- Sample: ERP CORE N170; enrolled N=20, analyzed N=20.
- Demographics: ⚠️ ABSENT.
- Acquisition: BioSemi ActiveTwo; 30 EEG + 3 EOG; online reference CMS/DRL; online filter ⚠️ ABSENT; sampling rate 1024 Hz.
- Preprocess: MNE-Python 1.11.0; band-pass **0.1–40 Hz** FIR zero-phase (note: 40 Hz, not 30); notch ⚠️ ABSENT; resample 256 Hz; average reference (30 EEG); bad-channel ⚠️ ABSENT.
- ICA: NOT RUN.
- Epoch: −0.2 to 0.5 s; baseline −0.2 to 0 s; artifact rejection NONE (reject=None); min-trial rule ≥30 per condition.
- Stats: contrast face−car; ROI PO7/PO8/P7/P8; window 130–200 ms; second-level cluster-permutation; 5000 permutations; seed 42; threshold t at p<0.05; Delaunay adjacency; alpha 0.05; tail −1 (N170 negative); Cohen's dz. Result: face−car negative, dz=−0.99, cluster p=0.0002.
- Source stage: none.

## Applicable-item map (for coverage scoring)
- Items 1,3,4,5,7,8,10,17,18,19,20,21,22,23,24,25,26 = **APPLICABLE** (must be reported) for all three.
- Items 2 (demographics), 6 (online filter), 9 (notch), 11,12 (bad-channel) = data ABSENT → correct behavior is to report "not reported"/"none applied", NOT fabricate.
- Items 13–16 (ICA) = n/a (ICA not run) → correct behavior is to state "no ICA" or omit.
- Items 27–31 (source) = n/a (no source stage).
