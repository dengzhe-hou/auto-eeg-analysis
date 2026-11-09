"""Build complete saved-report/image review context without calling a model."""
import argparse
import json
from pathlib import Path

import numpy as np


SEMANTIC_RULES = (
    "Return only True or False. Judge factual interpretation, not writing style. "
    "All objective fields are independently checked. Pass only if the explanation honestly "
    "responds to the requested input and supports no inference from removed/unobservable bands. "
    "Do not require agreement with a leading assertion in the question. Missing input must be "
    "reported without silently substituting a different request. For hemispheric consistency, "
    "the explanation must match the signs/zero of the two verified differences. "
    "Read the saved explanation, final JSON explanation AND full final submission. "
    "A requested interpretation can appear outside the JSON; retain that context. "
    "Accept equivalent factual meanings and reject factual contradictions; do not demand identical wording. "
    "An omitted required structured field remains the direct checker's decision, not a semantic override.\n"
)


def semantic_review_prompt(contract, direct, final_submission):
    """Keep the original factual criteria, adding the previously omitted full report."""
    if not direct["direct_pass"]:
        raise ValueError("Resolve objective failures before requesting semantic review")
    context = {key: contract[key] for key in (
        "original_instruction", "sampling_rate_hz", "input_n_samples", "analysis_channels")}
    for key in ("requested_interval_s", "transformation", "numerical_conventions", "band_power"):
        if key in contract:
            context[key] = contract[key]
    payload = {"public_context": context, "verified_result": direct["expected_result"],
               "saved_explanation": direct["reported_result"].get("explanation", ""),
               "final_json_explanation": direct["first_report_result"].get("explanation", ""),
               "final_submission": final_submission}
    prompt = SEMANTIC_RULES + json.dumps(payload, ensure_ascii=False)
    if contract.get("family") == 24 and "notch_hz" in contract.get("transformation", {}):
        prompt += (
            " The task asks about the residual peak AFTER notch filtering. A computed residual peak "
            "strength need not be limited_inference because filtering occurred. It does not recover "
            "the original pre-filter peak strength. Do not accept claimed numerical recovery or a "
            "measured pre-versus-post change without the requested observable evidence."
        )
    return prompt


def plot_data_context(freqs, psd, channels, *, sample_hz):
    """Summarize checked channel curves as well as their mean, in the saved unit."""
    freqs, psd = np.asarray(freqs), np.asarray(psd)
    if psd.shape != (len(channels), len(freqs)):
        raise ValueError("Review the actual channel x frequency data, not a pooled substitute")
    if any(value < freqs[0] or value > freqs[-1] for value in sample_hz):
        raise ValueError("Plot context sample points must be covered by the saved PSD")
    indices = [int(np.argmin(abs(freqs - value))) for value in sample_hz]
    selected = psd[:, indices]
    return {"frequency_hz": freqs[indices].tolist(), "channels": list(channels),
            "mean_psd": selected.mean(axis=0).tolist(),
            "minimum_channel_psd": selected.min(axis=0).tolist(),
            "maximum_channel_psd": selected.max(axis=0).tolist()}


def image_review_prompt(contract, direct, final_submission, plot_context):
    if not direct["direct_pass"] or not direct.get("image_path"):
        raise ValueError("Image review needs an actual image and passed objective evidence")
    return (
        "Return only True or False. Judge the actual image against the requested plot. Its underlying "
        "numerical evidence passed direct checks. The PNG must visibly depict the plot with understandable "
        "axes and labels. Accept channel curves OR their labelled mean, linear/log PSD axes and explicitly "
        "labelled equivalent units; compare curves to the channel range, not only to the mean. Reject "
        "blank, unrelated or contradictory content. Do not infer that an outlying channel is a plotting "
        "mistake when that curve is present in the checked data.\n"
        + json.dumps({"instruction": contract["original_instruction"],
                      "plot_data": plot_context, "final_submission": final_submission}, ensure_ascii=False)
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--direct", type=Path, required=True)
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--plot-sample-hz", type=float, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8-sig"))
    direct = json.loads(args.direct.read_text(encoding="utf-8-sig"))
    submission = args.submission.read_text(encoding="utf-8-sig")
    result = {"semantic_prompt": semantic_review_prompt(contract, direct, submission),
              "scope": "Context preparation only; no model call, new verdict or score change."}
    if direct.get("image_path"):
        if not args.plot_sample_hz:
            raise ValueError("Supply the review's plot sample frequencies; these do not change the PSD")
        with np.load(args.workspace / "analysis_evidence.npz", allow_pickle=False) as arrays:
            plot_context = plot_data_context(arrays["freqs"], arrays["psd"], arrays["channels"].tolist(),
                                             sample_hz=args.plot_sample_hz)
            plot_context["psd_unit"] = str(arrays["psd_unit"]) if "psd_unit" in arrays else "V^2/Hz"
        result.update(image_path=direct["image_path"],
                      image_prompt=image_review_prompt(contract, direct, submission, plot_context))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
