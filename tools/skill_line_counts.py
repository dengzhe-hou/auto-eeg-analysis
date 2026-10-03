"""Print actual SKILL.md line counts so the README table can't silently drift.

  python tools/skill_line_counts.py            # markdown table of counts
  python tools/skill_line_counts.py --check     # nonzero exit if README total is off by >5%

The README's per-skill "Lines" column and "~N,NNN lines" headline are hand-maintained;
run this after editing skills and paste the table / fix the headline.
"""
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def counts():
    rows = {}
    for f in sorted(ROOT.glob("skills/*/SKILL.md")):
        rows[f.parent.name] = sum(1 for _ in f.open(encoding="utf-8-sig"))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    rows = counts()
    total = sum(rows.values())
    for name, n in rows.items():
        print(f"| `{name}` | {n} |")
    print(f"\nTotal: {total} lines across {len(rows)} skills")

    if args.check:
        readme = (ROOT / "README.md").read_text(encoding="utf-8-sig")
        m = re.search(r"~([\d,]+)\s+lines", readme)
        if not m:
            raise SystemExit("README headline '~N lines' not found")
        claimed = int(m.group(1).replace(",", ""))
        drift = abs(claimed - total) / total
        print(f"README claims ~{claimed}; actual {total}; drift {drift:.1%}")
        if drift > 0.05:
            raise SystemExit(f"README line headline off by {drift:.1%} (>5%) — update it")


if __name__ == "__main__":
    main()
