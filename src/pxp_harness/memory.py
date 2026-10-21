"""Integración explícita de Engram por repo."""

import os
from pathlib import Path

from .localio import (
    checked,
    read_json,
    write_json,
)
from .mcp import MCPServer
from .project import ProjectError, load_config

PROTOCOL = (
    "Use the project-local Engram MCP for "
    "relevant prior context. Save significant "
    "decisions and discoveries; summarize "
    "completed work before ending. Never store "
    "credentials or secrets. Memory operations "
    "are best effort; report failures honestly."
)


def paths(root):
    """Rechaza redirecciones externas."""
    checked(root, ".pxp/engram", directory=True)
    return checked(root, ".pxp/memory.json")


def load(root):
    """Valida toda la configuración local."""
    load_config(root)
    path = paths(root)
    if not path.exists():
        return {
            "schema_version": 1,
            "enabled": False,
        }
    value = read_json(root, path)
    if (
        not isinstance(value, dict)
        or set(value)
        - {
            "schema_version",
            "enabled",
            "executable",
        }
        or type(value.get("schema_version"))
        is not int
        or value.get("schema_version") != 1
        or type(value.get("enabled")) is not bool
        or (
            "executable" in value
            and not isinstance(
                value["executable"], str
            )
        )
    ):
        raise ProjectError(
            "Invalid memory configuration."
        )
    return value


def executable(config):
    """Usa binario privado o ruta explícita."""
    selected = config.get("executable")
    path = (
        Path(selected)
        if selected
        else Path(__file__).resolve().parents[3]
        / "libexec/pxp-harness/engram"
    )
    if (
        not path.is_absolute()
        or any(
            ord(c) < 32 or ord(c) == 127
            for c in str(path)
        )
        or not path.is_file()
        or not os.access(path, os.X_OK)
    ):
        raise ProjectError(
            "Engram executable unavailable; "
            "install bundled package or use "
            "memory enable --executable PATH."
        )
    return path.resolve()


def configure(root, enabled, selected=None):
    """Activa sin borrar bases de datos."""
    config = load(root)
    config["enabled"] = enabled
    if selected is not None:
        config["executable"] = selected
    if enabled:
        executable(config)
    write_json(root, paths(root), config)


def integration(root):
    """Devuelve configuración neutral."""
    config = load(root)
    if not config["enabled"]:
        return (), ()
    binary = executable(config)
    data = checked(
        root, ".pxp/engram", directory=True
    )
    if data.exists() and any(
        path.is_symlink()
        for path in data.rglob("*")
    ):
        raise ProjectError(
            "Memory store symlink."
        )
    server = MCPServer(
        "engram",
        str(binary),
        ("mcp",),
        (),
        (
            ("ENGRAM_DATA_DIR", str(data)),
            ("ENGRAM_CLOUD_AUTOSYNC", "0"),
            ("ENGRAM_PROJECT", ""),
        ),
    )
    return (server,), (PROTOCOL,)
