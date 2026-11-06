"""Read AEA run controls without tying the analysis client to one vendor."""
import argparse
import json
from pathlib import Path


def load_run_settings(project_dir, *, config_path=None):
    """Explicit file, project AEA_RUN.json, existing legacy file, then run controls.

    These settings control already authorized execution. They cannot approve a
    scientific choice, model switch, paid call, or new experiment.
    """
    project = Path(project_dir).resolve()
    if config_path is not None:
        path = Path(config_path).resolve()
    elif (project / "AEA_RUN.json").is_file():
        path = project / "AEA_RUN.json"
    elif (Path.home() / ".claude/checkpoint.json").is_file():
        path = Path.home() / ".claude/checkpoint.json"
    else:
        path = None
    settings = json.loads(path.read_text()) if path is not None else {}
    auto = settings.get("auto_proceed", True)
    timeout = settings.get("timeout_seconds", 300)
    if not isinstance(auto, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ValueError("Run controls need boolean auto_proceed and positive timeout_seconds")
    return {"source": str(path) if path is not None else None,
            "auto_proceed": auto, "timeout_seconds": timeout,
            "gates": settings.get("gates", {}), "reviewer": settings.get("reviewer")}


def select_reviewer(settings, *, available_transports):
    """Check the explicitly selected transport/model; never choose a fallback.

    Caller supplies transports it actually found. Discovery is not evidence of
    authentication, model access, execution or a successful review.
    """
    reviewer = settings["reviewer"]
    if not reviewer or not reviewer.get("model"):
        raise ValueError("Record the already approved reviewer connection and model before launching it")
    transport = reviewer["transport"]
    if transport not in ("codex-cli", "codex", "llm-chat"):
        raise ValueError("Unsupported reviewer transport; configure an existing supported connection")
    if transport not in available_transports:
        raise RuntimeError(f"Selected reviewer transport {transport!r} is unavailable; review is incomplete")
    return dict(reviewer)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    print(json.dumps(load_run_settings(args.project, config_path=args.config), indent=2))


if __name__ == "__main__":
    main()
