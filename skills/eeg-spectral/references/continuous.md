## Welch and band power

Use the approved channels, processing order and interval. Signals are in V,
PSD in V²/Hz. Every Welch setting comes from the plan; no study defaults apply.
Keep a channel axis even for one channel. Integrate numerator and denominator
on the same grid when relative power is requested. Use the approved aggregation:
the mean of channel-wise ratios and the ratio of mean powers differ. Absolute
band power has no denominator. A dominant-band question alone does not resolve
absolute versus relative power or channel weighting.

Get MNE EEG with `raw.get_data(units="V")` or the bounded preprocessing helper.
The EDF/CNT source may have been recorded in uV; the reader has already handled
that conversion. A further `*1e-6` changes PSD by `1e-12` while leaving many
ratios unchanged. A nonnegative PSD or plausible ratio does not check units.
Only apply filters explicitly listed in the approved operations.

```python
from pathlib import Path
import runpy
spectral = runpy.run_path(str(Path(AEA_ROOT) / "skills/eeg-spectral/scripts/continuous.py"))
freqs, psd = spectral["welch_from_plan"](
    data_in_volts, sfreq, plan=approved_public_plan["welch"])
```

Only for an approved channel-wise relative-power calculation, use:

```python
ratios = spectral["channel_relative_power"](
    psd, freqs, band=approved_numerator_band, total_band=approved_total_band,
    upper_closed=approved_numerator_upper_closed,
    total_upper_closed=approved_denominator_upper_closed)
```

For a dominant-band request, use the [explicit summary](#explicit-band-power-summary)
after resolving its definition. PSD-only and absolute-power requests do not
acquire a relative-power calculation from this example.

AEA's Welch helpers return **`freqs, psd`**; MNE `psd_array_welch` returns
**`psd, freqs`**. Before integration, frequencies must be one-dimensional and
PSD's last axis must match their length. A swapped return is an API error;
reshaping or adding axes does not repair it. Use the plan adapter to preserve
the declared DC removal: `detrend="constant"` means `remove_dc=True`, not false.

Save actual channel names, frequencies and PSD. Label fractions, percentages
and percentage points; convert once. Use the task's total band and aggregation.
Save arrays actually used in plots. Do not squeeze single-channel PSD arrays.

The retained frequency axis must cover both bounds of every requested band.
`band_bins`, `integrated_power` and `maximum_bin_peak` reject partial coverage;
retain the full axis when a later summary needs wider support. Integration still
uses the approved selected bins and boundary convention, without interpolation.
Passing this grid check does not recover activity removed by preprocessing.

For a resolved JSON `welch` object, use `welch_from_plan`. Its canonical fields
are `segment_seconds`, `window`, `overlap_fraction`, `n_fft` (null or integer),
`remove_dc` (boolean) and `average`. The existing `detrend: "constant"`/false
and `n_fft: "n_per_seg"` form remains equivalent. Contradictory DC declarations
raise; a missing averaging choice is not filled from an example.

## Explicit band-power summary

Resolve `power_kind` (`absolute` or `relative`) and `aggregation` before computing
a categorical dominant band. Absolute power uses `mean_channel_power`; relative
power supports `mean_channel_ratios` or `ratio_of_channel_means`. Supply the total
band for relative power, or explicit null for absolute power. Each integration
definition contains `band` and a boolean `upper_closed`; the lower bound is
inclusive in this helper. Use another approved implementation for other bounds.
Missing scientific choices require resolution, not an inferred library default.
In unattended work record them as unresolved and continue independent work.

```python
settings = approved_public_plan["band_power"]
summary = spectral["band_power_summary"](psd, freqs,
    **{key: settings[key] for key in ("bands", "power_kind", "aggregation", "total_band")})
```

The result retains `selected_frequencies_hz` and every band's value. Transfer
the plan's boundary to the helper; do not hand-code `<` when `<=` was approved.
With a 0.25 Hz grid, inclusive 0.1–0.5 Hz contains both 0.25 and 0.5 Hz. Excluding
0.5 leaves one bin and causes an integration error; that error does not establish
a scientific inference limitation. Check the actual bins and approved rule.

Mean absolute power and mean relative power can rank the same saved PSD
differently. An example for one quantity does not approve it for another.
Do not choose the definition by whichever agrees with a benchmark answer or
the question's leading assertion. Preserve tied maxima until a reporting rule
is resolved. The [complete runner](../../../docs/PRELOADED_SKILLS.md#execute-and-check-a-complete-continuous-plan)
saves this definition and checks the derived outputs against the actual PSD.

## Maximum-bin alpha peak

Apply only to an approved maximum-bin estimator. Read search band and channels
from the plan. Estimate each channel's peak, then aggregate those frequencies.
Averaging PSDs first, smoothing, prominence tests and center of gravity differ.

```python
peaks = spectral["maximum_bin_peak"](psd, freqs, band=approved_search_band)
apf = float(peaks.mean())  # Only if arithmetic channel mean is approved.
```

For personalized power, use the approved APF offsets and total denominator,
integrating on the original PSD grid. Report undefined quantities explicitly.

Specify whether the personalized band is centered on the **mean peak** for all
channels or on **each channel's peak**. These produce different ratios. When
the approved plan says to first compute the mean APF and then define its band,
use `center_mode="mean_peak"`. Use `"per_channel_peak"` only when approved.

```python
alpha = spectral["personalized_alpha_power"](
    psd, freqs, search_band=approved_search_band, offsets=approved_offsets,
    total_band=approved_total_band, center_mode=approved_center_mode,
    upper_closed=approved_numerator_upper_closed,
    total_upper_closed=approved_denominator_upper_closed)
mean_apf = alpha["mean_peak_hz"]
# Only when the plan approves arithmetic averaging and percentage units:
mean_relative_percent = float(alpha["relative_power_per_channel"].mean() * 100)
```

Save the per-channel peaks, actual band centers and ratios with the PSD.
Generate JSON and the final report from these same computed values.
