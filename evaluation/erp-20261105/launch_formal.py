"""Submit the formal sessions. Refuses unless the user-set flags and the public freeze exist."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent


def main():
    auth = json.loads((ROOT / "EXECUTION_AUTHORIZATION.json").read_text())
    if not auth.get("formal_authorized"):
        raise SystemExit("formal_authorized is false: no formal session is submitted")
    frozen = ROOT / "PROTOCOL_FROZEN.json"
    if not frozen.exists() or not json.loads(frozen.read_text()).get("public_archive_url"):
        raise SystemExit("PROTOCOL_FROZEN.json with its public archive link is required first")
    if not (ROOT / "SCHEDULE.json").exists():
        raise SystemExit("SCHEDULE.json is written when the protocol is frozen")
    single = subprocess.run(["sbatch", "--parsable", str(ROOT / "formal-single.sbatch")], check=True, capture_output=True, text=True).stdout.strip()
    group = subprocess.run(["sbatch", "--parsable", str(ROOT / "formal-group.sbatch")], check=True, capture_output=True, text=True).stdout.strip()
    print(json.dumps({"formal_single": single, "formal_group": group}))


if __name__ == "__main__":
    main()
