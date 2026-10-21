"""Instrucciones base de Codex por modo."""

from __future__ import annotations

from pathlib import Path

from .localio import (
    checked,
    read_json,
    write_json,
)
from .project import (
    ProjectError,
    get_workflow,
    load_config,
)
from .workflows import identifier

MAX_BYTES = 1024 * 1024
MODEL_INSTRUCTIONS = "model_instructions_file"


def _mode(root, mode: str) -> None:
    """Rechaza modos no reconocidos."""
    get_workflow(load_config(root)).mode(mode)


def _config_path(root: Path) -> Path:
    """Rechaza configuraciones enlazadas."""
    return checked(root, ".pxp/prompts.json")


def _resolve(root: Path, value: str) -> Path:
    """Resuelve únicamente rutas del proyecto."""
    if not isinstance(value, str) or not value:
        raise ProjectError("Invalid prompt path.")
    path = checked(root, value)
    if not path.is_file():
        raise ProjectError(
            "Prompt must be a local regular file."
        )
    return path


def _validate_file(path: Path) -> None:
    """Valida UTF-8 no vacío sin mostrar texto."""
    try:
        with path.open("rb") as source:
            raw = source.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError
        text = raw.decode("utf-8-sig")
        if not text.strip() or any(
            ord(char) < 32
            and char not in "\t\r\n"
            for char in text
        ):
            raise ValueError
    except (OSError, ValueError):
        raise ProjectError(
            "Prompt must contain UTF-8 text "
            "(1 byte to 1 MiB, nonempty)."
        ) from None


def _read(root: Path) -> dict:
    """Lee asociaciones sin migrar archivos."""
    load_config(root)
    path = _config_path(root)
    if not path.exists():
        return {}
    data = read_json(root, path)
    if not isinstance(data, dict):
        raise ProjectError(
            "Invalid prompt config."
        )
    for mode, value in data.items():
        identifier(mode)
        if (
            not isinstance(value, str)
            or not value
        ):
            raise ProjectError(
                "Invalid configured prompt path."
            )
        try:
            value.encode("utf-8")
        except UnicodeError:
            raise ProjectError(
                "Invalid configured prompt path."
            ) from None
        if (
            Path(value).is_absolute()
            or ".." in Path(value).parts
            or any(
                ord(char) < 32 or ord(char) == 127
                for char in value
            )
        ):
            raise ProjectError(
                "Prompt paths must be relative."
            )
    return data


def _save(root: Path, data: dict) -> None:
    """Guarda rutas sin tocar los prompts."""
    write_json(root, _config_path(root), data)


def set_prompt(
    root: Path, mode: str, value: str
) -> None:
    """Asocia un archivo existente con un modo."""
    _mode(root, mode)
    data = _read(root)
    path = _resolve(root, value)
    _validate_file(path)
    data[mode] = path.relative_to(root).as_posix()
    _save(root, data)


def clear_prompt(root: Path, mode: str) -> None:
    """Elimina la asociación, nunca el archivo."""
    identifier(mode)
    data = _read(root)
    if mode in data:
        del data[mode]
        _save(root, data)
    else:
        _mode(root, mode)


def load_prompt(
    root: Path, mode: str
) -> Path | None:
    """Obtiene el archivo validado, si existe."""
    _mode(root, mode)
    data = _read(root)
    if mode not in data:
        return None
    path = _resolve(root, data[mode])
    _validate_file(path)
    return path


def editable_prompt(
    root: Path, mode: str
) -> tuple[Path, bool]:
    """Resuelve un archivo o un borrador."""
    _mode(root, mode)
    data = _read(root)
    if mode in data:
        return _resolve(root, data[mode]), False
    directory = checked(
        root, ".pxp/prompts", directory=True
    )
    if directory.is_symlink():
        raise ProjectError(
            "Prompt directory cannot "
            "be a symlink."
        )
    path = checked(root, directory / f"{mode}.md")
    try:
        directory.mkdir(exist_ok=True)
        try:
            with path.open("x", encoding="utf-8"):
                pass
        except FileExistsError:
            pass
    except OSError:
        raise ProjectError(
            "Cannot create local prompt draft."
        ) from None
    return _resolve(root, str(path)), True
