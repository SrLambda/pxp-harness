"""Edición y lectura de prompts con NeoVim."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .project import ProjectError
from .prompts import (
    editable_prompt,
    load_prompt,
    set_prompt,
)


def open_prompt(
    root: Path, mode: str, *, readonly=False
) -> int:
    """Abre NeoVim con argumentos explícitos."""
    executable = shutil.which("nvim")
    if executable is None:
        raise ProjectError(
            "NeoVim not found. "
            "Install Neovim and "
            "ensure nvim is on PATH."
        )
    draft = False
    if readonly:
        path = load_prompt(root, mode)
        if path is None:
            raise ProjectError(
                "No base prompt configured. "
                "Run pxp prompt edit first."
            )
    else:
        path, draft = editable_prompt(root, mode)
    environment = dict(os.environ)
    command = [executable]
    if readonly:
        environment["NVIM_LOG_FILE"] = os.devnull
        command.extend(
            [
                "--clean",
                "-R",
                "-M",
                "-n",
                "-i",
                "NONE",
            ]
        )
    command.extend(["--", str(path)])
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            env=environment,
            check=False,
            shell=False,
        )
    except KeyboardInterrupt:
        return 130
    except OSError:
        raise ProjectError(
            "Could not launch NeoVim. "
            "Any draft file has been kept."
        ) from None
    if completed.returncode:
        return completed.returncode
    if not readonly:
        if draft:
            set_prompt(root, mode, str(path))
        else:
            load_prompt(root, mode)
    return 0
