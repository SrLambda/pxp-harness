"""Comandos MCP por modo y flujo."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

from pxp_harness.cli import main
from pxp_harness.project import initialize


class McpTests(unittest.TestCase):
    """Configura sin ejecutar shell."""

    def setUp(self):
        """Prepara un proyecto temporal."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        initialize(self.root)

    def test_command_add_remove_mode_scope(self):
        """Respeta la selección de modo."""
        from pxp_harness.mcp import (
            AddMCP,
            MCPServer,
            RemoveMCP,
            selected,
        )

        server = MCPServer(
            "docs",
            sys.executable,
            ("--version",),
            ("DOCS_TOKEN",),
        )
        AddMCP("plan", server).execute(self.root)
        self.assertEqual(
            selected(self.root, "plan"), (server,)
        )
        self.assertEqual(
            selected(self.root, "design"), ()
        )
        RemoveMCP("plan", "docs").execute(
            self.root
        )
        self.assertEqual(
            selected(self.root, "plan"), ()
        )

    def test_cli_accepts_names_not_secrets(self):
        """Guarda solo nombres de variables."""
        self.assertEqual(
            main(
                [
                    "mcp",
                    "add",
                    "plan",
                    "docs",
                    "--command",
                    sys.executable,
                    "--arg=--version",
                    "--env-var",
                    "DOCS_TOKEN",
                ],
                cwd=self.root,
            ),
            0,
        )
        path = self.root / ".pxp/mcps.json"
        self.assertIn(
            "DOCS_TOKEN", path.read_text()
        )
        self.assertNotIn(
            "secretvalue", path.read_text()
        )
        data = json.loads(path.read_text())
        data["workflows"]["pxp"]["plan"]["docs"][
            "env"
        ] = {"TOKEN": "secretvalue"}
        path.write_text(json.dumps(data))
        self.assertEqual(
            main(["mcp", "list"], cwd=self.root),
            1,
        )

    def test_unknown_mode_rejected(self):
        """No crea configuración para errores."""
        from pxp_harness.errors import (
            ProjectError,
        )
        from pxp_harness.mcp import (
            AddMCP,
            MCPServer,
        )

        with self.assertRaises(ProjectError):
            AddMCP(
                "unknown",
                MCPServer("docs", sys.executable),
            ).execute(self.root)
        self.assertFalse(
            (
                self.root / ".pxp/mcps.json"
            ).exists()
        )

    def test_other_workflow_does_not_inherit(
        self,
    ):
        """Separa vínculos por workflow."""
        from pxp_harness.mcp import (
            AddMCP,
            MCPServer,
            selected,
        )

        AddMCP(
            "plan",
            MCPServer("docs", sys.executable),
        ).execute(self.root)
        path = self.root / ".pxp/config.json"
        config = json.loads(path.read_text())
        config["workflow"] = {
            "id": "delivery",
            "modes": [
                {
                    "id": "plan",
                    "label": "Review",
                    "group": "delivery",
                    "artifacts": [],
                }
            ],
        }
        path.write_text(json.dumps(config))
        self.assertEqual(
            selected(self.root, "plan"), ()
        )
