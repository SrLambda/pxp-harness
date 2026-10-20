"""Interfaz de terminal de PXP Harness."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from .project import (
    MODES,
    ProjectError,
    initialize,
    load_config,
    mode_context,
    set_mode,
)
from .prompts import (
    MODEL_INSTRUCTIONS,
    clear_prompt,
    load_prompt,
    set_prompt,
)
from .standards import (
    configure,
    load_standards,
    run_checks,
)


def _parser() -> argparse.ArgumentParser:
    """Define los argumentos de terminal."""
    parser = argparse.ArgumentParser(
        prog="pxp",
        description=(
            "Project context and mode "
            "launcher for Codex CLI"
        ),
    )
    subparsers = parser.add_subparsers(
        dest="command", required=True
    )
    subparsers.add_parser(
        "init",
        help=(
            "initialize PXP config and"
            " artifact files in this "
            "directory"
        ),
    )
    mode_parser = subparsers.add_parser(
        "mode",
        help=(
            "show available modes or "
            "select one by ID"
        ),
    )
    mode_parser.add_argument(
        "mode_id",
        nargs="?",
        help="mode ID to activate",
    )
    chat_parser = subparsers.add_parser(
        "chat",
        help=(
            "start Codex CLI with this"
            " project's mode and "
            "artifacts"
        ),
    )
    chat_parser.add_argument(
        "prompt",
        nargs="*",
        help="initial request for Codex",
    )
    standards = subparsers.add_parser(
        "standards",
        help="manage coding standards",
    )
    standards.add_argument(
        "action",
        nargs="?",
        default="show",
        choices=[
            "show",
            "configure",
            "check",
            "apply",
        ],
    )
    standards.add_argument("--profile")
    standards.add_argument(
        "--line-length", type=int
    )
    standards.add_argument(
        "--doc-language", choices=["es", "en"]
    )
    prompts = subparsers.add_parser(
        "prompt", help="manage base instructions"
    )
    actions = prompts.add_subparsers(
        dest="prompt_action", required=True
    )
    show = actions.add_parser("show")
    show.add_argument("mode_id", nargs="?")
    select = actions.add_parser("set")
    select.add_argument("mode_id")
    select.add_argument("path")
    clear = actions.add_parser("clear")
    clear.add_argument("mode_id")
    return parser


def _show_modes(active_id: str) -> None:
    """Muestra los modos disponibles."""
    for mode in MODES:
        marker = (
            "*"
            if mode["id"] == active_id
            else " "
        )
        print(
            f"{marker} {mode['id']:<26} "
            f"{mode['label']}"
        )


def _chat(root: Path, prompt: str) -> int:
    """Inicia Codex con contexto local."""
    config = load_config(root)
    active, artifact_paths = mode_context(
        root, config
    )
    settings = load_standards(root)
    base_prompt = load_prompt(root, active["id"])
    executable = shutil.which("codex")
    if executable is None:
        print(
            (
                "Codex CLI was not found. "
                "Install it and ensure "
                "`codex` is on PATH, then "
                "retry."
            ),
            file=sys.stderr,
        )
        return 1
    request = prompt or (
        "Help me continue this "
        "project in the selected "
        "PXP mode."
    )
    context = "\n".join(
        f"- {path}" for path in artifact_paths
    )
    full_prompt = (
        "You are working in a PXP Harness "
        "project. Use the selected mode and "
        "project artifacts as context.\n"
        f"Active mode: {active['id']} "
        f"({active['label']})\n"
        "Read these project-local artifacts "
        "when relevant; do not assume they "
        "contain content if empty:\n"
        f"{context}\n\n"
        "Coding standards (Python): PEP 8; "
        "maximum "
        f"{settings['line_length']} columns; "
        "documentation language: "
        f"{settings['doc_language']}; "
        f"profile: {settings['profile']}.\n"
        f"User request: {request}"
    )
    command = [executable]
    if base_prompt is not None:
        encoded = json.dumps(
            str(base_prompt), ensure_ascii=False
        )
        command.extend(
            [
                "-c",
                MODEL_INSTRUCTIONS
                + "="
                + encoded,
            ]
        )
    command.append(full_prompt)
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            check=False,
        )
    except OSError as exc:
        print(
            f"Could not launch Codex CLI: {exc}",
            file=sys.stderr,
        )
        return 1
    return completed.returncode


def main(
    argv: list[str] | None = None,
    *,
    cwd: Path | None = None,
) -> int:
    """Ejecuta la operación solicitada."""
    args = _parser().parse_args(argv)
    root = (cwd or Path.cwd()).resolve()
    try:
        if args.command == "init":
            created = initialize(root)
            print(
                f"PXP initialized in {root}"
                if created
                else (
                    "PXP is already "
                    "initialized in "
                    f"{root}"
                )
            )
            print("Artifacts: .pxp/artifacts/")
            return 0
        if args.command == "mode":
            config = load_config(root)
            if args.mode_id:
                set_mode(root, args.mode_id)
                print(
                    f"Active mode: {args.mode_id}"
                )
            else:
                _show_modes(
                    config.get(
                        "active_mode", "plan"
                    )
                )
            return 0
        if args.command == "prompt":
            if args.prompt_action == "set":
                set_prompt(
                    root, args.mode_id, args.path
                )
                print("Base prompt configured.")
            elif args.prompt_action == "clear":
                clear_prompt(root, args.mode_id)
                print("Base prompt cleared.")
            else:
                config = load_config(root)
                mode = args.mode_id
                if mode is None:
                    mode = config.get(
                        "active_mode", "plan"
                    )
                path = load_prompt(root, mode)
                value = (
                    path.relative_to(
                        root
                    ).as_posix()
                    if path is not None
                    else None
                )
                details = {
                    "mode": mode,
                    MODEL_INSTRUCTIONS: value,
                }
                print(
                    json.dumps(
                        details,
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            return 0
        if args.command == "standards":
            overrides = (
                args.profile is not None
                or args.line_length is not None
                or args.doc_language is not None
            )
            if (
                args.action != "configure"
                and overrides
            ):
                raise ProjectError(
                    (
                        "Overrides require "
                        "configure."
                    )
                )
            if args.action == "configure":
                configure(
                    root,
                    (
                        args.profile
                        if args.profile
                        is not None
                        else "default"
                    ),
                    args.line_length,
                    args.doc_language,
                )
            if args.action in {
                "show",
                "configure",
            }:
                print(
                    json.dumps(
                        load_standards(root),
                        indent=2,
                    )
                )
                return 0
            return run_checks(
                root, apply=args.action == "apply"
            )
        if args.command == "chat":
            return _chat(
                root, " ".join(args.prompt)
            )
    except ProjectError as exc:
        print(str(exc), file=sys.stderr)
        return (
            1
            if args.command != "mode"
            or args.mode_id is None
            else 2
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
