# AEA vs the world — an honest novelty audit

This document is the brutal version. We separate **what AEA genuinely brings** from **what it inherits**. If a future preprint claims novelty, it has to defend it from this table.

## 0. What AEA is (positioning)

**AEA is an EEG analysis tool.** Specifically: a library of executable, citable analysis recipes that an
LLM agent runs end-to-end, producing a paper-ready figure, a COBIDAS-compliant methods paragraph, and an
adversarial reviewer memo.

Its differentiator is not the LLM, and not the recipe format. It is this:

> **Among the systems reviewed here, AEA is the only EEG analysis tool whose reference-implementation pipelines are certified digit-by-digit against a
> gold-standard implementation, with a CI gate that fails the build if the agreement regresses.**

Everything else in this document exists to defend or qualify that sentence.

### The evidence behind the claim

| What the tool claims | Evidence |
|---|---|
| Recipe pipelines compute the right numbers | 5 ERP CORE components vs MNE-BIDS-Pipeline, CCC ≥ 0.9997, every subject within ±0.1 µV, scalar + full waveform ([BENCHMARK.md](BENCHMARK.md)) |
| …and it is not an MNE artefact | Independent SciPy DSP (§4g); **all 5 components re-run in two independent toolboxes — EEGLAB and FieldTrip under Octave — 10/10 reproduce the group conclusion, grand means within 0.3–3.8%** ([CROSS_TOOLBOX_EVAL.md](../tools/benchmark/CROSS_TOOLBOX_EVAL.md)) |
| …and where toolboxes *do* disagree, we know why | Controlled experiments trace divergence to unstated spec parameters, not toolbox code: harmonizing the rejection criterion improves per-subject agreement 2.2×, and pinning the filter *specification* (cutoff convention together with transition width) takes FieldTrip from max\|Δ\| 0.72 µV to **0.05 µV, r = ρ = 1.0000** — the cutoff-convention-only step at a fixed transition width is 0.80 → 0.05 µV (a staged comparison, not one parameter alone) ([CROSS_TOOLBOX_EVAL.md §2](../tools/benchmark/CROSS_TOOLBOX_EVAL.md)) |
| …and generated code reached the same values in a historical pilot (retained scoring summaries only; programs and, except MMN B1, per-subject vectors not retained — not a certification claim) | 7 pinned-spec generation records PASS (≤0.5 nV) across 3 components and 2 model families ([RECIPE_GENERATION_EVAL.md](../tools/benchmark/RECIPE_GENERATION_EVAL.md)) |
| …without requiring a frontier model — **not shown** | 0 of 4 open-weight models reproduced them as generated; one 14B model on CPU did so only after three author-classified output-handling repairs ([OPEN_MODEL_EVAL.md](../tools/benchmark/OPEN_MODEL_EVAL.md)) |
| The reviewer feature actually catches problems | 8/8 seeded EEG defects, clean control passed, on **both** backends ([audit_eval/](../tools/validation/audit_eval/)) |
| The methods text is complete and not fabricated | 100% COBIDAS coverage, 0/12 fabrications on withheld items ([methods_text_eval/](../tools/validation/methods_text_eval/)) |
| Regressions get caught | `tools/tests/test_benchmark.py` gates CCC, exact N and waveform RMSE on every push |

### What the tool actually guarantees — stated narrowly

The validation work also **narrowed** the claim, and the narrow version is the honest one:

- ⚠️ **Per-subject reproducibility (historical pilot).** The Spearman sequence formerly quoted here (0.894 → 0.992 → 1.000) is not recomputable from committed data and is withdrawn; what remains are retained scoring summaries (24 MMN generations, 24/24 negative grand-mean direction) — see `tools/benchmark/SPEC_PRECISION_EVAL.md` reconstructability note.


- ✅ **Removal of convention ambiguity.** Left unspecified, an LLM applies the field's conventional
  choice for that paradigm — which may not be the one your spec intends (mastoid vs average reference:
  2–3× amplitude difference on MMN/P3, no difference on N170)
  ([CROSS_PARADIGM_BASELINE.md](../tools/benchmark/CROSS_PARADIGM_BASELINE.md)).
- ❌ **NOT "prevents wrong conclusions."** All 24 enumerated generations produced a negative grand mean (the per-generation significance verdicts recorded at run time are not recomputable); the run-time record that all reached the same significant group-level conclusion is kept as history, is not recomputable from committed data, and is not used by the paper.
  conclusion as the certified pipeline, including the no-recipe baseline. For a well-powered group
  contrast, this tooling is not what stands between you and a wrong answer.
- ❌ **NOT "scientifically optimal."** Certification means *faithful to this specification*. A recipe can
  be perfectly certified and still encode a defensible-but-unconventional choice.

### Where the research findings fit

Building that certification produced methodological findings that generalise beyond AEA (specification
precision vs reproducibility; convention-vs-spec divergence; silent label corruption and silent empty
results that group-level checks cannot detect). **They are evidence for the tool, and guidance for how
to write recipes — not a replacement for it.** The tool remains the deliverable; the findings are why
you should trust it and how to extend it.

### The gap that still decides everything

**External adoption is zero.** No lab outside this project has run AEA on its own data. Every claim above
is about the tool's *correctness*, none about its *usefulness in practice*. That is the binding
constraint, and no amount of further validation substitutes for it.

## 1. Capability matrix

Legend: ✅ = first-class / ⚙️ = configurable / 〰️ = partial-via-script / ❌ = not provided.

| Capability | AEA | ARIS | MNE-BIDS-Pipeline | HAPPE | PREP | Automagic | DISCOVER-EEG | BeMoBIL | EEGLAB STUDY | Brainstorm protocols |
|---|---|---|---|---|---|---|---|---|---|---|
| **Domain** | EEG analysis | Generic ML research | EEG analysis | EEG (developmental/clinical) | EEG preprocessing | EEG preprocessing+QC | RS-EEG | Mobile EEG | EEG (group GUI) | EEG (GUI-scripted) |
| Markdown-only skill architecture | ✅ | ✅ (parent) | ❌ (Python config) | ❌ (MATLAB) | ❌ (MATLAB) | ❌ (MATLAB+GUI) | ❌ (MATLAB pipeline) | ❌ (MATLAB) | ❌ (GUI) | 〰️ (GUI script) |
| LLM-agent-orchestrated | ✅ | ✅ (parent) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Cross-platform (mac/linux/windows) | ✅ tier 1+2 | ✅ | ✅ | 〰️ (matlab license) | 〰️ | 〰️ | ✅ | 〰️ | 〰️ | ✅ |
| MNE-Python backend | ✅ | ❌ | ✅ MNE-only | ❌ EEGLAB-only | ❌ EEGLAB-only | ❌ | ❌ (EEGLAB+FieldTrip, MATLAB) | ❌ EEGLAB-only | ❌ | ❌ |
| Preprocess (filter, ref, bad-chan, notch) | ✅ | n/a | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| ICA + auto-label | ✅ | n/a | ✅ | ✅ | ❌ | 〰️ | ✅ | ✅ | ✅ | ✅ |
| Cluster permutation | ✅ | n/a | ✅ | ❌ | ❌ | ❌ | 〰️ | ✅ | ✅ | ✅ |
| Microstate analysis | ✅ | n/a | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | 〰️ plugin | ✅ |
| Source localization | ✅ planned | n/a | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | 〰️ DIPFIT | ✅ |
| **Recipe library (paradigm-specific shareable analyses)** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | 〰️ "process scripts" but tool-locked |
| **Auto COBIDAS-MEEG methods paragraph** | ✅ demonstrated D2 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Reviewer-2 simulator (pre-submission audit)** | ✅ demonstrated D3 | ✅ generic | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Natural-language analysis pivot | ✅ planned D4 | ✅ generic | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Reproducibility receipt (seeds + hashes + versions) | ✅ demonstrated D7 | ✅ generic | 〰️ (BIDS sidecars) | ❌ | ❌ | ❌ | 〰️ | 〰️ | ❌ | 〰️ |
| Plan-vs-result divergence detection (mtime check) | ✅ planned D8 | 〰️ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Citation receipt (BibTeX of method paper) | ✅ planned D6 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Recipe drive-by reproduction (one cmd) | ✅ demonstrated D1 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| GUI dependency | ❌ none | ❌ none | ❌ none | ❌ none | ❌ none | ✅ GUI required | ❌ none | ❌ none | ✅ GUI | ✅ GUI for setup |
| BIDS-aware | ✅ via eeg-bids | n/a | ✅ first-class | 〰️ | ❌ | ❌ | ✅ | 〰️ | ❌ | 〰️ |
| Maintained 2024+ | ✅ | ✅ active | ✅ active | 〰️ slow | 〰️ slow | ❌ | ✅ active | ✅ active | ✅ | ✅ |

## 2. The honest novelty claim

### What AEA genuinely brings (rank by defensibility)

#### N1. Recipe library as the sharable unit of EEG analysis [STRONG]

**Claim:** A recipe is one Markdown file declaring an EEG paradigm's complete analysis. Tool-agnostic, reproducible, citation-bound. Anyone clones the repo, drops their data, runs `/eeg-recipe <slug>`, gets a paper-ready figure + methods text + BibTeX.

**Defensibility:**
- ✅ Not done in EEG. Existing "shared analyses" are tool-locked: Brainstorm process scripts only run in Brainstorm, EEGLAB STUDY files only in EEGLAB, MNE Jupyter notebooks aren't declarative.
- ✅ Declarative. A recipe declares parameters; the LLM generates MNE-Python code from those parameters.
- ✅ Citation-bound. Every recipe carries a `citation.bib` for the method's source paper.
- ⚠️ Risk: low-quality contributions dilute the library. Mitigated by review process (CONTRIBUTING.md).
- ⚠️ Risk: HuggingFace-for-X has been claimed many times. Differentiation is the validation requirement (every recipe ships a public dataset it reproduces against).

**Comparable elsewhere:** HuggingFace model hub (NLP), Papers With Code (benchmarks), MNE-Python tutorials (close but tutorials are demos, not declarative recipes). **Closest in EEG:** Brainstorm "tutorial datasets" — but tool-locked and not citation-bound.

#### N2. Auto COBIDAS-MEEG methods text generation [STRONG]

**Claim:** AEA reads its own pipeline's stage logs and emits a submission-ready methods paragraph that satisfies the COBIDAS-MEEG checklist (Pernet et al. 2020). No copy-paste from past papers.

**Defensibility:**
- ✅ Not done. We surveyed every pipeline; none generate a methods paragraph.
- ✅ Concrete checklist standard exists (COBIDAS-MEEG, Pernet et al. 2020) — compliance is measurable, not a vibe.
- ✅ Useful even if AEA isn't your full pipeline — could become a methods-text generator standalone.
- ⚠️ Risk: LLM hallucination — methods text claiming things the pipeline didn't do. Mitigated by template-interpolation (no free generation; values come from logs).

**Comparable elsewhere:** None we know of. The closest analogues are reproducibility tools like RRID (Research Resource Identifiers) — they identify, but don't compose paragraphs.

#### N3. Reviewer-2 simulator with EEG-specific failure modes [MODERATE]

**Claim:** Pre-submission, AEA hands the paper + analysis logs to an external LLM (gpt-6-astra, max effort) prompted to play a hostile EEG reviewer, surfacing concerns specific to the field (cluster threshold choice, adjacency, montage bias, bandpass-vs-time-window leakage, post-hoc exclusion).

**Defensibility:**
- ✅ Domain-specific reviewer simulators don't exist for EEG. ARIS does generic ML review; we go deep on EEG-specific failure modes.
- ⚠️ Defensibility hinges on the reviewer being **good**. Research question: does the Codex reviewer model catch real EEG-reviewer concerns? Empirical claim needed (first answer: the seeded-defect evaluation below, 8/8 on the GPT/Codex backend).
- ⚠️ Could be commoditized: anyone with Codex MCP + a domain prompt can build this. The moat is the prompt library + the integration with the pipeline's audit log, not the LLM call.

**Comparable elsewhere:** ARIS' `kill-argument` and `rebuttal` skills do generic adversarial review for ML papers. Generic LLM "review my paper" prompts. **None EEG-specific.**

#### N4. Markdown-only LLM-orchestrated EEG pipeline [WEAK on its own]

**Claim:** Skills are Markdown files; LLM agent (Claude / Codex / etc.) orchestrates by reading SKILL.md + log artifacts.

**Defensibility:**
- ❌ This is **inherited from ARIS**. Not novel on its own.
- ✅ Novel only as **applied to EEG** with multi-backend support and recipe library on top.
- The synthesis is novel; the architecture is not.

### What AEA inherits (not novel)

| Inherited from | What |
|---|---|
| ARIS | Skill-based markdown architecture, Codex MCP cross-model audit, artifact-driven recovery, claim-driven plan freezing, AGENT_GUIDE.md pattern, sync-skills.sh idiom |
| MNE-Python ecosystem | Pipeline stages, cluster permutation API, mne-icalabel, AutoReject, PREP-style ransac, mne-bids |
| COBIDAS-MEEG (Pernet 2020) | Reporting standard for the methods text generator |
| HuggingFace / Papers With Code | "Library of shareable artifacts" pattern (recipes ≈ models / tasks) |

### What AEA is *not* (calibration)

- ❌ **Not a new EEG analysis algorithm.** No new statistical test, no new ICA variant, no new connectivity metric.
- ❌ **Not a fourth EEG toolbox.** It does not implement numerics. It is an *upper layer* above MNE — the
  relationship is HuggingFace-Transformers-to-PyTorch, not EEGLAB-vs-FieldTrip. Comparing AEA's *coverage* to
  MNE/EEGLAB/FieldTrip is a category error: its ceiling **is** MNE. What it adds sits a level up (recipes +
  reviewer + methods text), where those toolboxes are empty.
- ❌ **Not a more configurable pipeline than MNE-BIDS-Pipeline.** That tool wins on raw configurability.
- ❌ **Not the first LLM-research-agent.** ARIS, AI Scientist (Sakana), ChemCrow, BioPlanner all predate.
- ❌ **Not the first LLM × EEG system.** EEGAgent (AAAI 2026), BrainAgent, and others predate — but those are *agent frameworks* (runtime systems), a different artifact type from AEA's *portable skills corpus*, and **none does numeric validation, cross-model audit, or COBIDAS methods text** (see [RELATED_WORK.md](RELATED_WORK.md)).
- ✅ **It is a *demonstrably faithful* upper layer — for the 5 ERP components tested (MMN, P3, N170, ERN, N400).** When
  harmonized, the AEA recipe reproduces MNE-BIDS-Pipeline's per-subject numbers to ~3 nV (§7). Both call the
  same MNE kernels, so this proves AEA *composes* them correctly, not that the kernels are independently right —
  but composition-correctness is exactly the empirical content the HuggingFace analogy needs.

## 3. So is it publishable?

### Tool paper venues (high success probability)
- **Journal of Open Source Software (JOSS)**: easy, formula = "open-source tool, reproducible, documented, novel-enough". AEA clears bar at v0.3 (post killer-demos).
- **SoftwareX (Elsevier)**: similar bar.
- **Frontiers in Neuroinformatics**: tool paper venue with EEG community readership.
- **eNeuro (SfN)**: methods/tools section accepts open-source releases.

### Methods paper venues (moderate success probability — needs empirical claims)
- **NeuroImage Methods**: would need: (a) reproduce ≥10 published findings end-to-end, (b) demonstrate Reviewer-2 simulator catches concerns at rate ≥ X% on a held-out test set of submitted-then-revised papers, (c) demonstrate methods-text generator agrees with manually-written paragraphs on a panel of expert raters.
- **NeurIPS Datasets & Benchmarks track**: positions AEA recipes as benchmark suite for "EEG analysis reproducibility".
- **Nature Methods Brief Communications**: hard. Would need the recipe library to have grown to ~50+ entries with clear community uptake.

### What kills the publication
- ❌ Pipeline component being claimed as the novelty (it's commodity).
- ❌ "LLM-agent-for-EEG" framed as novelty (ARIS already does it for science generically).
- ❌ Recipe library presented without an empirical reproducibility study.
- ⚠️ Reviewer-2 simulator empirical evaluation — **first result in** (8/8 seeded-defect recall + clean specificity, `tools/validation/audit_eval/`); still needs the GPT-backend re-run, subtler defects, and real-review comparison.

### What makes the publication
- ✅ Recipe library framed as an **artifact-as-publication-unit** for EEG, with X recipes reproducing Y published findings.
- ✅ COBIDAS methods generator framed as a **compliance tool** with empirical agreement-with-experts evaluation.
- ✅ Reviewer simulator framed as a **bias-checking tool** with empirical concern-detection evaluation.

## 4. So is it adoptable?

### Strong adoption pulls
- ✅ Methods-text generator alone is worth installing for 90% of EEG PhD students. ("It writes my methods section.")
- ✅ Recipe library, once seeded with 10+ canonical paradigms, becomes a one-stop reference even for non-LLM users.
- ✅ Cross-platform without GUI — runs over SSH, runs in CI, works on cluster.
- ✅ Markdown-only — fork-able, modifiable, no "black box".

### Adoption headwinds
- ⚠️ EEG community is conservative; "AI / LLM" labeling triggers skepticism.
- ⚠️ Migration cost from a working pipeline. Mitigated by "import your cleaned data, AEA handles methods+stats+figures".
- ⚠️ Quality of recipes determines library trust. One bad recipe in a high-profile paper damages credibility.

### Adoption tactics
- **Lead with the methods text**, not the LLM. EEG users adopt because methods text is painful; LLM is the engine, not the brand.
- **Recipe-as-publication-receipt** — convince paper authors to publish a recipe alongside their paper. Recipe gets a DOI, gets cited every time someone reproduces.
- **MNE / EEGLAB integration**, not competition. Position as "the layer that makes your existing analysis paper-ready".
- **Don't fight on configurability** with MNE-BIDS-Pipeline. Win on the recipe + reviewer + methods axes.

## 5. The bet

If forced to summarize the AEA bet in one sentence:

> **"EEG analyses are recipes; recipes are publishable; recipes ship with their methods text and their reviewer-2 memo built in. Build the library."**

If that sentence is right, AEA becomes the de facto EEG analysis sharing format and the publication pipeline saves PhD students 1-2 weeks per paper. If it's wrong, AEA is a personal automation system for a small lab. Both outcomes are net-positive — the downside is bounded.

## 6. Calibration: how confident are we in each novelty claim?

| Claim | Confidence | Evidence at v0.1 | Evidence needed for confidence ↑ |
|---|---|---|---|
| N1. Recipe library is novel | High | 4 recipes shipped; ern-flankers validated end-to-end in 94.6s | Demonstrate community contributions ≥ 10 external recipes |
| N2. Auto COBIDAS methods is novel | High | Demonstrated in 3 case studies; **first empirical eval — 100% COBIDAS coverage, 100% value accuracy, 0/12 fabrications on withheld items** across MMN/P3/N170 (`tools/validation/methods_text_eval/`) | Expert-rating vs manually-written paragraphs; ICA/source-item coverage; broader fabrication traps |
| N3. EEG-specific reviewer simulator is novel | Moderate→**High** | Empirical detection eval — **8/8 seeded EEG defects caught + clean control passed on BOTH backends** (blind Claude, and the shipped GPT/Codex) (`tools/validation/audit_eval/`) | Subtle/compound defects; comparison against real reviewer comments on real papers |
| N4. Markdown-LLM EEG pipeline is novel | Low as "first LLM×EEG" (EEGAgent AAAI 2026 predates); **defensible as "first portable EEG *skills corpus*"** (no EEG member of that category found — [RELATED_WORK.md](RELATED_WORK.md)) | ~22 SKILL.md; but the moat is N1–N3+N5 (validation+audit+methods), which every scanned competitor omits | Keep [RELATED_WORK.md](RELATED_WORK.md) current |
| N5. Recipe pipelines (reference impl) are numerically faithful | **High (5 components, both epoching modes)** | Cross-tool benchmark vs MNE-BIDS-Pipeline: MMN (N=38, CCC 0.9997), P3b, N170, response-locked ERN, N400 — all CCC ≥ 0.9997, within ±0.1 µV, scalar+waveform **CI-gated** (§7). **Generation step now tested (§6f): 7/7 blind generations from a pinned spec hit the certified values to ≤0.5 nV across MMN/P3/N170 and two generator backends (Claude, GPT/Codex).** *Scope: harmonized minimal pipeline; 3 recipes / 9 generations / 2 backends; the recipe as *written* diverges 0.245 µV until every number-moving step is pinned.* | N2pc + LRP (need new recipes); EEGLAB *toolbox* (SciPy kernel-check done §4g); generation eval on more recipes/backends |

## 7. Validation depth — are the generated pipelines actually correct?

This is the axis on which AEA was genuinely thin, and the one that separates *"an honest, novel
MNE upper layer"* from *"a tool you can stake a result on."* Until now every recipe shipped only a
**self**-regression test (re-run → bitwise-identical) — that proves reproducibility, **not** that
the generated pipeline computes the right number.

**First cross-tool numeric proof (2026-06-24).** AEA's `mmn-oddball` recipe vs the community gold
standard [MNE-BIDS-Pipeline](https://mne.tools/mne-bids-pipeline/) 1.10.1, on ERP CORE MMN
(OpenNeuro `ds003065`), every analysis parameter harmonized so only the *implementation* differs:

| | AEA recipe | MNE-BIDS-Pipeline |
|---|---|---|
| Grand-mean MMN (Fz/FCz/Cz, 100–250 ms) | −0.840 µV | −0.842 µV |

- N=38 (both pipelines' shared subjects), per-subject **max \|Δ\| = 0.09 µV**, **mean \|Δ\| = 0.003 µV**, **Lin's CCC = 0.9997**, **38/38 within ±0.1 µV**.
- 37/38 subjects agree to ≤ 5 nV; the lone 0.09 µV outlier is one extra epoch surviving rejection — a
  real, explained boundary effect the benchmark *surfaces* rather than hides.

**What it proves:** the recipe's spec, run as its **reference implementation**
(`tools/validation/validate_*_group.py` — hand-coded from `RECIPE.md`, *not* the live `/eeg-recipe`
LLM output), is numerically equivalent to an independent implementation of the same spec — no hidden
bug in event handling, filtering, referencing, or averaging. **What it does not:** it does not validate
that the LLM *generates* that code identically (recipe-generation-under-CI is future work), the recipe's
ICA/AutoReject *defaults* (the benchmark runs a harmonized *minimal* pipeline), a *different* numerical
backend (EEGLAB), connectivity/source, or the remaining ERP CORE components (N2pc, LRP). *(Non-ERP
validation has begun: resting spectral band power is now checked vs an independent Welch — [BENCHMARK.md §4h](BENCHMARK.md).)*
Full method + honest caveats: [BENCHMARK.md §5](BENCHMARK.md).

### Route to "够格" (good enough to stand beside the toolboxes, as a layer)

Adding features is not the gap; **validation depth + real adoption** is. Concretely:

| # | Milestone | Status |
|---|-----------|--------|
| 1 | Cross-tool numeric benchmark, ≥1 component | ✅ done (MMN, this section) |
| 1b | Per-sample full-waveform agreement (not just the ROI scalar) | ✅ done (~11 nV RMSE — [BENCHMARK.md §4b](BENCHMARK.md)) |
| 2 | All 7 ERP CORE components benchmarked vs MNE-BIDS-Pipeline | 🔶 5/7 done (MMN, P3, N170, ERN, N400 — both epoching modes); N2pc + LRP remain (both lateralized, need new recipes) |
| 3 | Non-MNE backend — *kernel* error, not just composition | ✅ **done**: independent SciPy DSP ([BENCHMARK §4g](BENCHMARK.md)), plus **all 5 components in EEGLAB *and* FieldTrip under Octave** — 10/10 same conclusion, and with the filter spec fully pinned FieldTrip reaches r = ρ = 1.0000 vs the certified values ([CROSS_TOOLBOX_EVAL.md](../tools/benchmark/CROSS_TOOLBOX_EVAL.md)). *Not yet wired into the skills as selectable backends — see `eeg-preprocess` Phase B.* |
| 4 | Benchmark wired into CI as a correctness gate | ✅ done (`tools/tests/test_benchmark.py` — CCC ≥ 0.99, exact-N, and waveform-RMSE gate on all 5 components every push) |
| 5 | External users reproduce their own data with AEA (currently 0) | ⬜ the real bar |
| 6 | Source-level end-to-end on real MRI; tool/methods paper (JOSS → NeuroImage Methods) | ⬜ |

## 8. Why MNE-Python is sufficient

AEA uses MNE-Python as its sole computation backend. This is a deliberate choice — the Python EEG ecosystem now covers ~90% of what MATLAB tools offer, and is **stronger** in several key areas.

### Coverage scorecard

> 🟢 = Python fully covers &nbsp;&nbsp; 🟡 = Python partial &nbsp;&nbsp; 🔵 = Python stronger &nbsp;&nbsp; 🔴 = MATLAB stronger

---

#### Preprocessing & Artifact Handling

|   | Analysis | MATLAB | Python | |
|---|----------|--------|--------|-|
| 🟢 | Bandpass / notch filter | EEGLAB `pop_eegfiltnew` | MNE `raw.filter()` | Equivalent |
| 🟢 | Bad channel detection | PREP / clean_rawdata | pyprep (RANSAC) | Equivalent |
| 🟢 | Adaptive line noise | CleanLine | meegkit ZapLine | Equivalent |
| 🟢 | Re-reference (avg/mastoid/REST) | EEGLAB / FieldTrip | MNE `set_eeg_reference` | Equivalent |
| 🟢 | ASR (artifact subspace reconstruction) | clean_rawdata | asrpy | Equivalent |
| 🟢 | BIDS conversion | bids-matlab-tools | mne-bids | Equivalent |

#### ICA & Component Classification

|   | Analysis | MATLAB | Python | |
|---|----------|--------|--------|-|
| 🟢 | ICA decomposition | EEGLAB runica / binica | MNE Infomax / FastICA / PICARD | Equivalent |
| 🟢 | Automated ICLabel | ICLabel (EEGLAB plugin) | mne-icalabel | Same algorithm |
| 🔵 | Epoch rejection | manual threshold | **autoreject** (Jas et al. 2017) | Python has automated data-driven method |

#### ERP Analysis

|   | Analysis | MATLAB | Python | |
|---|----------|--------|--------|-|
| 🟢 | Condition averaging | ERPLAB `pop_averager` | MNE `epochs.average()` | Equivalent |
| 🟢 | Grand average | ERPLAB / FieldTrip | MNE `grand_average()` | Equivalent |
| 🟢 | Peak / mean amplitude | ERPLAB `pop_geterpvalues` | MNE `get_peak()` + manual | Equivalent |
| 🟢 | Fractional area latency | ERPLAB | manual (simple formula) | Equivalent |
| 🟢 | Difference waves | ERPLAB `pop_binoperator` | MNE `combine_evoked` | Equivalent |

#### Time-Frequency Analysis

|   | Analysis | MATLAB | Python | |
|---|----------|--------|--------|-|
| 🟢 | Morlet wavelet TFR | EEGLAB `newtimef` | MNE `tfr_morlet` | Equivalent |
| 🟢 | Multitaper TFR | FieldTrip `mtmconvol` | MNE `tfr_multitaper` | Equivalent |
| 🟢 | Stockwell transform | FieldTrip | MNE `tfr_stockwell` | Equivalent |
| 🟢 | Inter-trial coherence | EEGLAB `newtimef` | MNE `return_itc=True` | Equivalent |
| 🟢 | ERDS maps | FieldTrip | MNE | Equivalent |

#### Spectral Analysis

|   | Analysis | MATLAB | Python | |
|---|----------|--------|--------|-|
| 🟢 | PSD (Welch / multitaper) | EEGLAB `spectopo` / FieldTrip | MNE `compute_psd` | Equivalent |
| 🔵 | Aperiodic + periodic decomposition | fooof_mat (wrapper) | **specparam** (native Python) | Python is the original |
| 🟢 | Individual alpha peak (IAPF) | manual | specparam + manual | Equivalent |

#### Statistics

|   | Analysis | MATLAB | Python | |
|---|----------|--------|--------|-|
| 🟢 | Cluster permutation | FieldTrip `ft_timelockstatistics` | MNE `spatio_temporal_cluster_test` | Equivalent |
| 🟡 | TFCE | FieldTrip (gold standard) | MNE (basic support) | FieldTrip more mature |
| 🟡 | Robust stats (LIMO) | LIMO EEG plugin | eelbrain / manual | Partial coverage |
| 🔵 | Mixed-effects models | — (use R) | **statsmodels / pymer4** | Python integrates natively |
| 🔵 | Bayesian stats | — (use R) | **bambi / PyMC** | Python integrates natively |

#### Decoding / MVPA

|   | Analysis | MATLAB | Python | |
|---|----------|--------|--------|-|
| 🟢 | Time-point decoding | MVPA-Light / DDTBOX | MNE `SlidingEstimator` + sklearn | Equivalent |
| 🟢 | Temporal generalization | MVPA-Light | MNE `GeneralizingEstimator` | Equivalent |
| 🟢 | Common Spatial Patterns | FieldTrip | MNE `CSP` | Equivalent |
| 🔵 | Classifier ecosystem | limited | **scikit-learn** (SVM, LDA, RF, XGB...) | Python vastly richer |

#### Connectivity

|   | Analysis | MATLAB | Python | |
|---|----------|--------|--------|-|
| 🟢 | wPLI / PLV / coherence | FieldTrip | mne-connectivity | Equivalent |
| 🟡 | Granger causality | SIFT (EEGLAB) / FieldTrip | mne-connectivity | Partial |
| 🔵 | Phase-amplitude coupling | EEGLAB plugins | **tensorpac** | Dedicated library |
| 🟢 | Graph theory metrics | BCT (MATLAB) | bctpy / networkx | Equivalent |

#### Microstate Analysis

|   | Analysis | MATLAB | Python | |
|---|----------|--------|--------|-|
| 🟢 | Modified k-means / AAHC | Microstate plugin (EEGLAB) | **pycrostates** | Equivalent |
| 🟢 | GEV / duration / coverage | Microstate plugin | pycrostates | Equivalent |
| 🟢 | Transition probabilities | Microstate plugin / manual | pycrostates | Equivalent |

#### Source Localization

|   | Analysis | MATLAB | Python | |
|---|----------|--------|--------|-|
| 🟢 | dSPM / MNE / sLORETA | FieldTrip / Brainstorm | MNE-Python | Equivalent |
| 🟢 | eLORETA | FieldTrip | MNE-Python | Equivalent |
| 🟢 | LCMV / DICS beamformer | FieldTrip | MNE-Python | Equivalent |
| 🔵 | FreeSurfer integration | Brainstorm (external) | MNE-Python (**native**) | Built-in |
| 🟢 | ROI extraction (aparc) | Brainstorm / FieldTrip | MNE `extract_label_time_course` | Equivalent |

#### Sleep & Specialized

|   | Analysis | MATLAB | Python | |
|---|----------|--------|--------|-|
| 🔵 | Sleep staging | manual / SleepSMG | **YASA** (automated) | Dedicated library |
| 🔵 | Spindle / slow oscillation detection | manual | **YASA** | Dedicated library |
| 🔵 | Entropy / complexity measures | manual | **antropy / neurokit2** | Dedicated libraries |
| 🟢 | HEP (heartbeat-evoked) | HEPLAB | neurokit2 | Equivalent |
| 🔴 | BCI / real-time | BCILAB / BCI2000 | brainflow / MNE-Realtime | MATLAB more mature |

---

### Summary

| | Count |
|---|---|
| 🟢 Python fully covers | **35** |
| 🔵 Python stronger | **11** |
| 🟡 Python partial | **4** |
| 🔴 MATLAB stronger | **2** |

(Counts reflect the rows above — 52 capabilities compared; re-count if you add rows.)

**AEA's target use case — offline research EEG analysis — is fully covered by MNE-Python and its ecosystem.** The few areas where MATLAB retains an edge (e.g. BCI/real-time) are explicitly out of AEA's scope.

## 9. Living document

This file gets updated as we learn. If a competing tool ships a feature we claimed as ours, mark it ⚠️ here and revise the novelty claim. If a recipe library reaches 50 entries, update N1 to ✅ confirmed.
