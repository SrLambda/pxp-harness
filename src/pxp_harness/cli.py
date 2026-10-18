"""Command-line interface for PXP Harness."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from .project import MODES, ProjectError, initialize, load_config, mode_context, set_mode


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pxp", description="Project context and mode launcher for Codex CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="initialize PXP config and artifact files in this directory")
    mode_parser = subparsers.add_parser("mode", help="show available modes or select one by ID")
    mode_parser.add_argument("mode_id", nargs="?", help="mode ID to activate")
    chat_parser = subparsers.add_parser("chat", help="start Codex CLI with this project's mode and artifacts")
    chat_parser.add_argument("prompt", nargs="*", help="initial request for Codex")
    return parser


def _show_modes(active_id: str) -> None:
    for mode in MODES:
        marker = "*" if mode["id"] == active_id else " "
        print(f"{marker} {mode['id']:<26} {mode['label']}")


def _chat(root: Path, prompt: str) -> int:
    config = load_config(root)
    active, artifact_paths = mode_context(root, config)
    executable = shutil.which("codex")
    if executable is None:
        print("Codex CLI was not found. Install it and ensure `codex` is on PATH, then retry.", file=sys.stderr)
        return 1
    request = prompt or "Help me continue this project in the selected PXP mode."
    context = "\n".join(f"- {path}" for path in artifact_paths)
    full_prompt = (
        "You are working in a PXP Harness project. Use the selected mode and project artifacts as context.\n"
        f"Active mode: {active['id']} ({active['label']})\n"
        "Read these project-local artifacts when relevant; do not assume they contain content if empty:\n"
        f"{context}\n\n"
        f"User request: {request}"
    )
    try:
        completed = subprocess.run([executable, full_prompt], cwd=root, check=False)
    except OSError as exc:
        print(f"Could not launch Codex CLI: {exc}", file=sys.stderr)
        return 1
    return completed.returncode


def main(argv: list[str] | None = None, *, cwd: Path | None = None) -> int:
    args = _parser().parse_args(argv)
    root = (cwd or Path.cwd()).resolve()
    try:
        if args.command == "init":
            created = initialize(root)
            print(f"PXP initialized in {root}" if created else f"PXP is already initialized in {root}")
            print("Artifacts: .pxp/artifacts/")
            return 0
        if args.command == "mode":
            config = load_config(root)
            if args.mode_id:
                set_mode(root, args.mode_id)
                print(f"Active mode: {args.mode_id}")
            else:
                _show_modes(config.get("active_mode", "plan"))
            return 0
        if args.command == "chat":
            return _chat(root, " ".join(args.prompt))
    except ProjectError as exc:
        print(str(exc), file=sys.stderr)
        return 1 if args.command != "mode" or args.mode_id is None else 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
