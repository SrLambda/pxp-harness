"""Configuración y artefactos locales."""

from __future__ import annotations

from pathlib import Path

from .errors import ProjectError
from .localio import (
    checked,
    read_json,
    write_json,
)
from .workflows import (
    BUILTIN_SPECS,
    from_config,
    identifier,
)

MODES = BUILTIN_SPECS

CONFIG_DIR = ".pxp"
CONFIG_FILE = "config.json"
ARTIFACT_DIR = "artifacts"


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


def config_path(root: Path) -> Path:
    """Resuelve la configuración local."""
    return checked(
        root, f"{CONFIG_DIR}/{CONFIG_FILE}"
    )


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
    config = read_json(root, path)
    if (
        not isinstance(config, dict)
        or type(config.get("schema_version"))
        is not int
        or config.get("schema_version") != 1
    ):
        raise ProjectError(
            "Unsupported or invalid PXP config: "
            f"{path}"
        )
    if config.get("backend", "codex") != "codex":
        raise ProjectError(
            "Unsupported agent backend."
        )
    if set(config) - {
        "schema_version",
        "active_mode",
        "artifacts",
        "workflow",
        "backend",
    }:
        raise ProjectError(
            "Unknown project fields."
        )
    workflow = get_workflow(config)
    active = config.get("active_mode", "plan")
    if not isinstance(
        active, str
    ) or active not in {
        item.id for item in workflow.modes
    }:
        raise ProjectError("Unknown active mode.")
    artifacts = config.get("artifacts", ARTIFACTS)
    if not isinstance(artifacts, dict) or (
        "workflow" not in config
        and set(artifacts) != set(ARTIFACTS)
    ):
        raise ProjectError(
            "Invalid artifact fields."
        )
    for key, value in artifacts.items():
        identifier(key)
        if (
            not isinstance(value, str)
            or not value
            or not Path(value).parts
            or Path(value).is_absolute()
            or ".." in Path(value).parts
        ):
            raise ProjectError(
                "Invalid artifact path."
            )
        checked(
            root, Path(".pxp/artifacts") / value
        )
    if len(set(artifacts.values())) != len(
        artifacts
    ):
        raise ProjectError(
            "Duplicate artifact paths."
        )
    for mode in workflow.modes:
        if not set(mode.artifacts) <= set(
            artifacts
        ):
            raise ProjectError(
                "Unknown mode artifact."
            )
    return config


def initialize(root: Path) -> bool:
    """Crea archivos sin sobrescribirlos."""
    directory = checked(
        root, CONFIG_DIR, directory=True
    )
    artifact_dir = checked(
        root, ".pxp/artifacts", directory=True
    )
    path = config_path(root)
    created_config = not path.exists()
    config = (
        {
            "schema_version": 1,
            "active_mode": "plan",
            "artifacts": ARTIFACTS,
        }
        if created_config
        else load_config(root)
    )
    targets = [
        (
            checked(root, artifact_dir / name),
            ARTIFACT_TITLES.get(name, key),
        )
        for key, name in config.get(
            "artifacts", ARTIFACTS
        ).items()
    ]
    try:
        directory.mkdir(exist_ok=True)
        artifact_dir.mkdir(exist_ok=True)
        if created_config:
            write_json(root, path, config)
        for artifact, title in targets:
            if not artifact.exists():
                artifact.parent.mkdir(
                    parents=True, exist_ok=True
                )
                with artifact.open(
                    "x", encoding="utf-8"
                ) as target:
                    target.write(f"# {title}\n\n")
    except OSError:
        raise ProjectError(
            "Cannot initialize project files."
        ) from None
    return created_config


def set_mode(root: Path, mode_id: str) -> None:
    """Guarda el modo seleccionado."""
    config = load_config(root)
    get_workflow(config).mode(mode_id)
    config["active_mode"] = mode_id
    write_json(root, config_path(root), config)


def mode_context(
    root: Path, config: dict
) -> tuple[dict, list[str]]:
    """Obtiene modo y rutas de artefactos."""
    active_id = config.get("active_mode", "plan")
    active = get_workflow(config).mode(active_id)
    configured = config.get(
        "artifacts", ARTIFACTS
    )
    paths = [
        f".pxp/artifacts/{configured[key]}"
        for key in active.artifacts
    ]
    return active.as_dict(), paths


def get_workflow(config):
    """Resuelve el flujo sin más IO."""
    return from_config(config, ARTIFACTS)
