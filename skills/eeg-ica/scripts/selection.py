"""Apply an explicitly approved policy to saved component labels and evidence."""
import numpy as np


def choose_components(labels, probabilities, *, reject_classes,
                      probability_threshold, require_corroboration,
                      corroborating_components):
    """Return decisions; do not fit ICA, run classifiers, or change exclusions.

    probabilities contains each predicted label's probability, as returned by
    mne_icalabel.label_components. Corroboration is keyed by that same label:
    None/absent means unavailable, [] means assessed but not corroborated.
    The threshold, eligible classes and need for corroboration are plan choices.
    """
    probabilities = np.asarray(probabilities, dtype=float)
    if probabilities.shape != (len(labels),) or not np.isfinite(probabilities).all():
        raise ValueError("Supply one finite predicted-class probability per component")
    if np.any((probabilities < 0) | (probabilities > 1)) or not 0 <= probability_threshold <= 1:
        raise ValueError("Probabilities and the approved threshold must be in [0, 1]")
    if not isinstance(require_corroboration, bool):
        raise ValueError("The approved corroboration requirement must be explicit")
    output = {"excluded": [], "ambiguous": [], "retained": [], "decisions": []}
    for index, (label, probability) in enumerate(zip(labels, probabilities)):
        if label == "brain":
            decision, reason = "retained", "brain_not_auto_rejected"
        elif label == "other":
            decision, reason = "ambiguous", "unclassified_component"
        elif label not in reject_classes:
            decision, reason = "retained", "class_not_authorized_for_rejection"
        elif probability < probability_threshold:
            decision, reason = "ambiguous", "below_approved_probability"
        elif require_corroboration and corroborating_components.get(label) is None:
            decision, reason = "ambiguous", "corroboration_unavailable"
        elif require_corroboration and index not in corroborating_components[label]:
            decision, reason = "ambiguous", "not_corroborated"
        else:
            decision, reason = "excluded", "approved_criteria_met"
        output[decision].append(index)
        output["decisions"].append({"component": index, "label": label,
            "probability": float(probability), "decision": decision, "reason": reason})
    return output
