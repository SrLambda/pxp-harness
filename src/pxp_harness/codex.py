"""Adaptador nativo de Codex; único serializer."""

import hashlib
import json
import os
import shutil
import subprocess
import sys

from .errors import ProjectError


def encode(value):
    """Representa solo tipos TOML conocidos."""
    if isinstance(value, dict):
        return (
            "{ "
            + ", ".join(
                key + " = " + encode(item)
                for key, item in value.items()
            )
            + " }"
        )
    return json.dumps(value, ensure_ascii=False)


def options(root, servers, notes=()):
    """Serializa MCP para Codex."""
    result = []
    names = set()
    suffix = hashlib.sha256(
        str(root).encode()
    ).hexdigest()[:12]
    for server in servers:
        if server.name in names:
            raise ProjectError(
                "Duplicate MCP name; remove or "
                "rename the mode binding."
            )
        names.add(server.name)
        server.validate_executable()
        prefix = (
            f"mcp_servers.pxp_{server.name}_"
            f"{suffix}."
        )
        settings = {
            "command": server.command,
            "args": list(server.args),
            "env_vars": list(server.env_vars),
            "env": dict(server.env),
            "cwd": str(root),
            "enabled": True,
            "required": True,
        }
        for key, value in settings.items():
            result += [
                "-c",
                prefix
                + key
                + "="
                + encode(value),
            ]
    if notes:
        result += [
            "-c",
            "developer_instructions="
            + encode("\n".join(notes)),
        ]
    return result


class CodexStrategy:
    """Conserva la TUI y permisos heredados."""

    def launch(self, request):
        """Inicia sin cambiar ajustes globales."""
        executable = shutil.which("codex")
        if executable is None:
            raise ProjectError(
                "Codex CLI was not found. "
                "Install it and ensure codex "
                "is on PATH, then retry."
            )
        command = [executable]
        command.extend(
            options(
                request.root,
                request.servers,
                request.developer_notes,
            )
        )
        if request.base_prompt is not None:
            command += [
                "-c",
                "model_instructions_file="
                + encode(
                    str(request.base_prompt)
                ),
            ]
        command.append(
            request.context
            + "\nUser request: "
            + request.user_request
        )
        try:
            completed = subprocess.run(
                command,
                cwd=request.root,
                env={
                    **os.environ,
                    "VISUAL": "nvim",
                    "EDITOR": "nvim",
                },
                check=False,
            )
        except OSError as exc:
            message = "Could not launch Codex: "
            print(
                message + str(exc),
                file=sys.stderr,
            )
            return 1
        return completed.returncode


def memory_arguments(root):
    """Permite comprobar opciones de memoria."""
    from .memory import integration

    servers, notes = integration(root)
    return options(root, servers, notes)
