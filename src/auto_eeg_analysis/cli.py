"""Copy the bundled AEA library into a new analysis project."""
import argparse
from pathlib import Path
import runpy
import shutil

from . import SOURCE_COMMIT, __version__


def resource_root():
    root = Path(__file__).parent / "resources"
    if not (root / "RESOURCE_INDEX.md").is_file():
        raise FileNotFoundError("AEA resources are missing. Install the built wheel or source distribution.")
    return root


def initialize(target, agent):
    target = Path(target).expanduser().resolve()
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise FileExistsError(f"The destination must be a new or empty directory: {target}")
    shutil.copytree(resource_root(), target, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"))
    created = unchanged = 0
    if agent:
        installer = runpy.run_path(str(target / "tools" / "install_skills.py"))
        created, unchanged = installer["install_skills"](target, agent)
    return target, created, unchanged


def main(argv=None):
    parser = argparse.ArgumentParser(description="Create a project containing the AEA EEG analysis library.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__} (resources {SOURCE_COMMIT})")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("path", help="Print the installed resource directory.")
    init = commands.add_parser("init", help="Copy resources to a new or empty project directory.")
    init.add_argument("directory", type=Path)
    init.add_argument("--agent", choices=("codex", "claude", "both"), help="Create project-local skill links using the existing installer.")
    args = parser.parse_args(argv)
    if args.command == "path":
        print(resource_root())
    else:
        try:
            target, created, unchanged = initialize(args.directory, args.agent)
        except FileExistsError as exc:
            parser.exit(2, f"{exc}\n")
        print(f"Created AEA project at {target}")
        if args.agent:
            print(f"Skill links created {created}, unchanged {unchanged}")
        print("Read AGENT_GUIDE.md and approve a study-specific analysis plan before analysis.")
    return 0
