"""Compare a run plan to existing approval/run evidence; mtime is only a hint."""
import argparse
from datetime import datetime
import json
from pathlib import Path


def _recorded_time(value):
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Recorded timestamps need an explicit timezone")
    return stamp


def check_plan_provenance(plan, *, approved_plan=None, approval_record=None,
                          analysis_record=None, approved_at=None,
                          analysis_started_at=None, outputs=()):
    """Check consistency of explicitly supplied evidence, not its authenticity.

    Extract timestamps from existing approval/run records and retain those
    source paths. Do not manufacture records or infer approval from mtimes.
    A differing snapshot or recorded late approval requires review; it does
    not by itself establish misconduct. Missing evidence remains unverified.
    """
    plan = Path(plan)
    content = plan.read_bytes()
    evidence = {}
    missing = []
    for key, value in (("approved_plan", approved_plan),
                       ("approval_record", approval_record),
                       ("analysis_record", analysis_record)):
        if value is None:
            missing.append(key)
        else:
            path = Path(value)
            if not path.read_bytes():
                missing.append(key)
            evidence[key] = str(path.resolve())
    matches = (content == Path(approved_plan).read_bytes()
               if approved_plan is not None else None)
    for key, value in (("approved_at", approved_at),
                       ("analysis_started_at", analysis_started_at)):
        if value is None:
            missing.append(key)
    before = (_recorded_time(approved_at) <= _recorded_time(analysis_started_at)
              if approved_at is not None and analysis_started_at is not None else None)
    issues = []
    if matches is False:
        issues.append("run_plan_differs_from_supplied_approved_snapshot")
    if before is False:
        issues.append("supplied_approval_time_is_after_analysis_start")
    status = "needs_review" if issues else "unverified" if missing else "consistent"
    plan_mtime = plan.stat().st_mtime
    observed = [{"path": str(Path(path).resolve()),
                 "mtime": Path(path).stat().st_mtime,
                 "plan_mtime_is_later": plan_mtime > Path(path).stat().st_mtime}
                for path in outputs]
    return {"status": status, "plan": str(plan.resolve()),
            "approved_snapshot_matches": matches,
            "recorded_approval_before_analysis": before,
            "approved_at": approved_at, "analysis_started_at": analysis_started_at,
            "evidence": evidence, "missing_evidence": missing, "issues": issues,
            "plan_mtime": plan_mtime, "output_mtime_observations": observed,
            "scope": "Consistency of supplied records only. Inspect sources for actual approval; mtime is not proof."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--approved-plan", type=Path)
    parser.add_argument("--approval-record", type=Path)
    parser.add_argument("--analysis-record", type=Path)
    parser.add_argument("--approved-at")
    parser.add_argument("--analysis-started-at")
    parser.add_argument("--outputs", type=Path, nargs="*", default=[])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = check_plan_provenance(
        args.plan, approved_plan=args.approved_plan,
        approval_record=args.approval_record, analysis_record=args.analysis_record,
        approved_at=args.approved_at, analysis_started_at=args.analysis_started_at,
        outputs=args.outputs)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
