"""Build the EEGLAB plugin ZIP; no models, datasets or study outputs are included."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
from zipfile import ZipFile, ZIP_DEFLATED


def build_archive(root: Path, output: Path):
    source = root / "extensions/eeglab/aea"
    text = (source / "eegplugin_aea.m").read_text(encoding="utf-8-sig")
    version = re.search(r"vers = 'aea([^']+)'", text)[1]
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(source.iterdir()):
            if path.is_file():
                archive.write(path, f"aea{version}/{path.name}")
        archive.write(root / "LICENSE", f"aea{version}/LICENSE")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(build_archive(Path(__file__).resolve().parents[1], args.output))


if __name__ == "__main__":
    main()
