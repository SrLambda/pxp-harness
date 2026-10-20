"""Configuración y artefactos locales."""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_DIR = ".pxp"
CONFIG_FILE = "config.json"
ARTIFACT_DIR = "artifacts"

MODES = (
    {
        "id": "plan",
        "label": "General plan",
        "group": "general",
    },
    {
        "id": "design",
        "label": "General design",
        "group": "general",
    },
    {
        "id": "iteration-initialization",
        "label": "Iteration initialization",
        "group": "iteration",
    },
    {
        "id": "iteration-design",
        "label": "Iteration design",
        "group": "iteration",
    },
    {
        "id": "implementation-tests",
        "label": "Implementation tests",
        "group": "implementation",
    },
    {
        "id": "implementation-code",
        "label": "Implementation code",
        "group": "implementation",
    },
    {
        "id": "implementation-refactor",
        "label": "Implementation refactor",
        "group": "implementation",
    },
    {
        "id": "system-tests",
        "label": "System tests",
        "group": "validation",
    },
    {
        "id": "retrospective",
        "label": "Retrospective",
        "group": "iteration",
    },
)

ARTIFACTS = {
    "requirements": "requirements.md",
    "rules": "rules.md",
    "architecture_design": (
        "architecture-design.md"
    ),
    "mockups": "mockups.md",
    "data_model": "data-model.md",
}

ARTIFACT_TITLES = {
    "requirements.md": "Requirements",
    "rules.md": "Project Rules",
    "architecture-design.md": (
        "Architecture Design"
    ),
    "mockups.md": "Mockups",
    "data-model.md": "Data Model",
}


class ProjectError(Exception):
    """Error de configuración del proyecto."""


def config_path(root: Path) -> Path:
    """Resuelve la configuración local."""
    return root / CONFIG_DIR / CONFIG_FILE


def load_config(root: Path) -> dict:
    """Lee la configuración existente."""
    path = config_path(root)
    if not path.is_file():
        raise ProjectError(
            (
                "PXP is not initialized "
                "here. Run `pxp init` "
                "first."
            )
        )
    try:
        config = json.loads(
            path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectError(
            f"Could not read {path}: {exc}"
        ) from exc
    if (
        not isinstance(config, dict)
        or config.get("schema_version") != 1
    ):
        raise ProjectError(
            "Unsupported or invalid PXP config: "
            f"{path}"
        )
    return config


def initialize(root: Path) -> bool:
    """Crea archivos sin sobrescribirlos."""
    directory = root / CONFIG_DIR
    artifact_dir = directory / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(
        parents=True, exist_ok=True
    )
    path = directory / CONFIG_FILE
    created_config = not path.exists()
    if created_config:
        config = {
            "schema_version": 1,
            "active_mode": "plan",
            "artifacts": ARTIFACTS,
        }
        path.write_text(
            json.dumps(config, indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        config = load_config(root)
        config.setdefault("artifacts", ARTIFACTS)
    for (
        filename,
        title,
    ) in ARTIFACT_TITLES.items():
        artifact = artifact_dir / filename
        if not artifact.exists():
            artifact.write_text(
                f"# {title}\n\n", encoding="utf-8"
            )
    return created_config


def set_mode(root: Path, mode_id: str) -> None:
    """Guarda el modo seleccionado."""
    if mode_id not in {
        mode["id"] for mode in MODES
    }:
        raise ProjectError(
            f"Unknown mode '{mode_id}'. "
            "Run `pxp mode` to list modes."
        )
    config = load_config(root)
    config["active_mode"] = mode_id
    config_path(root).write_text(
        json.dumps(config, indent=2) + "\n",
        encoding="utf-8",
    )


def mode_context(
    root: Path, config: dict
) -> tuple[dict, list[str]]:
    """Obtiene modo y rutas de artefactos."""
    active_id = config.get("active_mode", "plan")
    active = next(
        (
            mode
            for mode in MODES
            if mode["id"] == active_id
        ),
        None,
    )
    if active is None:
        raise ProjectError(
            f"Configured mode '{active_id}' "
            "is not recognized. "
            "Run `pxp mode <mode-id>`."
        )
    configured_artifacts = config.get(
        "artifacts", ARTIFACTS
    )
    paths = [
        f"{CONFIG_DIR}/{ARTIFACT_DIR}/"
        f"{configured_artifacts[key]}"
        for key in ARTIFACTS
    ]
    return active, paths
