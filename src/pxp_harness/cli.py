"""Interfaz de terminal de PXP Harness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import memory
from .agents import AgentStrategy, LaunchRequest
from .codex import CodexStrategy
from .editor import open_prompt
from .mcp import (
    AddMCP,
    MCPServer,
    RemoveMCP,
    selected,
)
from .project import (
    ProjectError,
    get_workflow,
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
from .repository import (
    ensure_git,
    find_project_root,
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
    init_parser = subparsers.add_parser(
        "init",
        help=(
            "initialize PXP config and"
            " artifact files in this "
            "directory"
        ),
    )
    init_parser.add_argument(
        "--git",
        action="store_true",
        help="initialize Git if needed",
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
    for action in ("edit", "view"):
        editor = actions.add_parser(action)
        editor.add_argument("mode_id", nargs="?")
    clear = actions.add_parser("clear")
    clear.add_argument("mode_id")
    memories = subparsers.add_parser("memory")
    memories.add_argument(
        "action",
        nargs="?",
        default="show",
        choices=["show", "enable", "disable"],
    )
    memories.add_argument("--executable")
    mcps = subparsers.add_parser("mcp")
    commands = mcps.add_subparsers(
        dest="mcp_action", required=True
    )
    add = commands.add_parser("add")
    add.add_argument("mode_id")
    add.add_argument("name")
    add.add_argument(
        "--command",
        dest="server_command",
        required=True,
    )
    add.add_argument(
        "--arg", action="append", default=[]
    )
    add.add_argument(
        "--env-var", action="append", default=[]
    )
    remove = commands.add_parser("remove")
    remove.add_argument("mode_id")
    remove.add_argument("name")
    listing = commands.add_parser("list")
    listing.add_argument("mode_id", nargs="?")
    return parser


def _show_modes(config) -> None:
    """Muestra los modos disponibles."""
    active_id = config.get("active_mode", "plan")
    for item in get_workflow(config).modes:
        mode = item.as_dict()
        marker = (
            "*"
            if mode["id"] == active_id
            else " "
        )
        print(
            f"{marker} {mode['id']:<26} "
            f"{mode['label']}"
        )


def _chat(root, prompt, strategy=None) -> int:
    """Inicia Codex con contexto local."""
    config = load_config(root)
    active, artifact_paths = mode_context(
        root, config
    )
    settings = load_standards(root)
    base_prompt = load_prompt(root, active["id"])
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
    )
    servers, notes = memory.integration(root)
    servers += selected(root, active["id"])
    return (strategy or CodexStrategy()).launch(
        LaunchRequest(
            root,
            full_prompt.rstrip(),
            request,
            base_prompt,
            servers,
            notes,
        )
    )


def main(
    argv: list[str] | None = None,
    *,
    cwd: Path | None = None,
    strategy: AgentStrategy | None = None,
) -> int:
    """Ejecuta la operación solicitada."""
    args = _parser().parse_args(argv)
    try:
        root = find_project_root(
            (cwd or Path.cwd()).resolve()
        )
        if args.command == "init":
            if args.git:
                ensure_git(root)
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
        if args.command == "mcp":
            if args.mcp_action == "add":
                AddMCP(
                    args.mode_id,
                    MCPServer(
                        args.name,
                        args.server_command,
                        tuple(args.arg),
                        tuple(args.env_var),
                    ),
                ).execute(root)
            elif args.mcp_action == "remove":
                RemoveMCP(
                    args.mode_id, args.name
                ).execute(root)
            else:
                config = load_config(root)
                mode = args.mode_id or config.get(
                    "active_mode", "plan"
                )
                declarations = {}
                for spec in selected(root, mode):
                    declarations[spec.name] = (
                        spec.declaration()
                    )
                print(json.dumps(declarations))
            return 0
        if args.command == "memory":
            if args.action != "show":
                memory.configure(
                    root,
                    args.action == "enable",
                    args.executable,
                )
            print(json.dumps(memory.load(root)))
            return 0
        if args.command == "mode":
            config = load_config(root)
            if args.mode_id:
                set_mode(root, args.mode_id)
                print(
                    f"Active mode: {args.mode_id}"
                )
            else:
                _show_modes(config)
            return 0
        if args.command == "prompt":
            if args.prompt_action in {
                "edit",
                "view",
            }:
                config = load_config(root)
                mode = args.mode_id
                if mode is None:
                    mode = config.get(
                        "active_mode", "plan"
                    )
                return open_prompt(
                    root,
                    mode,
                    readonly=(
                        args.prompt_action
                        == "view"
                    ),
                )
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
                root,
                " ".join(args.prompt),
                strategy,
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
