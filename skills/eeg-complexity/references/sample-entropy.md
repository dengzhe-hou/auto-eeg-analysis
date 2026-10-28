# Sample entropy on a specified EEG segment

Use the channels, duration, sampling rate, embedding dimension and tolerance in
the approved task. The sliding-window defaults elsewhere in the skill do not
override an explicit segment calculation. Resolve channel identities and types
from the recording and its documentation; a library's generic EEG type alone
does not establish an electrode's anatomical identity.

## Computation

The bundled helper needs NumPy and SciPy, with no optional entropy package.
It counts matching template pairs directly with a tree, avoiding a full
distance matrix and neighbor lists. Memory scales with the embedded signal;
runtime still depends on its length and structure. Read the selected segment
without preloading the entire recording when the file reader supports it.

```python
from pathlib import Path
import runpy

# AEA_ROOT is the installed checkout or the run's frozen aea/ directory.
helper = Path(AEA_ROOT) / "skills/eeg-complexity/scripts/sample_entropy.py"
sample_entropy = runpy.run_path(str(helper))["sample_entropy"]

# x is ONE selected channel's requested segment, without extra resampling.
result = sample_entropy(x, m=2, r_fraction=0.2, closed=True)
value = result["sample_entropy"]
```

Pass the task's actual m and tolerance fraction, rather than always using the
example values. Run per channel, then aggregate the resulting values as the
task specifies. Report undefined values and their channels; do not silently
replace them with zero or omit them from an average.

## Numerical conventions

- Distance is Chebyshev; self-matches are excluded.
- Both m and m+1 embeddings use the same N-m starting positions.
- r uses the segment's own standard deviation with ddof=0.
- `closed=True` counts distances <= r; `closed=False` counts distances < r.
  Use the approved comparison rule, or disclose the choice when unspecified.
- SampEn is -log(A/B), with A and B the unordered matching-pair counts for
  dimensions m+1 and m. It is undefined if either count is zero.

For 30000 samples, a dense pairwise calculation has about 900 million entries;
broadcasting subtraction and absolute value can require tens of GB. Do not
construct those arrays for long segments. Reducing the requested duration or
sampling rate changes the analysis; choose an equivalent counting method.

Validate a new counting implementation against direct comparisons on short
signals, including repeated values and the selected radius boundary. The
bundled helper has those checks. This does not certify channel selection or
equivalence to libraries with different embedding or boundary conventions.
