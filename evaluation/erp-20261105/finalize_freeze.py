"""Turn the draft into the frozen protocol once a public archive exists. It starts nothing."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--public-archive-url', required=True)
    a = ap.parse_args()
    if (ROOT / 'PROTOCOL_FROZEN.json').exists():
        raise SystemExit('Protocol already frozen')
    draft = json.loads((ROOT / 'PROTOCOL_FROZEN.draft.json').read_text())
    snapshot = ROOT / 'controller_snapshot'
    snapshot.mkdir()
    for source in ROOT.glob('*.py'):
        shutil.copy2(source, snapshot / source.name)
    schedule = json.loads((ROOT / 'SCHEDULE.proposed.json').read_text())
    schedule['status'] = 'frozen_fixed_assignments'
    (ROOT / 'SCHEDULE.json').write_text(json.dumps(schedule, indent=1) + '\n')
    draft.update(status='frozen', public_archive_url=a.public_archive_url, frozen_at_utc=datetime.now(timezone.utc).isoformat())
    (ROOT / 'PROTOCOL_FROZEN.json').write_text(json.dumps(draft, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({'protocol_frozen': True, 'formal_authorized_unchanged': json.loads((ROOT / 'EXECUTION_AUTHORIZATION.json').read_text())['formal_authorized']}))


if __name__ == '__main__':
    main()
