"""Descubrimiento de proyectos y Git opcional."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .project import ProjectError


def _marker_present(root: Path) -> bool:
    """Detecta metadatos Git no vacíos."""
    marker = root / ".git"
    try:
        if marker.is_symlink():
            return True
        if marker.is_dir():
            return any(marker.iterdir())
        return marker.exists()
    except OSError:
        raise ProjectError(
            "Cannot inspect Git metadata."
        ) from None


def find_project_root(start: Path) -> Path:
    """Encuentra un proyecto dentro de Git."""
    configured = None
    for current in (start, *start.parents):
        if (
            (current / "HEAD").is_file()
            and (current / "objects").is_dir()
            and (current / "refs").is_dir()
        ):
            raise ProjectError(
                "Git metadata is not a project."
            )
        config = current / ".pxp/config.json"
        if (
            config.is_file()
            and configured is None
        ):
            configured = current
        if _marker_present(current):
            return configured or current
    return start


def ensure_git(root: Path) -> None:
    """Crea Git solo cuando hace falta."""
    executable = shutil.which("git")
    if executable is None:
        raise ProjectError(
            "Git not found. Install Git or "
            "run pxp init without --git."
        )
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("GIT_")
    }

    def run(*arguments):
        """Ejecuta Git con entorno aislado."""
        try:
            return subprocess.run(
                [executable, *arguments],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                shell=False,
                check=False,
                timeout=15,
            )
        except (
            OSError,
            UnicodeError,
            subprocess.TimeoutExpired,
        ):
            raise ProjectError(
                "Cannot run Git. "
                "Check installation "
                "and filesystem access."
            ) from None

    def working_root(result):
        """Verifica la raíz sin cambios."""
        try:
            found = Path(
                result.stdout.rstrip("\n")
            ).resolve()
        except (OSError, ValueError):
            raise ProjectError(
                "Cannot resolve Git project root."
            ) from None
        if found != root:
            raise ProjectError(
                "PXP is inside another "
                "Git project. "
                "Run pxp init --git at its root."
            )

    discovered = run(
        "rev-parse", "--show-toplevel"
    )
    if discovered.returncode == 0:
        working_root(discovered)
        return
    metadata = run("rev-parse", "--git-dir")
    marker = (root / ".git").exists() or any(
        _marker_present(directory)
        for directory in root.parents
    )
    if metadata.returncode == 0 or marker:
        raise ProjectError(
            "Cannot use this Git working tree. "
            "Check repository configuration."
        )
    initialized = run("init", "--quiet")
    if initialized.returncode:
        raise ProjectError(
            "Git initialization failed. Check "
            "permissions and Git configuration."
        )
    verified = run("rev-parse", "--show-toplevel")
    if verified.returncode:
        raise ProjectError(
            "Git initialized but "
            "verification failed. "
            "Inspect the repository "
            "before retrying."
        )
    working_root(verified)
