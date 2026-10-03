---
name: eeg-qc
description: "Automated EEG data-quality dashboard: per-channel SNR/variance/Hurst, PSD-based bad-channel and line-noise detection, flatline/high-amplitude flags, channel & epoch rejection-rate reporting, before/after SNR per pipeline stage, head-motion/EMG indices, and an overall QC report (mne.Report + JSON) with pass/warn/fail gates. Runs BEFORE analysis to catch bad data early. Backend: MNE-Python. Use when user says 'QC', 'data quality', 'quality check', 'is this data usable', 'check my recordings', or before committing to an analysis."
argument-hint: "[project-dir] [— stage: raw|preprocess|ica|epoch|all] [— gates: strict|normal|lenient] [— subjects: sub-01,...]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# eeg-qc: automated data-quality dashboard

## Context: $ARGUMENTS

Compute a per-subject, per-channel, per-stage quality report so bad data is caught **before** it costs analysis time. This skill does not clean data — it *measures* the data that `eeg-preprocess` / `eeg-ica` / `eeg-epoch` produced, scores it against published gates, and emits a pass/warn/fail verdict plus an `mne.Report` HTML and machine-readable JSON. It is diagnostic, not corrective: a `fail` here routes the user back to a preprocessing decision, never to a silent fix.

## Constants

- **BACKEND = `mne`** — MNE-Python is the computation backend.
- **OUTPUT_DIR = `qc-stage/`** — relative to project root. Create if missing.
- **STAGES = `all`** — which stages to QC: `raw` (pre-preprocess sanity), `preprocess`, `ica`, `epoch`, or `all`. Each consumes the matching `*-stage/` directory.
- **GATES = `normal`** — gate strictness preset (`strict` | `normal` | `lenient`). Sets the pass/warn/fail thresholds in Phase F. The chosen preset and every numeric threshold are written verbatim to `qc-stage/QC_GATES.json` (no hidden thresholds — COBIDAS).
- **LINE_FREQ = inferred from country** — 50 Hz (Japan/EU/most) or 60 Hz (Americas) — confirmed against `DATASET_BRIEF.md > Notch`. Used for the line-noise ratio.
- **FMIN/FMAX = `1` / `40`** Hz — PSD analysis band for SNR and bad-channel scoring. Raise FMAX for high-gamma studies.
- **HURST_EPOCH_S = `4.0`** — window length for the per-channel Hurst/DFA estimate (scaling needs longer epochs than band power; see Domain Knowledge → Hurst). OPTIONAL — degrades to variance+correlation if no DFA backend.
- **SEED = read from ANALYSIS_PLAN**, default `42` — for any subsampled metric (LOF neighbor draws are deterministic; AutoReject preview is seeded).
- **N_JOBS = `4`** — parallelism for PSD computation.

> Override: `/eeg-qc projects/my-study — stage: preprocess — gates: strict — subjects: sub-01,sub-02`

## Required Inputs

QC adapts to whatever stages exist; at least one must be present.

1. `DATASET_BRIEF.md` — for line frequency, montage, expected channel count, paradigm (resting vs task). **Stop if it has `<…>` placeholders for the line freq or montage.**
2. `ENVIRONMENT.json` — to resolve MNE and check optional QC deps (`pyprep`, `autoreject`, `antropy`/`nolds`).
3. One or more stage directories:
   - `raw/` — raw recordings (for the pre-preprocess `raw` stage sanity pass).
   - `preprocess-stage/<sub>/*_preprocessed_raw.fif` + `preprocess_summary.json`.
   - `ica-stage/<sub>/*-clean-raw.fif` + `ica_labels.json`.
   - `epoch-stage/<sub>/*-epo.fif` + `*-reject-log.json`, `TRIAL_COUNT_TABLE.csv`.
4. Optional: `channel_mapping.json` (to report bad channels in 10-20 names), `ANALYSIS_PLAN.md` (for the analyzed-conditions list and seed).

## Phase A — Inventory and plan

1. Read `DATASET_BRIEF.md` and `ENVIRONMENT.json`. Resolve `LINE_FREQ`, montage, expected channel count, paradigm.
2. Probe backends and record availability — `pyprep` and `autoreject` are **core** deps (`environment.yml`), so expect them present, but still check and degrade rather than crash if a stripped env lacks one:
   - `pyprep` (core) — `NoisyChannels` for RANSAC + FASTER-style channel metrics, corroborates LOF.
   - `autoreject` (core) — `get_rejection_threshold` for a data-driven epoch-reject preview.
   - `antropy` / `nolds` — **genuinely optional** (`requirements-optional.txt`), only needed for Hurst/DFA. If neither imports, Hurst degrades to a documented `not_computed` with a logged substitution; the rest of the dashboard is unaffected.
3. Discover which stages have data. For each present stage, list subjects.
4. Write `qc-stage/QC_PLAN.json` (stages to run, subjects, line freq, band, gate preset, available optional backends) **and** `qc-stage/QC_GATES.json` (every pass/warn/fail threshold for the chosen preset). Print both. No metric below uses a threshold absent from `QC_GATES.json`.

## Phase B — Per-channel quality metrics (per subject, per stage)

For each subject's continuous data at each present stage, write and execute a script that computes, per EEG channel:

### B.1 Amplitude / variance / flatline / high-amplitude

- **Variance / RMS** per channel (`np.var`, `np.sqrt(np.mean(x**2))` on `raw.get_data(picks='eeg')`). Robust z-score each channel's log-variance against the across-channel median/MAD; `|z| > 3` flags a deviant channel (FASTER channel criterion, Nolan et al. 2010).
- **Flatline detection**: channels whose peak-to-peak over the recording (or in ≥`bad_percent` of the data) is below a floor. Use MNE's amplitude annotator, which flags *both* flat and high-amplitude segments in one pass:
  ```python
  from mne.preprocessing import annotate_amplitude
  annots, flat_chs = annotate_amplitude(
      raw, peak=dict(eeg=PEAK_V),   # high-amplitude segment threshold (e.g. 150e-6)
      flat=dict(eeg=FLAT_V),        # flat threshold (e.g. 5e-7 = 0.5 µV ptp)
      bad_percent=5.0,              # a channel flat/peaky in >5% of samples → bad channel
      min_duration=0.005)
  # annots: mne.Annotations ('BAD_flat' / 'BAD_high'); flat_chs: persistently-flat channel names
  raw.set_annotations(raw.annotations + annots)   # for the % bad-time metric below
  ```
  `flat_chs` are persistently dead channels (report as bad-channel candidates); the `BAD_*` annotations give the **percent of recording time** lost to flat/saturated segments (a per-subject metric, Phase D).
- **High-amplitude / saturation**: the `peak=` side of the same call. Saturated/clipped channels (rail-to-rail) appear as both high variance and many `BAD_high` segments.

### B.2 PSD-based bad-channel and line-noise detection

Compute the PSD once per channel and derive several QC scalars from it:
```python
psd = raw.compute_psd(method='welch', fmin=FMIN, fmax=FMAX,
                      n_fft=int(2*raw.info['sfreq']),
                      n_per_seg=int(2*raw.info['sfreq']),
                      n_overlap=int(raw.info['sfreq']), window='hann', picks='eeg')
psds, freqs = psd.get_data(return_freqs=True)   # (n_ch, n_freq), V**2/Hz
```
- **Line-noise ratio** (per channel): power in a narrow band around `LINE_FREQ` (±1–2 Hz) divided by the power in flanking bands. A high ratio after preprocessing means the notch/ZapLine under-performed. Also check the first harmonic (`2*LINE_FREQ`) if within FMAX.
- **High-frequency / EMG index** (per channel): ratio of high-band power (e.g. 20–40 Hz, or up toward Nyquist) to low-band power. Channels with an anomalously high ratio carry muscle/EMG or are noisy (this is the spectral analog of the FASTER high-frequency-noise criterion).
- **Spectral bad-channel score**: a channel whose whole PSD shape is an outlier vs the across-channel median (e.g. correlation of its log-PSD with the channel-median log-PSD is low, or its broadband power is `|z|>3`) is flagged. Do NOT interpret content above the low-pass cutoff — bins exist to Nyquist but are filter roll-off (see `eeg-spectral`).
- **Slope/`1/f` sanity**: a healthy scalp channel has a decreasing PSD; a flat or rising log-log PSD across 1–40 Hz signals a disconnected/reference-shorted channel.

### B.3 Neighbor-prediction bad-channel detectors (montage required)

When 3D positions exist, add geometry-aware detectors — they catch channels that variance/PSD miss:
```python
from mne.preprocessing import find_bad_channels_lof
bads_lof, scores = find_bad_channels_lof(
    raw, n_neighbors=20, picks='eeg',
    threshold=1.5, return_scores=True)   # Local Outlier Factor on spatial neighbors
```
`find_bad_channels_lof` (Kumaravel et al. 2022, the detector used in the HAPPE/automagic family) scores each channel by how anomalous it is relative to its spatial neighbors — robust to global noise that fools simple variance thresholds. Corroborate with `pyprep.NoisyChannels(raw).find_all_bads()` (RANSAC + correlation + deviation + HF-noise + SNR + flat criteria, Bigdely-Shamlo et al. 2015) — `pyprep` is a core dep, so it is normally present; a channel flagged by **both** LOF and RANSAC is a high-confidence bad channel. If a stripped env lacks `pyprep`, fall back to LOF + the FASTER-style variance/spectral metrics and log the substitution.

> **`find_bad_channels_maxwell` is MEG-only** (it relies on Maxwell filtering / SSS and an Elekta/MEGIN-style fine-calibration + crosstalk model). Do NOT call it on scalp EEG; use `find_bad_channels_lof` (+ pyprep RANSAC) for EEG. Only reach for `find_bad_channels_maxwell` if the recording is MEG (then it is the canonical bad-channel detector).

### B.4 Per-channel SNR

SNR is paradigm-dependent — pick the definition that matches the data and **state which one**:
- **Resting / continuous**: spectral SNR — power at the feature of interest (e.g. the alpha peak) over the aperiodic/broadband floor, or simply `signal_band / noise_band`. For a generic channel-health number use `median_psd / psd_at_line_freq` or the broadband-vs-EMG ratio from B.2.
- **Task / ERP**: the standardized measurement error (SME, Luck et al. 2021) or the across-trial SNR of the evoked response: `SNR = var(evoked) / mean(var(single_trials − evoked))`, or the simpler `peak_amplitude / baseline_RMS`. ERP SNR scales as `sqrt(n_trials)` (Luck 2014), so report it alongside trial count, never alone.
- Report SNR **per channel** and as an ROI median; flag channels in the bottom decile.

### B.5 Per-channel Hurst exponent (OPTIONAL — degrade explicitly)

The Hurst exponent `H` of a clean scalp EEG channel sits near ~0.7 (long-range temporal correlation); values driven toward 0.5 (white-noise-like) or toward 1 (drift/saturation) flag a bad channel — this is the FASTER channel-level Hurst criterion (Nolan et al. 2010).
```python
# OPTIONAL: needs antropy or nolds. Guard the import; fall back if absent.
try:
    from antropy import detrended_fluctuation     # DFA exponent α  (α ≈ H for fGn)
    have_hurst = True
except ImportError:
    try:
        from nolds import hurst_rs as _hurst       # rescaled-range Hurst
        have_hurst = True
    except ImportError:
        have_hurst = False                          # log substitution; Hurst='not_computed'
```
Compute on ≥`HURST_EPOCH_S`-second windows (scaling estimates need longer epochs than band power — see `eeg-spectral`/`eeg-complexity`), z-score across channels, flag `|z|>3`. If no backend, record `"hurst": "not_computed (no antropy/nolds)"` in the per-channel table and proceed — **never** silently skip without logging (House rule: no silent fallbacks). The DFA exponent also ties back to the 1/f slope (`H ≈ (β−1)/2`); see `eeg-complexity`.

Write per subject per stage: `qc-stage/<sub>/<stage>_channel_metrics.csv` with one row per channel
(`channel, variance_z, line_ratio, emg_ratio, spectral_z, lof_score, snr, hurst, hurst_z, flagged, flag_reasons`).

## Phase C — Before/after SNR per pipeline stage

The headline QC value of this skill: show that each stage **improved** the data, not degraded it. For each subject, compute a small set of comparable scalars at every available stage on the SAME channels/band and tabulate the deltas:

| Metric | raw → preprocess | preprocess → ica | epoch (post) |
|---|---|---|---|
| Median broadband SNR | should rise | should rise (blinks gone) | n/a |
| Line-noise ratio | should drop sharply (notch/ZapLine) | ~flat | ~flat |
| EMG/HF ratio | drops if LP applied | drops (muscle ICs removed) | drops (bad epochs gone) |
| % bad-time (flat/high annot) | baseline | should drop | n/a |
| N bad channels | detected→interpolated | ~flat | ~flat |

- Compute the same B.1–B.4 scalars on each stage's data and store the **deltas**. A stage that makes a metric WORSE (e.g. SNR drops after re-reference, line ratio rises after a botched notch) is the single most useful thing this report surfaces — flag it loudly.
- Where ICA ran, read `ica-stage/<sub>/ica_labels.json` for n components removed by class (eye/muscle/heart/line/channel-noise) and report variance removed — cross-check that EMG ratio actually fell after the muscle ICs were taken out.
- This is the QC analog of the PREP "before/after" reporting (Bigdely-Shamlo et al. 2015) and the HAPPE quality-metrics table (Gabard-Durnam et al. 2018).

Write `qc-stage/<sub>/stage_snr_delta.json`.

## Phase D — Per-subject summary metrics

Aggregate the channel table into subject-level numbers (these drive the gates in Phase F):

- `n_bad_channels` and `pct_bad_channels` (flagged by ≥2 detectors), with the channel list in 10-20 names.
- `pct_bad_time` — fraction of recording in `BAD_flat`/`BAD_high` annotations (from B.1).
- `median_line_ratio`, `median_emg_ratio`, `median_snr`, `median_hurst` (or `not_computed`).
- **Head-motion / drift index** — RMS of the very-low-frequency band (e.g. <1 Hz, computed before the high-pass on a raw copy, or from the slow-drift residual) and the count of large all-channel excursions. Big synchronous low-frequency swings across all channels = head movement, which is **uncorrectable** and must be rejected as bad segments, not ICA'd (Luck 2014; see `eeg-preprocess` artifact table). Report the count and total bad-time.
- **EMG/muscle index** — subject-median high-frequency ratio and the count/time of muscle bursts. Peri-auricular muscle is ICA-resistant — high residual EMG after ICA is a real warn, not a pipeline bug.

### Channel & epoch rejection-rate reporting

This is the rejection-rate dashboard the roadmap calls for. Pull the numbers that upstream stages already logged — **do not recompute or re-reject** here:
- **Channels**: from `preprocess-stage/<sub>/preprocess_summary.json` (`n_interpolated`, which channels). Report per-subject interpolation rate and the group channel-interpolation heat map (channel × subject) so consistently-bad electrodes (a faulty cap site) stand out.
- **Epochs**: from `epoch-stage/<sub>/<sub>-reject-log.json` and `TRIAL_COUNT_TABLE.csv` — `pct_rejected` per condition, `n_after_reject`, and the most-interpolated channels. Read `Epochs.drop_log` directly when you need the per-epoch reason breakdown:
  ```python
  epochs = mne.read_epochs(epo_path)
  # drop_log: tuple, one entry per ORIGINAL epoch.
  #   ()            -> kept
  #   ('IGNORED',)  -> not selected for this Epochs object
  #   ('TOO_LONG',) / ('USER',) / channel names -> dropped, reason = the tuple contents
  reasons = [r for entry in epochs.drop_log for r in entry if r not in ('IGNORED',)]
  from collections import Counter
  drop_reason_counts = Counter(reasons)       # e.g. {'Fp1': 12, 'TOO_SHORT': 3}
  drop_rate = epochs.drop_log_stats()         # overall % dropped (MNE helper)
  ```
- Optionally preview a data-driven epoch threshold (does NOT mutate the saved epochs) — `autoreject` is a core dep:
  ```python
  from autoreject import get_rejection_threshold      # core dep (environment.yml)
  reject = get_rejection_threshold(epochs, random_state=SEED)  # {'eeg': ...}
  ```
  If the previewed threshold would reject far more than the stage actually did, the upstream epoch reject was too lenient — flag it. If a stripped env lacks `autoreject`, skip the preview and log the substitution.

Write `qc-stage/<sub>/qc_summary.json` (schema in Phase G).

## Phase E — Group QC

- `qc-stage/GROUP_QC.csv` — one row per subject with every subject-level metric + the verdict.
- **Channel-interpolation heat map** (channel × subject) and **rejection-rate bar chart** (per subject, per condition) → `figure-stage/` (or `qc-stage/figures/`).
- **Outlier subjects**: flag any subject whose summary metric is `>3` MAD from the group median (a recording-day or cap problem). Group-level outliers are often more diagnostic than absolute thresholds.

## Phase F — Pass / warn / fail gates

Apply the thresholds from `QC_GATES.json` (the `normal` preset below; `strict`/`lenient` scale these). Every threshold is explicit and reported — **no hidden gating**.

| Metric | pass | warn | fail (normal preset) |
|---|---|---|---|
| % bad channels | ≤10% | 10–20% | >20% |
| % bad time (flat/high) | ≤5% | 5–20% | >20% |
| Epoch rejection rate (per condition) | ≤15% | 15–30% | >30% |
| Trials retained per analyzed condition | ≥ recommended | ≥ minimum | < minimum (see `eeg-epoch` table) |
| Line-noise ratio (post-preprocess) | ≤ 2× flanking | 2–5× | >5× (notch failed) |
| Residual EMG/HF ratio (post-ICA) | low | moderate | high (muscle not removed) |
| Median SNR | ≥ preset floor | borderline | below floor |
| Stage SNR delta | non-negative | small negative | a stage made SNR worse |

- The subject verdict is the **worst** gate it trips: any `fail` → `fail`; else any `warn` → `warn`; else `pass`.
- A `fail` is a routing signal, not a fix: name the offending metric and the stage to revisit (e.g. "fail: line ratio 8× at preprocess → re-run notch/ZapLine in `eeg-preprocess`"). **Never** auto-edit upstream data from this skill.
- `strict` tightens each band by ~half; `lenient` widens it. The exact numbers live in `QC_GATES.json` so the methods text can cite them.

## Phase G — Write outputs

### `qc-stage/<sub>/qc_summary.json`
```json
{
  "subject": "sub-07",
  "stages_present": ["raw", "preprocess", "ica", "epoch"],
  "n_channels": 64,
  "n_bad_channels": 4,
  "pct_bad_channels": 6.3,
  "bad_channels_1020": ["T7", "TP9", "Fp1", "Oz"],
  "bad_channel_detectors": {"lof": ["T7","Oz"], "ransac": ["T7","TP9","Fp1"], "agreed": ["T7"]},
  "pct_bad_time": 3.1,
  "median_line_ratio_post": 1.4,
  "median_emg_ratio_post": 0.8,
  "median_snr": 6.2,
  "snr_definition": "across-trial evoked SNR (ERP)",
  "median_hurst": 0.71,
  "head_motion_index": {"low_freq_rms_uv": 14.2, "n_large_excursions": 2, "bad_time_s": 1.8},
  "epoch_rejection": {"standard": {"pct": 8.0, "n_after": 368},
                      "deviant":  {"pct": 12.5, "n_after": 70}},
  "drop_reason_counts": {"Fp1": 12, "USER": 3, "TOO_SHORT": 1},
  "stage_snr_delta": {"raw->preprocess": +2.1, "preprocess->ica": +1.3},
  "gates": {"bad_channels": "pass", "bad_time": "pass", "epoch_reject": "warn",
            "line_ratio": "pass", "emg": "pass", "snr": "pass", "snr_delta": "pass"},
  "verdict": "warn",
  "verdict_reason": "deviant epoch rejection 12.5% (warn band 15-30 not tripped) — borderline trial count flagged",
  "optional_backends": {"pyprep": true, "autoreject": false, "hurst": "antropy"}
}
```

### `qc-stage/QC_REPORT.html` (mne.Report)
Build a self-contained HTML dashboard mirroring `eeg-report` conventions:
```python
import mne
report = mne.Report(title="EEG QC Dashboard")
report.add_raw(raw_preproc, title="Preprocessed (sub-07)", psd=True, tags=("qc", "preprocess"))
# Per-channel metric tables + the channel-interpolation heat map + rejection bar chart as images:
report.add_image(heatmap_png, title="Channel interpolation heat map", tags=("qc", "group"))
report.add_html(title="QC gate summary", html=gate_table_html, tags=("qc", "gates"))
report.save(str(out / "QC_REPORT.html"), overwrite=True, open_browser=False)
```
`add_raw(..., psd=True)` embeds the interactive PSD so a reviewer can eyeball line noise and bad channels directly. This is a **diagnostic** report (does the data pass?), distinct from `eeg-report`'s **results** report (what did the analysis find?).

### `qc-stage/GROUP_QC.csv`, `qc-stage/QC_GATES.json`, `qc-stage/QC_PLAN.json`
Group table, the exact gate thresholds used, and the run plan.

### Append to `FINDINGS.md`
```markdown
## Data quality (eeg-qc)
- N subjects QC'd: 24 — pass 19, warn 4, fail 1 (sub-12: 26% bad channels)
- Mean bad-channel rate: 7.1% (range 0–26%)
- Mean epoch rejection: 11.4% (SD 6.0)
- Line-noise removed: median ratio 9.2× (raw) → 1.4× (post-preprocess)
- Gate preset: normal; thresholds in qc-stage/QC_GATES.json
```

## Phase H — Sanity checks

All must pass before declaring success:

- [ ] Every QC'd subject has `qc-stage/<sub>/qc_summary.json` and a `verdict`.
- [ ] `qc-stage/QC_REPORT.html` exists and is >10 KB.
- [ ] `qc-stage/GROUP_QC.csv` lists every subject (including `fail`s).
- [ ] `qc-stage/QC_GATES.json` records the exact numeric thresholds used (no metric gated by an unrecorded number).
- [ ] Every `warn`/`fail` has a `verdict_reason` naming the metric and the stage to revisit.
- [ ] Optional-backend availability is logged in every `qc_summary.json` (`pyprep`, `autoreject`, `hurst`), and any degraded metric reads `not_computed (<reason>)`, never silently missing.
- [ ] `FINDINGS.md` has a new dated QC entry.
- [ ] No upstream stage file was modified by this skill (QC is read-only on stage data).

## Critical Rules

- **Never** modify, re-reject, or re-reference upstream stage data — QC measures, it does not clean. A `fail` routes the user back to `eeg-preprocess`/`eeg-ica`/`eeg-epoch`; it never edits their outputs.
- **Never** call `find_bad_channels_maxwell` on scalp EEG — it is MEG-only (Maxwell/SSS + fine-cal/crosstalk). Use `find_bad_channels_lof` (+ pyprep RANSAC) for EEG.
- **Never** gate on a threshold that is not written to `QC_GATES.json` — hidden thresholds violate COBIDAS reproducibility.
- **Never** silently skip a metric when its optional backend is missing — record `not_computed (<reason>)` and log the substitution (House rule: no silent fallbacks). The dashboard must still run without `pyprep`/`autoreject`/`antropy`.
- **Never** try to ICA out or "correct" head-movement / saturation segments — they are uncorrectable; report them as bad-time and reject the segment (Luck 2014).
- **Never** report a single SNR number without stating its definition (spectral vs across-trial evoked) and the trial count it depends on — ERP SNR scales as `sqrt(N)`.
- **Never** interpret PSD content above the low-pass cutoff as signal when scoring channels — bins exist to Nyquist but are filter roll-off (`eeg-spectral`).
- **Never** flag a channel bad on a single detector when geometry-aware corroboration is available — require ≥2 detectors (LOF + RANSAC, or variance-z + spectral-z) before marking, to avoid over-interpolation.
- **Never** present a green QC verdict as evidence the *analysis* is valid — QC certifies data quality (inputs), not the statistical claims (that is `eeg-stats` + `eeg-audit`).
- **Never** baseline-correct or assume task structure when QC'ing resting-state data — use the continuous/fixed-length path and spectral SNR.

## Domain Knowledge (distilled from EEG data-quality literature)

These guidelines are encoded from EEG quality-control methodology. The LLM must follow them when computing metrics and setting gates.

### The PREP pipeline and before/after reporting (Bigdely-Shamlo et al. 2015, Frontiers in Neuroinformatics)

- PREP standardizes early-stage quality control: line-noise removal → robust average reference → RANSAC bad-channel detection → interpolation, with quality numbers logged at each step.
- **RANSAC** predicts each channel from a random subset of spatial neighbors and flags channels poorly predicted across many random subsets — robust to global noise that fools variance thresholds. In Python: `pyprep.NoisyChannels(raw).find_all_bads()` runs RANSAC plus correlation, deviation, high-frequency-noise, SNR, and flat criteria.
- PREP's reporting philosophy — record the data state *before and after* each operation so degradation is visible — is exactly the Phase C "stage SNR delta" table here.
- Cite: Bigdely-Shamlo, N., Mullen, T., Kothe, C., Su, K.-M., & Robbins, K. A. (2015). The PREP pipeline: standardized preprocessing for large-scale EEG analysis. Frontiers in Neuroinformatics, 9, 16.

### FASTER channel/epoch/component metrics (Nolan et al. 2010, Journal of Neuroscience Methods)

- FASTER (Fully Automated Statistical Thresholding for EEG artifact Rejection) thresholds z-scored statistical properties at three levels.
- **Channel level**: variance, mean correlation with other channels, and **Hurst exponent**; any metric with `|z| > 3` marks the channel bad. The Hurst criterion catches channels whose temporal-correlation structure departs from the clean-EEG norm (~0.7) — a detector that pure amplitude metrics miss.
- **Epoch level**: amplitude range, variance, channel deviation. **Component level** (after ICA): spatial kurtosis, slope, Hurst, median gradient, correlation with EOG.
- AEA's per-channel table (variance-z, correlation/spectral-z, Hurst-z) is a direct port of the FASTER channel metrics; combine with LOF/RANSAC rather than relying on any single one.
- Cite: Nolan, H., Whelan, R., & Reilly, R. B. (2010). FASTER: Fully Automated Statistical Thresholding for EEG artifact Rejection. Journal of Neuroscience Methods, 192(1), 152–162.

### Local Outlier Factor for bad-channel detection (Kumaravel et al. 2022, Sensors)

- LOF scores each channel by how isolated it is relative to its spatial neighbors in feature space, catching channels that are anomalous *given the montage geometry* even when their raw variance looks ordinary.
- MNE exposes it as `mne.preprocessing.find_bad_channels_lof(raw, n_neighbors=20, threshold=1.5)`; the default threshold ~1.5 balances sensitivity and false positives. It is the bad-channel detector adopted in the automated-EEG (HAPPE/automagic) family.
- LOF is geometry-aware but reference- and montage-dependent — corroborate with RANSAC and treat a single-detector flag as a candidate, not a verdict.
- Cite: Kumaravel, V. P., Buiatti, M., Parise, E., & Farella, E. (2022). Adaptable and robust EEG bad channel detection using Local Outlier Factor (LOF). Sensors, 22(19), 7314.

### Automated quality metrics for large/developmental datasets — HAPPE (Gabard-Durnam et al. 2018, Frontiers in Neuroscience)

- HAPPE (Harvard Automated Processing Pipeline for EEG) ships a per-file **quality-metrics report**: number/percent of good channels, percent of variance retained after artifact removal, percent of segments/trials kept, and cross-correlation of the data before vs after each step. These quality numbers — not just the cleaned data — are the deliverable.
- The design intent (high-throughput, developmental/clinical cohorts where manual inspection does not scale) is the same use case AEA's dashboard targets: a machine-readable pass/warn/fail per recording so bad data is caught before analysis.
- AEA's Phase D summary table (good-channel %, variance/SNR retained, trials kept, before/after correlation) mirrors the HAPPE quality report.
- Cite: Gabard-Durnam, L. J., Mendez Leal, A. S., Wilkinson, C. L., & Levin, A. R. (2018). The Harvard Automated Processing Pipeline for EEG (HAPPE): standardized processing software for developmental and high-artifact data. Frontiers in Neuroscience, 12, 97.

### EEG data quality at scale and NEMAR (Delorme 2023, Scientific Reports; Delorme et al. 2022, Database)

- Delorme (2023) introduces a quantitative EEG data-quality metric — the percentage of channels showing a significant condition difference in an early post-stimulus window — to objectively *compare* automated preprocessing methods, and finds that (apart from high-pass filtering and bad-channel interpolation) several automated corrections did not improve, and sometimes reduced, that metric. The lesson AEA encodes: a QC report needs an explicit, quantitative quality criterion, and a "cleaning" step is only justified if it measurably improves it — exactly the Phase C before/after delta.
- NEMAR / OpenNeuro (Delorme et al. 2022) provide automated quality dashboards over thousands of openly shared EEG/MEG datasets, surfacing per-dataset quality indicators (channel counts, sampling, artifact levels, processing provenance) so reusers can triage data before downloading.
- Implication for AEA: emit a machine-readable QC JSON + an HTML dashboard with explicit, reported thresholds, so a downstream consumer (or `eeg-audit`) can decide usability without re-running the pipeline.
- Cite: Delorme, A. (2023). EEG is better left alone. Scientific Reports, 13, 2372. (and) Delorme, A., et al. (2022). NEMAR: an open access data, tools and compute resource operating on neuroelectromagnetic data. Database (Oxford), 2022, baac096. (See also Pernet et al. 2019, EEG-BIDS, Scientific Data 6, 103, for the metadata that makes QC auditable.)

### AutoReject and data-driven rejection previews (Jas et al. 2017, NeuroImage)

- AutoReject learns per-channel peak-to-peak thresholds by cross-validation rather than using an arbitrary fixed number; `get_rejection_threshold(epochs)` returns a data-driven global threshold dict.
- For QC, run it in **preview** mode only: compare the data-driven threshold to what the epoch stage actually applied. A large gap means the upstream reject was mis-tuned. QC never re-rejects — it flags the discrepancy for `eeg-epoch` to revisit.
- Cite: Jas, M., Engemann, D. A., Bekhti, Y., Raimondo, F., & Gramfort, A. (2017). Autoreject: Automated artifact rejection for MEG and EEG data. NeuroImage, 159, 417–429.

### Standardized measurement error as a recording-quality metric (Luck et al. 2021, Psychophysiology)

- The standardized measurement error (SME) quantifies the data quality of a single-subject ERP measure (e.g. mean amplitude over a window) as the standard error of that measure across trials — a principled, score-specific SNR that an arbitrary "peak/RMS" ratio lacks.
- SME makes data quality comparable across subjects and labs and exposes when a low trial count, not the effect, drives a noisy estimate. Report SME (or an across-trial evoked SNR) alongside trial count, since ERP SNR improves as `sqrt(N)` (Luck 2014).
- Cite: Luck, S. J., Stewart, A. X., Simmons, A. M., & Rhemtulla, M. (2021). Standardized measurement error: A universal metric of data quality for averaged event-related potentials. Psychophysiology, 58(6), e13793.

### Head motion, EMG, and uncorrectable artifacts (Luck 2014, An Introduction to the ERP Technique, 2nd ed.)

- Large synchronous low-frequency swings across all channels are head/cable movement — **uncorrectable** by ICA or interpolation; they must be annotated and the segment rejected. A QC head-motion index (low-frequency RMS + count of large excursions) quantifies how much data this costs.
- Peri-auricular / temporalis EMG is high-frequency "fuzz" on ear-adjacent channels and is **ICA-resistant**; a high residual EMG/HF ratio after ICA is a genuine quality warning, not a pipeline bug. Quantify it as a high-band/low-band power ratio.
- Cite: Luck, S. J. (2014). An Introduction to the Event-Related Potential Technique, 2nd ed., ch. 6 (artifact identification). MIT Press.

### COBIDAS-MEEG quality reporting (Pernet et al. 2020, Nature Neuroscience)

The methods/QC section must report, with exact numbers and thresholds:
- Number and percent of bad/interpolated channels per subject (mean, range), and the detection method and criteria.
- Percent of data/epochs rejected per subject and per condition, and the rejection method.
- Line-noise handling and any residual line power.
- The exact pass/warn/fail thresholds and how subjects were included/excluded — no hidden gating.
- Software and version for every metric.
- Cite: Pernet, C. R., et al. (2020). Issues and recommendations from the OHBM COBIDAS MEEG committee for reproducible EEG and MEG research. Nature Neuroscience, 23(12), 1473–1483.

## Failure Modes

| Symptom | Action |
|---|---|
| No stage directories present | Stop. At least one of `raw/`, `preprocess-stage/`, `ica-stage/`, `epoch-stage/` must exist. |
| `DATASET_BRIEF.md` line freq / montage is a placeholder | Stop. Cannot compute line-noise ratio or geometry-aware detectors without them. |
| Montage / 3D positions missing | Skip `find_bad_channels_lof` and RANSAC (geometry-aware); fall back to variance-z + spectral-z + line/EMG ratios. Log the substitution. |
| `find_bad_channels_maxwell` suggested for EEG | Wrong detector — it is MEG-only. Use `find_bad_channels_lof` (+ pyprep RANSAC). |
| `pyprep` not installed (stripped env; it is a core dep) | Use LOF + FASTER-style metrics only; log "RANSAC corroboration unavailable". |
| `autoreject` not installed (stripped env; it is a core dep) | Skip the data-driven epoch-reject preview; report the stage's logged rejection only; log substitution. |
| `antropy`/`nolds` not installed (optional Hurst dep) | Record `hurst: not_computed (no antropy/nolds)`; rely on variance/correlation/LOF. Do not crash. |
| Residual 50/60 Hz peak after preprocess (high line ratio) | `fail` line gate → route to `eeg-preprocess`: re-run notch/ZapLine, include harmonics. Do not notch here. |
| >20% bad channels for a subject | `fail`. Likely wrong reference/montage or a bad cap — flag for manual review; do not auto-interpolate from QC. |
| A stage made SNR worse (negative delta) | Flag loudly with the stage name (e.g. re-reference before interpolation, or an over-aggressive filter). Route to that stage. |
| Epoch rejection >30% for a condition | `fail` epoch gate; investigate upstream ICA sufficiency and remaining bad channels (`eeg-ica`, `eeg-epoch`). |
| QC verdict green but analysis still looks wrong | QC certifies inputs, not claims. Direct the user to `eeg-stats`/`eeg-audit` for the analysis-validity question. |

## Cross-references

- **Inputs**: `DATASET_BRIEF.md`, `ENVIRONMENT.json`, `raw/`, `preprocess-stage/*_preprocessed_raw.fif` + `preprocess_summary.json`, `ica-stage/*-clean-raw.fif` + `ica_labels.json`, `epoch-stage/*-epo.fif` + `*-reject-log.json` + `TRIAL_COUNT_TABLE.csv`, `channel_mapping.json`, `ANALYSIS_PLAN.md` (seed).
- **Outputs**: `qc-stage/<sub>/qc_summary.json`, `qc-stage/<sub>/<stage>_channel_metrics.csv`, `qc-stage/<sub>/stage_snr_delta.json`, `qc-stage/QC_REPORT.html`, `qc-stage/GROUP_QC.csv`, `qc-stage/QC_GATES.json`, `qc-stage/QC_PLAN.json`, `FINDINGS.md` entry, heat-map/bar-chart figures.
- **Runs before analysis**: `eeg-qc` consumes the cleaning stages and gates the data *before* `eeg-erp`/`eeg-tfr`/`eeg-spectral`/`eeg-stats` invest compute on it.
- **Upstream stages it measures**: `eeg-preprocess` (channel interpolation, line noise, reference), `eeg-ica` (variance/components removed, residual EMG), `eeg-epoch` (`drop_log`, rejection rates, AutoReject). A `fail` routes back to the offending one.
- **Related**: `eeg-spectral` (shares the PSD/line-noise/EMG-ratio and SNR conventions; QC must not interpret above the LP cutoff), `eeg-complexity` (Hurst/DFA and the `H ≈ (β−1)/2` link to the 1/f slope), `eeg-report` (the *results* HTML report — `eeg-qc` is the complementary *quality* report, same `mne.Report` builder), `eeg-audit` (consumes `QC_GATES.json` and `GROUP_QC.csv` to verify quality gates and exclusions were reported per COBIDAS).
