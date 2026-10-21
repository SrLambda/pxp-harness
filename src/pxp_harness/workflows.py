"""Modos inmutables y flujos declarativos."""

import re
from dataclasses import dataclass

from .errors import ProjectError


def identifier(value):
    """Valida identificadores portables."""
    if not isinstance(
        value, str
    ) or not re.fullmatch(
        r"[a-z][a-z0-9_-]{0,63}", value
    ):
        raise ProjectError("Invalid identifier.")
    return value


@dataclass(frozen=True)
class Mode:
    """Unidad de contexto sin backend acoplado."""

    id: str
    label: str
    group: str
    artifacts: tuple[str, ...]

    def __post_init__(self):
        """Valida incluso construcción directa."""
        identifier(self.id)
        identifier(self.group)
        try:
            self.label.encode("utf-8")
        except (AttributeError, UnicodeError):
            raise ProjectError(
                "Invalid label."
            ) from None
        if (
            not isinstance(self.label, str)
            or not self.label.strip()
            or len(self.label) > 120
            or any(
                ord(c) < 32 for c in self.label
            )
            or type(self.artifacts) is not tuple
        ):
            raise ProjectError("Invalid mode.")
        for key in self.artifacts:
            identifier(key)
        if len(set(self.artifacts)) != len(
            self.artifacts
        ):
            raise ProjectError(
                "Duplicate artifacts."
            )

    def as_dict(self):
        """Mantiene la interfaz anterior."""
        return {
            "id": self.id,
            "label": self.label,
            "group": self.group,
        }


class ModeBuilder:
    """Construye un modo completo y validado."""

    def __init__(self, mode_id):
        """Recibe la identidad de la unidad."""
        self.mode_id = identifier(mode_id)

    def build(self, label, group, artifacts=()):
        """Publica una instancia inmutable."""
        if type(artifacts) not in (tuple, list):
            raise ProjectError(
                "Invalid artifacts."
            )
        return Mode(
            self.mode_id,
            label,
            group,
            tuple(artifacts),
        )


@dataclass(frozen=True)
class Workflow:
    """Colección validada de modos únicos."""

    id: str
    modes: tuple[Mode, ...]

    def __post_init__(self):
        """Rechaza flujos vacíos o ambiguos."""
        identifier(self.id)
        if (
            type(self.modes) is not tuple
            or not self.modes
            or not all(
                isinstance(m, Mode)
                for m in self.modes
            )
            or len({m.id for m in self.modes})
            != len(self.modes)
        ):
            raise ProjectError(
                "Invalid workflow."
            )

    def mode(self, mode_id):
        """Resuelve un modo reconocido."""
        for mode in self.modes:
            if mode.id == mode_id:
                return mode
        raise ProjectError(
            "Unknown workflow mode."
        )


def from_config(config, default_catalog):
    """Compone datos sin imports de plugins."""
    declaration = config.get("workflow")
    if "workflow" not in config:
        items = [
            {
                **item,
                "artifacts": list(
                    default_catalog
                ),
            }
            for item in BUILTIN_SPECS
        ]
        workflow_id = "pxp"
    else:
        if (
            not isinstance(declaration, dict)
            or set(declaration) != {"id", "modes"}
            or not isinstance(
                declaration["modes"], list
            )
        ):
            raise ProjectError(
                "Invalid workflow."
            )
        items = declaration["modes"]
        workflow_id = declaration["id"]
    modes = []
    for item in items:
        if (
            not isinstance(item, dict)
            or set(item)
            != {
                "id",
                "label",
                "group",
                "artifacts",
            }
            or not isinstance(
                item["artifacts"], list
            )
        ):
            raise ProjectError(
                "Invalid mode fields."
            )
        modes.append(
            ModeBuilder(item["id"]).build(
                item["label"],
                item["group"],
                item["artifacts"],
            )
        )
    return Workflow(workflow_id, tuple(modes))


BUILTIN_SPECS = (
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
