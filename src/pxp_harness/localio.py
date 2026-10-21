"""IO local validado; no es un sandbox."""

import json
import os
import tempfile
from pathlib import Path

from .errors import ProjectError


def checked(root, value, *, directory=False):
    """Rechaza escapes y ancestros enlazados."""
    try:
        root = Path(root).absolute()
        path = Path(value)
        if not path.is_absolute():
            path = root / path
        relative = path.relative_to(root)
        if ".." in relative.parts:
            raise ValueError
        text = str(path)
        text.encode("utf-8")
        if any(
            ord(c) < 32 or ord(c) == 127
            for c in text
        ):
            raise ValueError
        for ancestor in (root, *root.parents):
            if ancestor.is_symlink():
                raise ValueError
        current = root
        for index, part in enumerate(
            relative.parts
        ):
            current = current / part
            if current.is_symlink():
                raise ValueError
            if (
                index < len(relative.parts) - 1
                and current.exists()
                and not current.is_dir()
            ):
                raise ValueError
        if path.exists():
            valid = (
                path.is_dir()
                if directory
                else path.is_file()
            )
            if not valid:
                raise ValueError
        return path
    except (OSError, ValueError, RuntimeError):
        raise ProjectError(
            "Expected a project-local path "
            "without symlink ancestors."
        ) from None


def read_json(root, value, default=None):
    """Lee JSON sin mostrar contenido sensible."""
    path = checked(root, value)
    if not path.exists() and default is not None:
        return default
    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        raise ProjectError(
            "Cannot read project JSON config."
        ) from None


def write_json(root, value, data):
    """Reemplaza sin truncar archivos."""
    path = checked(root, value)
    temporary = None
    try:
        encoded = (
            json.dumps(
                data, indent=2, ensure_ascii=False
            )
            + "\n"
        )
        descriptor, name = tempfile.mkstemp(
            prefix=".pxp-", dir=path.parent
        )
        temporary = Path(name)
        with os.fdopen(
            descriptor, "w", encoding="utf-8"
        ) as target:
            target.write(encoded)
            target.flush()
            os.fsync(target.fileno())
        checked(root, path)
        os.replace(temporary, path)
    except (OSError, ValueError):
        raise ProjectError(
            "Cannot save project JSON config."
        ) from None
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
