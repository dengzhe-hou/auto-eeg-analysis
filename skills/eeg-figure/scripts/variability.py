"""Compute a planned descriptive mean band and its matching caption together."""
import numpy as np
from scipy import stats


def mean_band(data, *, specification):
    """Use observations by time in the stated unit; no uncertainty default.

    Supported approved specifications: SEM with explicit std_ddof, two-sided
    Student-t CI with sample SD, or percentile-bootstrap CI of the mean with
    explicit level, resampling count and seed. Other estimators need their own
    approved implementation, not a silent fallback to this arithmetic mean.
    """
    data = np.asarray(data, dtype=float)
    if data.ndim != 2 or len(data) < 2 or not np.isfinite(data).all():
        raise ValueError("Mean bands need finite observations-by-time data and at least two observations")
    mean = data.mean(axis=0)
    kind = specification["kind"]
    n = len(data)
    unit = specification["unit"]
    observation_unit = specification["observation_unit"]
    if kind in ("student_t_ci", "bootstrap_ci") and specification["sidedness"] != "two-sided":
        raise ValueError("This mean-band helper implements explicitly approved two-sided CIs")
    if kind == "sem":
        ddof = specification["std_ddof"]
        if ddof not in (0, 1):
            raise ValueError("This SEM helper supports an approved std_ddof of 0 or 1")
        half_width = data.std(axis=0, ddof=ddof) / np.sqrt(n)
        lower, upper = mean - half_width, mean + half_width
        description = f"±1 SEM (SD ddof={ddof})"
    elif kind == "student_t_ci":
        if specification["std_ddof"] != 1:
            raise ValueError("Student-t intervals here use sample SD (std_ddof=1)")
        level = specification["level"]
        if not 0 < level < 1:
            raise ValueError("The approved confidence level must be between 0 and 1")
        half_width = stats.t.ppf((1 + level) / 2, n - 1) * data.std(axis=0, ddof=1) / np.sqrt(n)
        lower, upper = mean - half_width, mean + half_width
        description = f"two-sided {100 * level:g}% Student-t CI (df={n-1})"
    elif kind == "bootstrap_ci":
        if specification["method"] != "percentile":
            raise ValueError("Use the approved bootstrap method's own implementation")
        if not 0 < specification["level"] < 1 or specification["seed"] is None:
            raise ValueError("Specify the approved confidence level and bootstrap seed")
        interval = stats.bootstrap((data,), np.mean, axis=0, vectorized=True,
            confidence_level=specification["level"], n_resamples=specification["n_resamples"],
            method="percentile", alternative="two-sided",
            random_state=specification["seed"]).confidence_interval
        lower, upper = interval.low, interval.high
        description = (f"two-sided {100 * specification['level']:g}% percentile-bootstrap CI "
                       f"of the mean ({specification['n_resamples']} resamples; seed={specification['seed']})")
    else:
        raise ValueError("Use the approved uncertainty method's own implementation")
    caption = f"Line shows the arithmetic mean; shaded band shows {description}; N={n} {observation_unit}; unit {unit}."
    return {"mean": mean, "lower": lower, "upper": upper, "caption": caption,
            "metadata": {"n_observations": n, "specification": dict(specification)}}
