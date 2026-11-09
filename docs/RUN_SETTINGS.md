# Run controls and the selected reviewer

Use the same project settings from Codex, Claude Code, EEGLAB or another client.
Read them before chaining stages:

```bash
python tools/run_settings.py --project projects/my-study
```

Selection order is an explicit `--config path`, the project's `AEA_RUN.json`,
then an existing `~/.claude/checkpoint.json`. The last path supports current
installations; new projects can use `AEA_RUN.json` without a Claude directory.
An explicitly named missing or malformed file fails clearly. The loader reports
the actual source and preserves `gates`. With no file, the previous run controls
remain `auto_proceed: true`, `timeout_seconds: 300`, and no configured reviewer.
An explicit relative path is resolved from the command's working directory.

This example illustrates an existing Codex review route; use its model/effort
only when already approved. It does not authorize a paid call:

```json
{
  "auto_proceed": true,
  "timeout_seconds": 300,
  "gates": {},
  "reviewer": {"transport": "codex-cli", "model": "gpt-6-astra", "effort": "max"}
}
```

`reviewer.transport` can select the supported `codex-cli`, existing `codex` MCP,
or configured `llm-chat` connection. Save the actual approved model and optional
effort; credentials belong in the chosen client's existing setup, not this file.
An approval already given in the session can be recorded here without asking
again. Configuring a target is distinct from authorizing its use.

Save the loader result as `run_controls` in `PIPELINE_STATE.json`, pass the
selected reviewer to `eeg-audit`, and retain it with the run. The orchestration
client applies those controls; the loader itself neither launches a pipeline
nor calls a reviewer.

For programmatic use, call `load_run_settings(project_dir, config_path=...)`.
Before a review, `select_reviewer(settings, available_transports=...)` checks
the recorded target against connections the caller actually found. It never
chooses a model or fallback. A missing selected transport means the review is
incomplete; an unrelated unavailable MCP server does not block a selected CLI.
Discovery does not establish authentication, model access, a running process or
a passing verdict. Keep the real execution logs and response validation.

`auto_proceed`, gates and timeouts control already authorized work. They cannot
approve an unresolved scientific method, exclusion, new experiment, model
switch or additional spending. Keep unresolved work and failed reviews visible.
