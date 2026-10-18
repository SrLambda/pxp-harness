# PXP Harness

PXP Harness is a small Python CLI that adds repeatable project modes and artifact context around an existing Codex CLI installation. It runs locally in the project directory; it does not provide an AI model, store credentials, or change UNIX permissions.

## Quick start

From a cloned PXP Harness repository:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
pxp init
pxp mode
pxp mode implementation-code
pxp chat "Implement the next task"
```

Install or authenticate Codex CLI separately using its official instructions. PXP invokes the `codex` executable already available on `PATH`; it does not need an OpenAI API key of its own. If Codex is unavailable, `pxp chat` reports how to proceed.

## Modes

Mode IDs are stable, machine-friendly selectors. Labels keep the nine requested PXP stages distinct:

| Mode ID | Label | Group |
|---|---|---|
| `plan` | General plan | General |
| `design` | General design | General |
| `iteration-initialization` | Iteration initialization | Iteration |
| `iteration-design` | Iteration design | Iteration |
| `implementation-tests` | Implementation tests | Implementation |
| `implementation-code` | Implementation code | Implementation |
| `implementation-refactor` | Implementation refactor | Implementation |
| `system-tests` | System tests | Validation |
| `retrospective` | Retrospective | Iteration |

Run `pxp mode` to list the modes and mark the active one. Run `pxp mode <mode-id>` to change it.

## Project context

`pxp init` creates `.pxp/config.json` and these starter files:

| Artifact | File |
|---|---|
| Requirements | `.pxp/artifacts/requirements.md` |
| Rules | `.pxp/artifacts/rules.md` |
| Architecture design | `.pxp/artifacts/architecture-design.md` |
| Mockups | `.pxp/artifacts/mockups.md` |
| Data model | `.pxp/artifacts/data-model.md` |

Initialization is safe to repeat: it adds missing files but preserves existing configuration and artifact contents. Keep the files that are useful to the project under version control. `pxp chat` passes Codex a prompt naming the active mode and all five artifact paths, then starts Codex with the project as its working directory.

## Remote terminal workflow

The MVP has no terminal UI or background server. Its plain CLI and project-local JSON/Markdown files are intentionally usable over a normal SSH terminal, including Termux: connect to the Debian VM, enter the project directory, and run the same `pxp` commands. A future remote TUI can call the CLI and read/write the same local project state without introducing a new state service. Use a stable SSH setup and keep the project repository as the source of truth.

## Permissions and security boundary

This MVP never runs `sudo`, changes ownership, or grants elevated permissions. It uses the current user's access to the project directory. UNIX user/group separation is future work and should be designed explicitly before adding permission-management commands. Do not place credentials, access tokens, or personal data in the public repository or its artifacts.

## Development

Run the standard-library test suite from the repository root:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```
