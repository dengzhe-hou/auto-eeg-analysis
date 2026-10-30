"""Fetch only the fifteen EDF files used by the recipe validation."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from urllib.request import urlopen


BASE = "https://physionet.org/files/eegmmidb/1.0.0"
CONFIG = json.loads((Path(__file__).parent / "config.json").read_text())


def fetch(item):
    subject, run, destination = item
    name = f"S{subject:03d}R{run:02d}.edf"
    path = destination / f"S{subject:03d}" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path.stat().st_size
    with urlopen(f"{BASE}/S{subject:03d}/{name}", timeout=120) as response:
        content = response.read(6_000_001)
    assert len(content) <= 6_000_000, "Unexpected file size; inspect the data source."
    temporary = path.with_suffix(".part")
    temporary.write_bytes(content)
    temporary.replace(path)
    print(name, len(content), flush=True)
    return len(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    args = parser.parse_args()
    items = [(s, r, args.data) for s in CONFIG["subjects"] for r in CONFIG["runs"]]
    with ThreadPoolExecutor(max_workers=4) as pool:
        sizes = list(pool.map(fetch, items))
    assert sum(sizes) < 100_000_000
    print(json.dumps({"files": len(sizes), "bytes": sum(sizes)}), flush=True)


if __name__ == "__main__":
    main()
