# `.codex` Directory and File Roles

This document explains the directories and files currently present under `/root/.codex` based on the actual local structure checked on `2026-04-09`.

## Overview

`/root/.codex` is the local working directory used by the Codex CLI/runtime. It stores:

- configuration
- authentication and trust state
- session and prompt history
- runtime logs
- local SQLite state databases
- cached model and tool metadata
- built-in skills
- temporary plugin and shell snapshot artifacts

It is a runtime data directory, not a normal project source directory.

## Top-level entries

### `/root/.codex/config.toml`

- Stores local Codex configuration.
- In this environment it contains project trust information for `/root`.
- Example role: whether a directory is treated as trusted by the CLI.

### `/root/.codex/auth.json`

- Stores authentication-related local state.
- Likely contains tokens, account/session metadata, or provider auth data.
- This is sensitive and should not be committed, shared, or printed casually.

### `/root/.codex/version.json`

- Stores version check state for the CLI.
- Current observed fields:
  - `latest_version`
  - `last_checked_at`
  - `dismissed_version`
- Role: remember update-check results without checking every time.

### `/root/.codex/models_cache.json`

- Cache for model-related metadata.
- Likely includes model availability, cached descriptors, or provider-facing capabilities.
- Role: reduce repeated model discovery/lookups.

### `/root/.codex/history.jsonl`

- Lightweight line-based prompt history.
- Each line is a JSON object with fields like `session_id`, `ts`, and `text`.
- Role: quick history of user-entered messages across sessions.

### `/root/.codex/state_5.sqlite`

- Main SQLite state database used by Codex locally.
- Likely stores structured runtime/session/app state that is better suited to relational storage than JSONL files.

### `/root/.codex/state_5.sqlite-shm`

- SQLite shared-memory sidecar for `state_5.sqlite`.
- Created automatically by SQLite in WAL mode.

### `/root/.codex/state_5.sqlite-wal`

- SQLite write-ahead log sidecar for `state_5.sqlite`.
- Holds recent transactional writes before checkpointing back into the main DB.

### `/root/.codex/logs_1.sqlite`

- SQLite database for structured logs or event records.
- Separate from the plain text log file.

### `/root/.codex/logs_1.sqlite-shm`

- SQLite shared-memory sidecar for `logs_1.sqlite`.

### `/root/.codex/logs_1.sqlite-wal`

- SQLite WAL sidecar for `logs_1.sqlite`.

### `/root/.codex/.personality_migration`

- Small internal marker file.
- Likely used to note that a one-time migration related to assistant/personality settings has already been applied.

## Directories

### `/root/.codex/log`

- Plain log directory.
- Currently contains `codex-tui.log`.
- Role: human-readable runtime log output from the terminal UI.

### `/root/.codex/memories`

- Directory reserved for memory artifacts.
- Currently empty in this environment.
- Role: long-lived memory/state items when that feature is used.

### `/root/.codex/cache`

- Cache directory for reusable tool/app metadata.
- Current subdirectory:
  - `codex_apps_tools`
- Current observed file:
  - hashed JSON cache entry
- Role: avoid recomputing or re-fetching app/tool descriptions repeatedly.

### `/root/.codex/sessions`

- Stores session transcripts by date hierarchy.
- Current layout pattern:
  - `sessions/YYYY/MM/DD/rollout-<timestamp>-<session-id>.jsonl`
- Role: detailed per-session event log, richer than `history.jsonl`.
- These files may contain prompts, tool calls, outputs, metadata, and instructions.

### `/root/.codex/shell_snapshots`

- Stores shell snapshot scripts.
- Current observed file name looks like a UUID/timestamp-based `.sh` file.
- Role: preserve shell context or reproducible shell state for a rollout/session.

### `/root/.codex/skills`

- Stores Codex skills.
- Current content is under `.system`, which indicates built-in/system-provided skills.
- Observed built-in skills:
  - `imagegen`
  - `openai-docs`
  - `plugin-creator`
  - `skill-creator`
  - `skill-installer`
- Each skill typically includes a `SKILL.md`, and some include license files.
- Role: inject specialized instructions/workflows on demand.

### `/root/.codex/tmp`

- General temporary working directory for Codex runtime tasks.
- Current observed structure:
  - `tmp/arg0/codex-arg0.../.lock`
- Role: transient lock files and scratch runtime artifacts.

### `/root/.codex/.tmp`

- Hidden temporary/runtime workspace.
- More tool-internal than `tmp`.
- Current observed content shows plugin sync and plugin checkout material.
- Likely safe to treat as disposable runtime cache rather than durable user content.

## Important nested areas

### `/root/.codex/cache/codex_apps_tools`

- Contains cached JSON files keyed by hashes.
- Role: cached metadata for app/tool integrations.

### `/root/.codex/sessions/2026/04/08` and `/root/.codex/sessions/2026/04/09`

- Date-partitioned session transcript directories.
- Each `rollout-*.jsonl` file is a full event stream for one Codex session.

### `/root/.codex/skills/.system`

- Marker and built-in skill packages live here.
- Observed marker:
  - `.codex-system-skills.marker`
- Role: distinguish system-managed skills from user-installed/custom ones.

### `/root/.codex/.tmp/plugins`

- Temporary plugin repository checkout/worktree.
- Contains:
  - `.git`
  - `.agents`
  - `plugins`
  - `README.md`
  - `.gitignore`
  - `plugins.sha`
- Role: local synced copy of plugin assets/definitions used by Codex.

### `/root/.codex/.tmp/plugins/.agents`

- Support files for plugin-side agents/skills.
- Observed entries:
  - `plugins/marketplace.json`
  - `skills/plugin-creator`
- Role: expose plugin marketplace and plugin-related agent resources.

### `/root/.codex/.tmp/plugins/plugins`

- Contains many plugin packages such as:
  - `figma`
  - `github`
  - `gmail`
  - `cloudflare`
  - `vercel`
  - `notion`
  - `slack`
  - `build-web-apps`
  - `build-macos-apps`
  - `test-android-apps`
- Inside each plugin, common files/directories include:
  - `.codex-plugin`
  - `.app.json`
  - `.mcp.json`
  - `README.md`
  - `assets`
  - `skills`
  - `agents`
  - `commands`
  - `scripts`
  - `plugin.lock.json`
- Role: plugin definitions and resources that expand Codex capabilities.

## File type meaning

### `*.jsonl`

- JSON Lines format.
- Usually used for append-only logs, transcripts, or event streams.

### `*.sqlite`

- SQLite database.
- Used for structured local state and logs.

### `*.sqlite-wal`, `*.sqlite-shm`

- Automatic SQLite sidecar files for WAL mode.
- Do not edit manually.

### `*.toml`

- Human-readable configuration file format.

### `*.md`

- Documentation/instruction files.
- In skills, `SKILL.md` defines how the skill should be used.

### `*.sh`

- Shell script or shell snapshot artifact.

### `.lock`

- Lock file used to prevent concurrent access or conflicting temp operations.

## Operational notes

- `auth.json` is sensitive.
- `sessions`, `history.jsonl`, and `log/codex-tui.log` may contain prompts, commands, tool outputs, and other activity records.
- `state_5.sqlite` and `logs_1.sqlite` should be treated as application-managed files.
- `tmp` and `.tmp` are mainly runtime scratch areas and may be regenerated.
- `skills/.system` appears system-managed, so manual edits there are usually a bad idea unless you know the runtime behavior.
- `.tmp/plugins` also looks runtime-managed and may be refreshed by Codex/plugin sync.

## Practical summary

If you classify the current `.codex` tree by purpose, it looks like this:

- Config and trust:
  - `config.toml`
  - `version.json`
  - `.personality_migration`
- Sensitive auth:
  - `auth.json`
- Session/history records:
  - `history.jsonl`
  - `sessions/`
  - `shell_snapshots/`
- Logs:
  - `log/`
  - `logs_1.sqlite*`
- Structured runtime state:
  - `state_5.sqlite*`
- Cached metadata:
  - `cache/`
  - `models_cache.json`
- Skills and extensions:
  - `skills/`
  - `.tmp/plugins/`
- Temporary runtime workspace:
  - `tmp/`
  - `.tmp/`
  - `memories/`

## Limitations

- This explanation is based on observed file names, directory structure, and a few non-sensitive file formats.
- I did not dump sensitive file contents such as `auth.json`.
- Some internal meanings are inferred from standard Codex/CLI naming conventions rather than official internal schema documentation.
