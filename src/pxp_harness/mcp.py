"""Herramientas stdio configuradas por modo."""

import os
import re
from dataclasses import dataclass
from pathlib import Path

from .errors import ProjectError
from .localio import read_json, write_json
from .project import get_workflow, load_config
from .workflows import identifier


def text(value):
    """Rechaza texto inválido para transporte."""
    if not isinstance(value, str):
        raise ProjectError("Expected a string.")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise ProjectError(
            "Invalid Unicode."
        ) from None
    if any(
        ord(c) < 32 or ord(c) == 127
        for c in value
    ):
        raise ProjectError(
            "Control character denied."
        )
    return value


@dataclass(frozen=True)
class MCPServer:
    """Especificación neutral de un servidor."""

    name: str
    command: str
    args: tuple[str, ...] = ()
    env_vars: tuple[str, ...] = ()
    env: tuple[tuple[str, str], ...] = ()

    def __post_init__(self):
        """Valida sin lanzar procesos."""
        identifier(self.name)
        command = text(self.command)
        if (
            not command
            or not Path(command).is_absolute()
        ):
            raise ProjectError(
                "Use an absolute command."
            )
        for values in (
            self.args,
            self.env_vars,
            self.env,
        ):
            if type(values) is not tuple:
                raise ProjectError(
                    "Expected immutable spec."
                )
        for value in self.args:
            text(value)
        for name in self.env_vars:
            if not re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*",
                text(name),
            ):
                raise ProjectError(
                    "Invalid env name."
                )
        for pair in self.env:
            if (
                type(pair) is not tuple
                or len(pair) != 2
            ):
                raise ProjectError(
                    "Invalid internal env."
                )
            if not re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*",
                text(pair[0]),
            ):
                raise ProjectError(
                    "Invalid env name."
                )
            text(pair[1])

    def validate_executable(self):
        """Falla antes de iniciar el agente."""
        path = Path(self.command)
        if not path.is_file() or not os.access(
            path, os.X_OK
        ):
            raise ProjectError(
                "MCP executable unavailable; "
                "configure an installed program."
            )

    def declaration(self):
        """Serializa sin secretos."""
        if self.env:
            raise ProjectError(
                "Internal env is not stored."
            )
        return {
            "command": self.command,
            "args": list(self.args),
            "env_vars": list(self.env_vars),
        }


def _server(name, value):
    """Valida el esquema público."""
    if (
        not isinstance(value, dict)
        or set(value)
        != {"command", "args", "env_vars"}
        or not isinstance(value["args"], list)
        or not isinstance(value["env_vars"], list)
    ):
        raise ProjectError(
            "Invalid MCP declaration."
        )
    return MCPServer(
        name,
        value["command"],
        tuple(value["args"]),
        tuple(value["env_vars"]),
    )


def _read(root):
    """Conserva bindings inactivos."""
    load_config(root)
    data = read_json(
        root,
        ".pxp/mcps.json",
        {
            "schema_version": 1,
            "workflows": {},
        },
    )
    if (
        not isinstance(data, dict)
        or set(data)
        != {"schema_version", "workflows"}
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or not isinstance(data["workflows"], dict)
    ):
        raise ProjectError(
            "Invalid MCP configuration."
        )
    for flow, modes in data["workflows"].items():
        identifier(flow)
        if not isinstance(modes, dict):
            raise ProjectError(
                "Invalid MCP modes."
            )
        for mode, servers in modes.items():
            identifier(mode)
            if not isinstance(servers, dict):
                raise ProjectError(
                    "Invalid MCP servers."
                )
            for name, value in servers.items():
                _server(name, value)
    return data


def selected(root, mode_id):
    """Obtiene herramientas del modo."""
    workflow = get_workflow(load_config(root))
    workflow.mode(mode_id)
    data = _read(root)
    entries = (
        data["workflows"]
        .get(workflow.id, {})
        .get(mode_id, {})
    )
    return tuple(
        _server(name, value)
        for name, value in entries.items()
    )


@dataclass(frozen=True)
class AddMCP:
    """Comando de configuración atómica."""

    mode: str
    server: MCPServer

    def execute(self, root):
        """Actualiza un binding explícito."""
        workflow = get_workflow(load_config(root))
        workflow.mode(self.mode)
        self.server.validate_executable()
        data = _read(root)
        modes = data["workflows"].setdefault(
            workflow.id, {}
        )
        modes.setdefault(self.mode, {})[
            self.server.name
        ] = self.server.declaration()
        write_json(root, ".pxp/mcps.json", data)


@dataclass(frozen=True)
class RemoveMCP:
    """Comando que retira solo un binding."""

    mode: str
    name: str

    def execute(self, root):
        """Retira únicamente la asociación."""
        workflow = get_workflow(load_config(root))
        data = _read(root)
        modes = data["workflows"].get(
            workflow.id, {}
        )
        servers = modes.get(self.mode, {})
        if self.name not in servers:
            raise ProjectError(
                "MCP binding not found."
            )
        del servers[self.name]
        write_json(root, ".pxp/mcps.json", data)
