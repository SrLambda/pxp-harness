"""Perfiles locales y comprobación de Python."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from .localio import (
    checked,
    read_json,
    write_json,
)
from .project import ProjectError, load_config

DEFAULT = {
    "line_length": 50,
    "doc_language": "es",
}
SKIP = {
    ".git",
    ".codegraph",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "build",
    "dist",
    ".tox",
    ".ruff_cache",
}


def _path(root: Path) -> Path:
    """Resuelve solo archivos locales seguros."""
    return checked(root, ".pxp/standards.json")


def _validate(value: dict) -> None:
    """Valida valores antes de usarlos."""
    if not isinstance(value, dict):
        raise ProjectError(
            "Invalid standards profile."
        )
    if set(value) != set(DEFAULT):
        raise ProjectError(
            "Invalid profile fields."
        )
    length = value["line_length"]
    if (
        type(length) is not int
        or not 40 <= length <= 320
    ):
        raise ProjectError(
            ("Line length must be 40..320.")
        )
    if value["doc_language"] not in ("es", "en"):
        raise ProjectError(
            "Doc language must be es/en."
        )


def _read(root: Path) -> dict:
    """Carga perfiles sin modificar archivos."""
    load_config(root)
    path = _path(root)
    if not path.exists():
        return {
            "active_profile": "default",
            "profiles": {
                "default": dict(DEFAULT)
            },
        }
    data = read_json(root, path)
    if not isinstance(data, dict):
        raise ProjectError(
            "Invalid standards config."
        )
    if set(data) != {
        "active_profile",
        "profiles",
    }:
        raise ProjectError(
            "Invalid standards fields."
        )
    profiles = data["profiles"]
    if (
        not isinstance(profiles, dict)
        or not profiles
    ):
        raise ProjectError(
            "Profiles must be a map."
        )
    for name, value in profiles.items():
        _name(name)
        _validate(value)
    active = data["active_profile"]
    if (
        not isinstance(active, str)
        or active not in profiles
    ):
        raise ProjectError(
            "Unknown active profile."
        )
    return data


def _name(name: str) -> None:
    """Valida nombres simples."""
    if not isinstance(
        name, str
    ) or not re.fullmatch(
        r"[a-zA-Z0-9_-]{1,40}", name
    ):
        raise ProjectError(
            "Invalid profile name."
        )


def load_standards(root: Path) -> dict:
    """Devuelve el perfil efectivo."""
    data = _read(root)
    name = data["active_profile"]
    return {
        "profile": name,
        **data["profiles"][name],
    }


def configure(
    root: Path,
    profile: str,
    length: int | None,
    language: str | None,
) -> None:
    """Crea o selecciona un perfil."""
    _name(profile)
    data = _read(root)
    value = dict(
        data["profiles"].get(profile, DEFAULT)
    )
    if length is not None:
        value["line_length"] = length
    if language is not None:
        value["doc_language"] = language
    _validate(value)
    data["profiles"][profile] = value
    data["active_profile"] = profile
    write_json(root, _path(root), data)


def python_files(root: Path) -> list[Path]:
    """Enumera Python sin atravesar enlaces."""
    files = []
    for entry in sorted(root.iterdir()):
        if (
            entry.is_symlink()
            or entry.name in SKIP
        ):
            continue
        if entry.is_dir():
            files.extend(python_files(entry))
        elif entry.suffix == ".py":
            files.append(entry)
    return files


def run_checks(root: Path, *, apply=False) -> int:
    """Aplica correcciones seguras y comprueba."""
    settings = load_standards(root)
    executable = shutil.which("ruff")
    if executable is None:
        raise ProjectError(
            (
                "Ruff not found. Install "
                "ruff>=0.16.4."
            )
        )
    files = python_files(root)
    if not files:
        return 0
    targets = [str(path) for path in files]
    common = [
        "--isolated",
        "--no-cache",
        "--line-length",
        str(settings["line_length"]),
    ]

    def invoke(arguments):
        """Ejecuta Ruff sin shell."""
        return subprocess.run(
            [
                executable,
                *arguments,
                *common,
                "--",
                *targets,
            ],
            cwd=root,
            check=False,
        ).returncode

    try:
        if apply:
            code = invoke(
                [
                    "check",
                    "--select",
                    "E,F,I,D",
                    "--ignore",
                    "D203,D213",
                    "--fix",
                ]
            )
            # Formatea pese a errores de lint.
            formatted = invoke(["format"])
            if code == 2 or formatted:
                return 1
        lint = invoke(
            [
                "check",
                "--select",
                "E,F,I,D",
                "--ignore",
                "D203,D213",
            ]
        )
        formatted = invoke(["format", "--check"])
    except OSError as exc:
        raise ProjectError(
            f"Cannot launch Ruff: {exc}"
        ) from exc
    too_long = False
    for path in files:
        try:
            lines = path.read_text(
                encoding="utf-8"
            ).splitlines()
        except (OSError, UnicodeError) as exc:
            raise ProjectError(
                f"Cannot read source: {path}"
            ) from exc
        for number, line in enumerate(lines, 1):
            if (
                len(line.expandtabs(8))
                > settings["line_length"]
            ):
                print(
                    f"{path}:{number}: "
                    "line too long"
                )
                too_long = True
    return int(
        bool(lint or formatted or too_long)
    )
