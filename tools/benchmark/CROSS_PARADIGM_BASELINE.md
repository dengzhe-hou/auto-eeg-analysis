# Why the no-recipe baseline diverges — and when it does not

The spec-precision eval found the no-recipe baseline (L0) off by ~0.9 µV on MMN, with 7 of 9
generations independently choosing a **P9/P10 mastoid-style reference** where the certified spec uses
an **average reference**. That raised an obvious question: is this a *paradigm-specific quirk*, a
general LLM habit, or something else? We tested it on two more ERP CORE components.

## Design

Same blind protocol, condition **L0 only** (scientific goal + dataset brief, **no protocol document**),
k=2 per paradigm, code-only generation executed by us. Each generator was asked to state its
**reference scheme** explicitly.

## Result: the baseline is paradigm-appropriately opinionated

| Paradigm (topography) | L0 reference choice | matches certified spec? | grand mean | certified | **ratio** |
|---|---|:---:|---:|---:|:---:|
| **MMN** (frontocentral) | mastoid P9/P10 (7/9) | ✗ | −1.735 | −0.840 | **2.1×** |
| **P3b** (centro-parietal) | mastoid P9/P10 (2/2) | ✗ | +5.475 / +4.978 | +1.683 | **3.25× / 2.96×** |
| **N170** (occipito-temporal) | **average** (2/2) | **✓** | −1.202 / −1.226 | −1.181 | **1.02× / 1.04×** |

**Where the baseline's reference choice happens to match the certified specification (N170), a bare
LLM with no protocol at all reproduces the certified grand mean to within 2–4%.** Where it differs
(MMN, P3), divergence is 2–3×.

## Interpretation

The choices are **not arbitrary and not a blanket habit**. They track the canonical reference for each
component in the EEG literature:

- MMN and P3b are frontocentral/centro-parietal — **mastoid referencing is the conventional choice**,
  and it enlarges those deflections.
- N170 is measured at **PO7/PO8/P7/P8** — mastoid sites P9/P10 sit essentially *inside* that ROI, so
  mastoid referencing would contaminate the measurement. Both generations avoided it and chose average
  reference, which is what the field does for N170.

That is a competent, paradigm-sensitive judgement — made with no protocol.

> **The unspecified baseline is not "unreliable". It is opinionated in a paradigm-appropriate way.
> Its divergence from a certified pipeline is almost entirely explained by whether the specification's
> choices happen to coincide with the field's convention for that paradigm.**

## What this changes

**1. Reframes what the recipe buys.** Not protection from incompetence — protection from *ambiguity
about which convention is in force*. When spec and convention agree (N170), the recipe adds little
accuracy; when they disagree (MMN, P3), it is the only thing that makes the pipeline follow the spec
rather than the convention.

**2. Sharpens the "certified ≠ optimal" point.** The P3 baseline is ~3× the certified value not
because it is wrong but because it applied the conventional reference. Both analyses are defensible;
they are not the same number. A certified corpus therefore commits its users to *a* convention, and
that commitment should be explicit and justified — not an accident of whoever wrote the spec.

**3. Predicts where certification matters most:** paradigms where the specification departs from field
convention. Those are exactly the cases where a reader will assume the conventional analysis and get
something else.

## Honest limitations
1. **k = 2 per new paradigm** (MMN had k=9). The N170 and P3 patterns are consistent within themselves
   but two generations cannot establish a rate — given that the MMN conclusion flipped repeatedly
   between k=3 and k=9, treat the P3/N170 numbers as indicative.
2. **Reference scheme is one fork among several.** ICA, rejection threshold, and resampling also varied;
   the reference simply dominates the amplitude. A full decomposition is not attempted here.
3. Sample sizes differ across L0 runs (P3: n=11 and n=18 of 20) because rejection thresholds differed,
   so the grand means are not strictly like-for-like.
4. "Matches convention" is our reading of the literature, not a measured quantity. The
   [EEGManyPipelines](https://eegmanypipelines.github.io/) dataset (168 human teams, one EEG dataset)
   is the obvious way to measure what human analysts actually choose, and is the natural next step.
