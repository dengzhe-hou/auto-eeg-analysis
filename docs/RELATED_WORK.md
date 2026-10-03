# Related work & competitive landscape (LLM × EEG)

> Honesty obligation (COMPARISON.md §9): "if a competing tool ships a feature we claimed as ours,
> mark it and revise the novelty claim." This file is the competitor scan the distillation process
> previously skipped (it asked "what methods is AEA missing?", never "what systems did others build?").
> First scan 2026-07 (web + arXiv). For library contributions, see [CONTRIBUTING.md](../CONTRIBUTING.md).

## The key distinction: artifact *type*

There are **two different kinds of thing** in this space, and AEA is not the same type as the recent
headline systems:

| Type | What it is | Examples |
|------|-----------|----------|
| **Agent framework** | a *running system*: an LLM controller + a toolbox that schedules tools at runtime; you run *their* system | **EEGAgent**, **BrainAgent** |
| **Skills corpus** | a *portable body of Markdown methodology* that any agent host reads and executes; no runtime, no lock-in | **ARIS** (general ML), **AEA** (EEG) |

AEA is a **skills corpus** — ARIS's architecture specialized to EEG. Its true peer set is the
model-agnostic Markdown-skills ecosystem (ARIS, awesome-claude-skills, …), which is **general/coding;
our scan surfaced no EEG-specialized member.** So AEA is plausibly the **first portable EEG-methodology
skills corpus** — a narrower, defensible claim than "first LLM × EEG" (which is false: agent
frameworks predate it).

## Direct prior work (agent frameworks — must be cited)

- **EEGAgent** — *A Unified Framework for Automated EEG Analysis Using LLMs*, **AAAI 2026** ([arXiv 2511.09947](https://arxiv.org/abs/2511.09947)). LLM schedules a toolbox for perception / exploration / event detection / **clinical report** (ACNS template). *(This is the PDF already sitting in `papers/2511.09947.pdf` — it was known but never entered the competitor matrix; that gap is what this file fixes.)*
- **BrainAgent** — *LLM-Driven Multi-Agent Framework for Autonomous Brain Signal Understanding* ([arXiv 2606.25400](https://arxiv.org/abs/2606.25400)). NL → long-horizon executable pipelines.
- **LLM-for-EEG survey** — *Large Language Models for EEG: A Comprehensive Survey and Taxonomy* ([arXiv 2506.06353](https://arxiv.org/abs/2506.06353)). Confirms this is now a populated subfield with its own taxonomy.
- Landscape (not full competitors): **AutocleanEEG ICVision** ([arXiv 2512.00194](https://arxiv.org/abs/2512.00194), VLM ICA-artifact classifier); **EEG-Pype** (MNE GUI pipeline, PLOS Comput Biol); PREP, MNE-BIDS-Pipeline, HAPPE, DISCOVER-EEG (classical automated pipelines, already in `COMPARISON.md`).

## Where AEA still differs (verified against the two strongest agent frameworks)

Each row was checked by reading the papers directly (2026-07).

| Differentiator | EEGAgent | BrainAgent | **AEA** |
|---|:---:|:---:|:---:|
| Cross-tool **digit-by-digit** numeric validation vs a gold standard (MNE-BIDS-Pipeline) | ✗ | ✗ | ✅ 5 ERP CORE components, CCC ≥ 0.9997 |
| Automated **cross-model reviewer** (adversarial Reviewer-2) | ✗ | ✗ | ✅ 8/8 seeded-defect recall, both backends |
| **COBIDAS-MEEG** methods-paragraph generation | ✗ (clinical report) | ✗ | ✅ 100% coverage, 0 fabrications |
| Reproducible **recipe library** of published paradigms | ✗ (generic toolbox) | ✗ | ✅ 7 validated |

**None of the agent frameworks does numeric validation, cross-model audit, or COBIDAS methods text.**
So AEA's defensible novelty is *not* "first LLM × EEG" and *not* the skills format itself — it is the
**combination of validation depth + cross-model audit + COBIDAS methods + recipe reproducibility,
each empirically demonstrated**, delivered as a portable skills corpus. That combination sits in the
competitors' shared blind spot.

## What this changes in our claims

- **Retire**: "first LLM-native EEG layer / first LLM × EEG." (EEGAgent, AAAI 2026, predates.)
- **Keep (narrowed)**: first portable EEG-methodology *skills corpus* (no EEG member of that category found).
- **Lead with**: the four validated differentiators above — that is the real moat, and it is on the
  axis (validation + audit) that every scanned competitor omits.
