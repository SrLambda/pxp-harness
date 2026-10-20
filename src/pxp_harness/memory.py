"""Integración explícita de Engram por repo."""

import hashlib
import json
import os
from pathlib import Path

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
    directory = root / ".pxp"
    for path in (
        directory,
        directory / "memory.json",
        directory / "engram",
    ):
        if path.is_symlink():
            raise ProjectError(
                "Memory symlinks are not allowed."
            )
    return directory / "memory.json"


def load(root):
    """Valida toda la configuración local."""
    load_config(root)
    path = paths(root)
    if not path.exists():
        return {
            "schema_version": 1,
            "enabled": False,
        }
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise ProjectError(
            "Invalid memory configuration."
        ) from exc
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
    paths(root).write_text(
        json.dumps(config, indent=2) + "\n"
    )


def arguments(root):
    """Genera solo opciones efímeras de Codex."""
    config = load(root)
    if not config["enabled"]:
        return []
    binary = executable(config)
    data = root / ".pxp/engram"
    try:
        data.mkdir(mode=0o700, exist_ok=True)
        if any(
            path.is_symlink()
            for path in data.rglob("*")
        ):
            raise OSError("Memory store symlink")
    except OSError as exc:
        raise ProjectError(
            "Cannot use project memory store."
        ) from exc
    suffix = hashlib.sha256(
        str(root).encode()
    ).hexdigest()[:12]
    prefix = f"mcp_servers.pxp_engram_{suffix}."
    settings = {
        prefix + "command": str(binary),
        prefix + "args": ["mcp"],
        prefix + "cwd": str(root),
        prefix + "env": {
            "ENGRAM_DATA_DIR": str(data),
            "ENGRAM_CLOUD_AUTOSYNC": "0",
            "ENGRAM_PROJECT": "",
        },
        prefix + "enabled": True,
        prefix + "required": True,
        "developer_instructions": PROTOCOL,
    }
    result = []
    for key, value in settings.items():
        if isinstance(value, dict):
            encoded = (
                "{ "
                + ", ".join(
                    name
                    + " = "
                    + json.dumps(
                        text, ensure_ascii=False
                    )
                    for name, text in (
                        value.items()
                    )
                )
                + " }"
            )
        else:
            encoded = json.dumps(
                value, ensure_ascii=False
            )
        result += ["-c", key + "=" + encoded]
    return result
