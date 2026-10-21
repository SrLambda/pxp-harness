"""Construcción de modos inmutables."""

import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from pxp_harness.cli import main
from pxp_harness.project import initialize


class WorkflowTests(unittest.TestCase):
    """Permite flujos distintos de PXP."""

    def test_mode_builder_immutable(self):
        """Valida y congela un modo completo."""
        from pxp_harness.workflows import (
            ModeBuilder,
        )

        mode = ModeBuilder("review").build(
            "Review", "delivery", ("notes",)
        )
        self.assertEqual(mode.id, "review")
        with self.assertRaises(
            FrozenInstanceError
        ):
            mode.id = "other"

    def test_builder_rejects_duplicate_modes(
        self,
    ):
        """Rechaza colecciones ambiguas."""
        from pxp_harness.errors import (
            ProjectError,
        )
        from pxp_harness.workflows import (
            ModeBuilder,
            Workflow,
        )

        mode = ModeBuilder("review").build(
            "Review", "delivery", ()
        )
        with self.assertRaises(ProjectError):
            Workflow("delivery", (mode, mode))

    def test_custom_workflow_uses_existing_cli(
        self,
    ):
        """Usa los comandos existentes."""
        with (
            tempfile.TemporaryDirectory() as temp
        ):
            root = Path(temp)
            initialize(root)
            config = {
                "schema_version": 1,
                "active_mode": "review",
                "artifacts": {
                    "notes": "notes.md"
                },
                "workflow": {
                    "id": "delivery",
                    "modes": [
                        {
                            "id": "review",
                            "label": "Review",
                            "group": "delivery",
                            "artifacts": [
                                "notes"
                            ],
                        }
                    ],
                },
            }
            (
                root / ".pxp/config.json"
            ).write_text(json.dumps(config))
            self.assertEqual(
                main(["mode"], cwd=root), 0
            )
            self.assertEqual(
                main(
                    ["mode", "review"], cwd=root
                ),
                0,
            )
            base = root / "base.md"
            base.write_text("Review carefully")
            self.assertEqual(
                main(
                    [
                        "prompt",
                        "set",
                        "review",
                        "base.md",
                    ],
                    cwd=root,
                ),
                0,
            )

    def test_init_custom_artifact_catalog(self):
        """Init respeta el catálogo del flujo."""
        import json

        with (
            tempfile.TemporaryDirectory() as temp
        ):
            root = Path(temp)
            directory = root / ".pxp"
            directory.mkdir()
            config = {
                "schema_version": 1,
                "active_mode": "review",
                "artifacts": {
                    "brief": "nested/brief.md"
                },
                "workflow": {
                    "id": "delivery",
                    "modes": [
                        {
                            "id": "review",
                            "label": "Review",
                            "group": "delivery",
                            "artifacts": [
                                "brief"
                            ],
                        }
                    ],
                },
            }
            (
                directory / "config.json"
            ).write_text(json.dumps(config))
            initialize(root)
            artifacts = directory / "artifacts"
            self.assertTrue(
                (
                    artifacts / "nested/brief.md"
                ).is_file()
            )
            self.assertFalse(
                (
                    artifacts / "requirements.md"
                ).exists()
            )

    def test_retired_prompt_does_not_block(self):
        """Conserva asociaciones retiradas."""
        from unittest.mock import Mock

        from pxp_harness.prompts import set_prompt

        with (
            tempfile.TemporaryDirectory() as temp
        ):
            root = Path(temp)
            initialize(root)
            base = root / "base.md"
            base.write_text("Former instructions")
            original = base.read_bytes()
            set_prompt(root, "plan", "base.md")
            path = root / ".pxp/config.json"
            config = json.loads(path.read_text())
            config["active_mode"] = "review"
            config["workflow"] = {
                "id": "delivery",
                "modes": [
                    {
                        "id": "review",
                        "label": "Review",
                        "group": "delivery",
                        "artifacts": [],
                    }
                ],
            }
            path.write_text(json.dumps(config))
            fake = Mock()
            fake.launch.return_value = 0
            self.assertEqual(
                main(["init"], cwd=root), 0
            )
            self.assertEqual(
                main(
                    ["chat"],
                    cwd=root,
                    strategy=fake,
                ),
                0,
            )
            bindings = root / ".pxp/prompts.json"
            self.assertEqual(
                json.loads(bindings.read_text()),
                {"plan": "base.md"},
            )
            self.assertEqual(
                main(
                    [
                        "prompt",
                        "set",
                        "review",
                        "base.md",
                    ],
                    cwd=root,
                ),
                0,
            )
            self.assertEqual(
                main(
                    ["prompt", "clear", "plan"],
                    cwd=root,
                ),
                0,
            )
            self.assertEqual(
                json.loads(bindings.read_text()),
                {"review": "base.md"},
            )
            self.assertEqual(
                base.read_bytes(), original
            )
