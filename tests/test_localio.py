"""Límites de escritura por proyecto."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from pxp_harness.cli import main
from pxp_harness.project import initialize


class LocalIoTests(unittest.TestCase):
    """Reproduce enlaces y esquemas inválidos."""

    def setUp(self):
        """Crea dos carpetas aisladas."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = (
            Path(self.temp.name) / "project"
        )
        self.outside = (
            Path(self.temp.name) / "other"
        )
        self.root.mkdir()
        self.outside.mkdir()

    def test_init_rejects_symlink_before_writes(
        self,
    ):
        """No crea archivos en destino externo."""
        (self.root / ".pxp").symlink_to(
            self.outside, target_is_directory=True
        )
        self.assertEqual(
            main(["init"], cwd=self.root), 1
        )
        self.assertEqual(
            list(self.outside.iterdir()), []
        )

    def test_init_preflights_all_artifacts(self):
        """Valida todo antes de crear archivos."""
        directory = self.root / ".pxp/artifacts"
        directory.mkdir(parents=True)
        (directory / "rules.md").symlink_to(
            self.outside / "target"
        )
        before = set(directory.iterdir())
        self.assertEqual(
            main(["init"], cwd=self.root), 1
        )
        self.assertEqual(
            set(directory.iterdir()), before
        )
        self.assertFalse(
            (
                self.root / ".pxp/config.json"
            ).exists()
        )

    def test_mode_replaces_hardlink(self):
        """No modifica el inode compartido."""
        initialize(self.root)
        path = self.root / ".pxp/config.json"
        outside = self.outside / "config.json"
        os.link(path, outside)
        before = outside.read_bytes()
        self.assertEqual(
            main(
                ["mode", "design"], cwd=self.root
            ),
            0,
        )
        self.assertEqual(
            outside.read_bytes(), before
        )
        self.assertNotEqual(
            path.stat().st_ino,
            outside.stat().st_ino,
        )

    def test_bad_artifacts_controlled(self):
        """Devuelve error en vez de KeyError."""
        initialize(self.root)
        path = self.root / ".pxp/config.json"
        config = json.loads(path.read_text())
        for value in (
            {},
            [],
            None,
            {"requirements": "../../outside"},
        ):
            config["artifacts"] = value
            path.write_text(json.dumps(config))
            self.assertEqual(
                main(["chat"], cwd=self.root), 1
            )

    def test_sidecars_replace_hardlinks(
        self,
    ):
        """Aísla todos los guardados JSON."""
        initialize(self.root)
        prompt = self.root / "base.md"
        prompt.write_text("Local instructions")
        cases = (
            (
                "prompts.json",
                {},
                [
                    "prompt",
                    "set",
                    "plan",
                    "base.md",
                ],
            ),
            (
                "standards.json",
                {
                    "active_profile": "default",
                    "profiles": {
                        "default": {
                            "line_length": 50,
                            "doc_language": "es",
                        }
                    },
                },
                [
                    "standards",
                    "configure",
                    "--profile",
                    "local",
                ],
            ),
            (
                "memory.json",
                {
                    "schema_version": 1,
                    "enabled": False,
                },
                ["memory", "disable"],
            ),
        )
        for name, data, command in cases:
            path = self.root / ".pxp" / name
            path.write_text(json.dumps(data))
            outside = self.outside / name
            os.link(path, outside)
            before = outside.read_bytes()
            self.assertEqual(
                main(command, cwd=self.root), 0
            )
            self.assertEqual(
                outside.read_bytes(),
                before,
                name,
            )

    def test_null_workflow_rejected(self):
        """No admite campos declarativos nulos."""
        initialize(self.root)
        path = self.root / ".pxp/config.json"
        config = json.loads(path.read_text())
        config["workflow"] = None
        path.write_text(json.dumps(config))
        self.assertEqual(
            main(["mode"], cwd=self.root), 1
        )

    def test_regular_ancestor_preflight(self):
        """Rechaza un ancestro de tipo archivo."""
        initialize(self.root)
        config = self.root / ".pxp/config.json"
        data = json.loads(config.read_text())
        data["artifacts"]["requirements"] = (
            "blocked/notes.md"
        )
        config.write_text(json.dumps(data))
        blocked = (
            self.root / ".pxp/artifacts/blocked"
        )
        blocked.write_text("User content")
        before = config.read_bytes()
        self.assertEqual(
            main(["init"], cwd=self.root), 1
        )
        self.assertEqual(
            config.read_bytes(), before
        )
