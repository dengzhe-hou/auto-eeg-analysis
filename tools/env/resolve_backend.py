#!/usr/bin/env python
"""Resolve which computation backend a capability should use, and say so in writing.

AEA supports three backends for ERP work — MNE-Python (the reference, which produced every
committed certified value), EEGLAB and FieldTrip. This script turns "which one do I use?" into a
recorded decision rather than an implicit one.

It exists because of a specific empirical result. Cross-toolbox agreement is **not** a property of
the toolbox: run the same analysis in EEGLAB or FieldTrip under each toolbox's own defaults and
per-subject amplitudes differ by up to 43% of the group effect, but pin the specification
completely and the same three toolboxes land within 0.05 µV of each other with r = 1.0000
(`https://github.com/dengzhe-hou/auto-eeg-analysis/blob/995f53d42cc74205b164e8711d4b289b8c2ad3a1/tools/benchmark/CROSS_TOOLBOX_EVAL.md`). So a backend may never be selected without also
emitting the numerical conventions that selection commits you to.

Three rules, all enforced here:

1. **Never degrade silently.** If no candidate backend is available, exit non-zero with the
   install hint. A missing backend is a decision the user has to see.
2. **Never switch silently.** If the caller says the result must match a certified reference
   (`--certified-reference`), any backend other than the one those values were certified on is
   refused unless the caller passes `--allow-uncertified`, and the measured divergence is
   printed either way.
3. **Never assert unmeasured equivalence.** Where `backends.json` records `measured: false`, the
   report says so instead of implying the backends are interchangeable.

Usage:
    python tools/env/resolve_backend.py --capability erp.preprocess_average \
        --env ENVIRONMENT.json --out preprocess-stage/BACKEND_RESOLUTION.md
    python tools/env/resolve_backend.py --capability erp.preprocess_average --prefer eeglab
    python tools/env/resolve_backend.py --capability erp.preprocess_average --certified-reference mne
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKENDS_JSON = HERE / "backends.json"


class ResolutionError(RuntimeError):
    """No backend could be resolved. Never swallowed — this is rule 1."""


def _lookup(env: dict, dotted: str) -> dict | None:
    """Follow a dotted path into ENVIRONMENT.json, e.g. 'python_packages.mne'."""
    node: object = env
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, dict) else None


def backend_available(env: dict, spec: dict) -> tuple[bool, list[str]]:
    """A backend is usable only if EVERY requirement is present. Returns (ok, missing)."""
    missing = []
    for req in spec.get("requires", []):
        node = _lookup(env, req)
        if not node or not node.get("available"):
            hint = (node or {}).get("hint") or (node or {}).get("pip") or ""
            missing.append(f"{req}{f' — {hint}' if hint else ''}")
    return (not missing), missing


def resolve(
    capability: str,
    env: dict,
    registry: dict,
    prefer: str | None = None,
    certified_reference: str | None = None,
    allow_uncertified: bool = False,
) -> dict:
    caps = registry["capabilities"]
    if capability not in caps:
        raise ResolutionError(
            f"unknown capability {capability!r}; known: {', '.join(sorted(caps))}"
        )
    cap = caps[capability]
    backends = registry["backends"]

    order = list(cap["candidates"])
    if prefer:
        if prefer not in order:
            raise ResolutionError(
                f"backend {prefer!r} is not a candidate for {capability!r} "
                f"(candidates: {', '.join(order)})"
            )
        order = [prefer] + [b for b in order if b != prefer]

    considered, chosen = [], None
    for name in order:
        ok, missing = backend_available(env, backends[name])
        considered.append({"backend": name, "available": ok, "missing": missing})
        if ok and chosen is None:
            chosen = name

    if chosen is None:
        lines = [f"no backend available for capability {capability!r}. Candidates and what each needs:"]
        for c in considered:
            lines.append(f"  - {c['backend']}: missing {', '.join(c['missing'])}")
        raise ResolutionError("\n".join(lines))

    # Rule 2 — never switch silently away from the backend the numbers were certified on.
    refusal = None
    if certified_reference and chosen != certified_reference:
        agree = cap.get("agreement", {}).get(chosen, {})
        detail = (
            f"measured worst-case per-subject divergence "
            f"{agree.get('worst_max_abs_diff_uV')} µV over {agree.get('n_components')} components"
            if agree.get("measured")
            else f"agreement with {certified_reference} has NOT been measured for this capability"
        )
        if not allow_uncertified:
            raise ResolutionError(
                f"refusing to resolve {capability!r} to {chosen!r}: the expected values were "
                f"certified on {certified_reference!r} and {chosen!r} will not reproduce them "
                f"exactly ({detail}).\n"
                f"Either make {certified_reference!r} available, or pass --allow-uncertified and "
                f"accept that the result is no longer digit-comparable to the certified reference."
            )
        refusal = detail

    return {
        "capability": capability,
        "chosen": chosen,
        "chosen_label": backends[chosen]["label"],
        "is_reference": bool(backends[chosen].get("reference")),
        "considered": considered,
        "agreement": cap.get("agreement", {}).get(chosen, {}),
        "pin": cap.get("pin", []),
        "description": cap.get("description", ""),
        "certified_reference": certified_reference,
        "uncertified_override": refusal,
    }


def render_markdown(res: dict, env: dict) -> str:
    b = res["chosen"]
    out: list[str] = []
    a = out.append

    a(f"# Backend resolution — `{res['capability']}`")
    a("")
    a(f"**Resolved to: `{b}` — {res['chosen_label']}**"
      + ("  *(the certified reference backend)*" if res["is_reference"] else ""))
    a("")
    a(f"{res['description']}")
    a("")
    a(f"Probed environment: `{env.get('probed_at', 'unknown')}` "
      f"(ENVIRONMENT.json schema {env.get('schema_version', '?')})")
    a("")

    a("## Candidates considered")
    a("")
    a("| backend | available | blocked by |")
    a("|---|:---:|---|")
    for c in res["considered"]:
        mark = "✅" if c["available"] else "❌"
        sel = " ← **selected**" if c["backend"] == b else ""
        a(f"| `{c['backend']}`{sel} | {mark} | {'; '.join(c['missing']) or '—'} |")
    a("")

    a("## Numerical agreement with the certified reference")
    a("")
    ag = res["agreement"]
    if ag.get("role") == "reference":
        a("This **is** the reference backend — the committed certified values were produced by it.")
        if ag.get("evidence"):
            a(f"Evidence: {ag['evidence']}")
    elif ag.get("measured") and "worst_max_abs_diff_uV" not in ag:
        # A measured capability whose agreement is not an ERP-amplitude comparison (the cluster
        # test records partitions, summed-t and extents). Rendering the ERP fields here raised
        # KeyError for the FieldTrip cluster backend -- found by the Round-1 reviewer reproducing
        # the documented resolve-and-report path.
        a(f"Measured on **{ag.get('n_components', '?')} components** "
          f"({', '.join(ag.get('components', []))}):")
        a("")
        skip = {"measured", "components", "n_components", "evidence", "elementwise", "role", "caveat"}
        for k, v in ag.items():
            if k in skip or not isinstance(v, (bool, int, float, str)):
                continue
            a(f"- {k.replace('_', ' ')}: **{v}**")
        if isinstance(ag.get("elementwise"), dict):
            a(f"- elementwise: {ag['elementwise'].get('supported_wording', '')}")
        if ag.get("caveat"):
            a("")
            a(f"Caveat: {ag['caveat']}")
        a("")
        a(f"Evidence: {ag.get('evidence', '')}")
    elif ag.get("measured"):
        a(f"Measured on **{ag['n_components']} components** ({', '.join(ag['components'])}):")
        a("")
        a(f"- worst-case per-subject difference: **{ag['worst_max_abs_diff_uV']} µV**")
        a(f"- worst-case mean per-subject difference: {ag['worst_mean_abs_diff_uV']} µV")
        a(f"- minimum Lin's CCC: {ag['min_ccc']}")
        a(f"- worst grand-mean difference: {ag['worst_grand_mean_diff_pct']}%")
        a(f"- group-level conclusion reproduced: **{ag['group_conclusion_reproduced']}**")
        if "with_fully_pinned_spec" in ag:
            p = ag["with_fully_pinned_spec"]
            a(f"- with the specification fully pinned ({p['component']}): "
              f"**{p['max_abs_diff_uV']} µV**, CCC {p['ccc']}, r {p['pearson_r']} — {p['note']}")
        a("")
        a(f"Evidence: {ag['evidence']}")
        a("")
        a("> These are group-robust but **not** per-subject-identical numbers. Individual-differences "
          "analyses and single-subject classification are sensitive to this difference; group "
          "conclusions were not.")
    else:
        a(f"⚠️ **Not measured.** {ag.get('reason', 'No comparison against the reference exists.')}")
        a("")
        a("Do not describe this backend's output as equivalent to the certified reference.")
    a("")

    if res.get("uncertified_override"):
        a("## ⚠️ Uncertified backend accepted by explicit override")
        a("")
        a(f"The expected values were certified on `{res['certified_reference']}`; "
          f"`{b}` was accepted via `--allow-uncertified`.")
        a(f"{res['uncertified_override']}.")
        a("")
        a("**The result of this stage is no longer digit-comparable to the certified reference.** "
          "Say so in the methods text and the audit.")
        a("")

    a("## Conventions this backend commits you to — pin all of them")
    a("")
    a("Cross-toolbox agreement is a property of how completely the specification is pinned, not of "
      "the toolbox. Every item below must be written explicitly into the generated code; leaving "
      "any to the toolbox default is what produced the divergences above.")
    a("")
    for p in res["pin"]:
        a(f"### `{p['id']}` — {p['question']}")
        a("")
        for k in ("mne", "eeglab", "fieldtrip"):
            if k in p:
                mark = " ← **in force**" if k == b else ""
                a(f"- **{k}**: {p[k]}{mark}")
        a("")
        a(f"*Consequence if unpinned:* {p['consequence']}")
        a("")

    a("---")
    a("")
    a("Generated by `tools/env/resolve_backend.py`. Regenerate after any environment change; "
      "`eeg-audit` reads this file.")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--capability", required=True)
    ap.add_argument("--env", type=Path, default=Path("ENVIRONMENT.json"))
    ap.add_argument("--registry", type=Path, default=BACKENDS_JSON)
    ap.add_argument("--prefer", help="try this backend first (still must be available)")
    ap.add_argument("--certified-reference",
                    help="backend the expected values were certified on; resolving to any other "
                         "backend then fails unless --allow-uncertified is given")
    ap.add_argument("--allow-uncertified", action="store_true")
    ap.add_argument("--out", type=Path, help="write BACKEND_RESOLUTION.md here")
    ap.add_argument("--json", action="store_true", help="print the resolution as JSON")
    args = ap.parse_args()

    if not args.env.exists():
        print(f"ERROR: {args.env} not found. Run tools/env/check_env.sh (or .ps1) first.",
              file=sys.stderr)
        return 2
    env = json.loads(args.env.read_text(encoding="utf-8-sig"))
    registry = json.loads(args.registry.read_text(encoding="utf-8-sig"))

    try:
        res = resolve(args.capability, env, registry, prefer=args.prefer,
                      certified_reference=args.certified_reference,
                      allow_uncertified=args.allow_uncertified)
    except ResolutionError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"{args.capability} -> {res['chosen']} ({res['chosen_label']})"
              + ("  [reference backend]" if res["is_reference"] else ""))
        for p in res["pin"]:
            print(f"  pin: {p['id']}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(render_markdown(res, env), encoding="utf-8")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
