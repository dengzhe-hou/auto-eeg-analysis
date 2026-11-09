"""Assign responses and join observations using explicit study identities."""
import numpy as np
import pandas as pd


def _identity(table, keys):
    if not keys:
        raise ValueError("Supply the observation identity keys; row order is not an identity")
    if table[keys].isna().any().any() or table.duplicated(keys).any():
        raise ValueError(f"Missing or duplicate observation identity in {keys}")


def match_responses(stimuli, responses, *, group_keys, trial_keys, sfreq,
                    response_window_ms, stop_at_next_stimulus, assignment):
    """First unused response in an explicitly approved half-open RT window.

    Columns: stimuli = identity keys, stim_sample, condition; responses =
    group keys, response_sample, response_code. Sample coordinates must refer
    to the same recording grid. Group keys identify recording/session/block.
    The selected assignment visits stimuli in chronological order per group;
    each response row can be used once. Other assignment conventions require
    an explicit implementation, not an inferred fallback.
    """
    if assignment != "first_unused":
        raise ValueError("This helper implements explicitly selected first_unused assignment only")
    if not group_keys or not set(group_keys).issubset(trial_keys):
        raise ValueError("Include the recording/block identity in trial_keys")
    _identity(stimuli, trial_keys)
    if stimuli.duplicated(group_keys + ["stim_sample"]).any():
        raise ValueError("Simultaneous stimuli need an explicit trial-specific response association")
    if responses[group_keys].isna().any().any():
        raise ValueError("Response recording/block identity is missing")
    lo, hi = response_window_ms
    if (not np.isfinite([sfreq, lo, hi]).all() or sfreq <= 0
            or not 0 <= lo < hi or not isinstance(stop_at_next_stimulus, bool)):
        raise ValueError("Supply sfreq, ordered nonnegative RT bounds and explicit next-stimulus policy")
    for table, column in ((stimuli, "stim_sample"), (responses, "response_sample")):
        values = table[column].to_numpy(dtype=float)
        if not np.isfinite(values).all() or not np.equal(values, np.round(values)).all():
            raise ValueError("Event sample positions must be finite integers on the recording grid")

    source = responses.reset_index(drop=True).copy()
    source["response_row"] = np.arange(len(source))
    source = source.sort_values("response_sample", kind="stable")
    used = set()
    trials = []
    grouper = group_keys[0] if len(group_keys) == 1 else group_keys
    for _, group in stimuli.groupby(grouper, sort=False):
        group = group.sort_values("stim_sample", kind="stable")
        rows = group.to_dict("records")
        available = source
        for key in group_keys:
            available = available[available[key] == rows[0][key]]
        for index, row in enumerate(rows):
            start = row["stim_sample"] + lo * sfreq / 1000
            stop = row["stim_sample"] + hi * sfreq / 1000
            if stop_at_next_stimulus and index + 1 < len(rows):
                stop = min(stop, rows[index + 1]["stim_sample"])
            candidates = available[(available["response_sample"] >= start)
                                   & (available["response_sample"] < stop)]
            candidates = candidates[~candidates["response_row"].isin(used)]
            record = dict(row, status="missed", response_sample=None,
                          response_code=None, response_row=None, rt=np.nan,
                          eligible_response_count=int(len(candidates)))
            if not candidates.empty:
                response = candidates.iloc[0]
                used.add(int(response["response_row"]))
                record.update(status="matched", response_sample=int(response["response_sample"]),
                              response_code=response["response_code"],
                              response_row=int(response["response_row"]),
                              rt=float((response["response_sample"]-row["stim_sample"]) / sfreq * 1000))
            trials.append(record)
    duplicate = source.duplicated(group_keys + ["response_sample", "response_code"], keep=False)
    audit = {"assignment": assignment, "response_window_ms": [lo, hi],
             "window_boundary": "left_inclusive_right_exclusive",
             "stop_at_next_stimulus": stop_at_next_stimulus,
             "n_stimuli": int(len(stimuli)), "n_responses": int(len(responses)),
             "n_matched": len(used), "n_missed": int(len(stimuli)-len(used)),
             "duplicate_response_rows": source.loc[duplicate, "response_row"].tolist(),
             "unassigned_responses": source.loc[~source["response_row"].isin(used)].to_dict("records")}
    return pd.DataFrame(trials), audit


def align_trials(left, right, *, keys, right_columns, unmatched_policy):
    """One-to-one key join, retaining left order and explicit unmatched records.

    ``intersection`` is allowed only when the study approves using the common
    retained observations. ``error`` rejects any mismatch. Neither is a default.
    """
    _identity(left, keys)
    _identity(right, keys)
    if unmatched_policy not in ("error", "intersection"):
        raise ValueError("Select error or intersection for unmatched observations explicitly")
    if set(right_columns) & set(left.columns):
        raise ValueError("Give joined measurement columns distinct names")
    ordered = left.copy()
    ordered["_left_order"] = np.arange(len(ordered))
    outer = ordered.merge(right[keys + right_columns], on=keys, how="outer",
                          validate="one_to_one", indicator=True)
    missing_left = outer.loc[outer["_merge"] == "left_only", keys].to_dict("records")
    missing_right = outer.loc[outer["_merge"] == "right_only", keys].to_dict("records")
    if unmatched_policy == "error" and (missing_left or missing_right):
        raise ValueError(f"Unmatched observation identities: left-only={missing_left}, right-only={missing_right}")
    matched = outer.loc[outer["_merge"] == "both"].sort_values("_left_order")
    if matched.empty:
        raise ValueError("No common identified observations remain")
    audit = {"keys": list(keys), "unmatched_policy": unmatched_policy,
             "n_left": int(len(left)), "n_right": int(len(right)),
             "n_matched": int(len(matched)), "unmatched_left": missing_left,
             "unmatched_right": missing_right}
    return matched.drop(columns=["_merge", "_left_order"]).reset_index(drop=True), audit


def paired_values(table, *, unit_keys, condition_column, conditions,
                  value_column, unmatched_policy):
    """Align already summarized units or genuine trial pairs, without truncation.

    This does not aggregate trials. Duplicate unit/condition rows fail so the
    caller must supply the approved participant summary or true pair identity.
    """
    if len(conditions) != 2 or conditions[0] == conditions[1]:
        raise ValueError("Supply two distinct conditions in the approved contrast order")
    selected = table[table[condition_column].isin(conditions)]
    _identity(selected, unit_keys + [condition_column])
    a = selected.loc[selected[condition_column] == conditions[0], unit_keys + [value_column]]
    b = selected.loc[selected[condition_column] == conditions[1], unit_keys + [value_column]]
    a = a.rename(columns={value_column: "value_a"})
    b = b.rename(columns={value_column: "value_b"})
    joined, audit = align_trials(a, b, keys=unit_keys, right_columns=["value_b"],
                                unmatched_policy=unmatched_policy)
    values = joined[["value_a", "value_b"]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Paired measurements must be finite; apply the approved missing-data policy")
    audit.update(conditions=list(conditions), paired_units=joined[unit_keys].to_dict("records"))
    return values[:, 0], values[:, 1], audit
