#!/usr/bin/env python3
"""Link this checkout's skills into Codex and/or Claude Code project discovery paths."""
from __future__ import annotations

import argparse
import errno
import os
import sys
from pathlib import Path


AGENT_DIRS = {"codex": ".agents", "claude": ".claude"}


def install_skills(root: Path, agent: str) -> tuple[int, int]:
    """Preflight all destinations, then create relative directory symlinks."""
    sources = sorted(p.parent for p in (root / "skills").glob("*/SKILL.md") if p.is_file())
    if not sources:
        raise ValueError(f"No skills found under {root / 'skills'}")

    agents = tuple(AGENT_DIRS) if agent == "both" else (agent,)
    pending = []
    unchanged = 0
    conflicts = []
    for name in agents:
        agent_dir = root / AGENT_DIRS[name]
        destination_dir = agent_dir / "skills"
        for directory in (agent_dir, destination_dir):
            if os.path.lexists(directory) and not directory.is_dir():
                conflicts.append(f"{directory}: expected a directory")
        for source in sources:
            destination = destination_dir / source.name
            if not os.path.lexists(destination):
                pending.append((source, destination))
            elif destination.is_symlink() and destination.resolve() == source:
                unchanged += 1
            else:
                conflicts.append(f"{destination}: already exists and is not a link to {source}")

    if conflicts:
        raise ValueError("No links created. Resolve these conflicts manually:\n  "
                         + "\n  ".join(conflicts))

    for source, destination in pending:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to(os.path.relpath(source, destination.parent),
                               target_is_directory=True)
    return len(pending), unchanged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", required=True, choices=("codex", "claude", "both"),
                        help="Client(s) to configure in this checkout")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        created, unchanged = install_skills(root, args.agent)
    except (ValueError, OSError) as exc:
        print(f"Skill installation failed: {exc}", file=sys.stderr)
        if (getattr(exc, "winerror", None) == 1314
                or (os.name == "nt" and isinstance(exc, OSError)
                    and exc.errno in (errno.EACCES, errno.EPERM))):
            print("Windows requires permission to create symbolic links. Enable Developer "
                  "Mode, use a terminal with symlink privileges, or run from WSL.",
                  file=sys.stderr)
        return 1
    print(f"Skills in {root}: created {created} link(s); {unchanged} already installed.")
    print("Restart your agent session in this checkout to discover the skills.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
