"""Refresh the packaging resource list from tracked AEA files."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    "AGENT_GUIDE.md", "CHANGELOG.md", "CITATION.cff", "CONTRIBUTING.md",
    "LICENSE", "README.md", "README.ja.md", "README.zh-CN.md",
    "RESOURCE_INDEX.md", "environment.yml",
}


def included(name):
    parts = name.split("/")
    if "tests" in parts:
        return False
    if name in ROOT_FILES or parts[0] in {"skills", "recipes", "templates", "extensions", "tools"}:
        return True
    return parts[0] == "docs" and (name.endswith(".md") or name.startswith("docs/assets/eeglab/") or name in {"docs/assets/n400-example.png", "docs/assets/library-overview.svg"})


def main():
    names = subprocess.check_output(["git", "-C", str(ROOT), "ls-files", "-z"]).decode().split("\0")
    names = sorted(name for name in names if name and included(name))
    (ROOT / "packaging" / "RESOURCE_FILES.txt").write_text("\n".join(names) + "\n", encoding="utf-8")
    manifest = ["include packaging/README.md", "include packaging/RESOURCE_FILES.txt", "include packaging/update_resource_manifest.py"]
    (ROOT / "MANIFEST.in").write_text("\n".join(manifest + ["include " + name for name in names]) + "\n", encoding="utf-8")
    print(f"Listed {len(names)} resource files")


if __name__ == "__main__":
    main()
