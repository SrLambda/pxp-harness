"""Sustitución del backend sin sesiones reales."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pxp_harness.cli import main
from pxp_harness.project import initialize


class FakeStrategy:
    """Backend externo que registra peticiones."""

    def __init__(self):
        """Prepara la captura en memoria."""
        self.requests = []

    def launch(self, request):
        """No conoce Codex ni lanza procesos."""
        self.requests.append(request)
        return 17


class AgentTests(unittest.TestCase):
    """La CLI no construye argumentos nativos."""

    def test_strategy_is_injectable(self):
        """Reemplaza el backend concreto."""
        with (
            tempfile.TemporaryDirectory() as temp
        ):
            root = Path(temp)
            initialize(root)
            fake = FakeStrategy()
            with patch(
                "pxp_harness.codex."
                "CodexStrategy.launch",
                side_effect=AssertionError(
                    "Unexpected native launch"
                ),
            ):
                result = main(
                    ["chat", "hello"],
                    cwd=root,
                    strategy=fake,
                )
            self.assertEqual(
                result,
                17,
            )
            self.assertEqual(
                fake.requests[0].user_request,
                "hello",
            )
            self.assertIn(
                "Active mode: plan",
                fake.requests[0].context,
            )

    def test_unknown_backend_rejected(self):
        """Rechaza antes del adaptador externo."""
        with (
            tempfile.TemporaryDirectory() as temp
        ):
            root = Path(temp)
            initialize(root)
            path = root / ".pxp/config.json"
            config = json.loads(path.read_text())
            config["backend"] = "unregistered"
            path.write_text(json.dumps(config))
            fake = FakeStrategy()
            self.assertEqual(
                main(
                    ["chat"],
                    cwd=root,
                    strategy=fake,
                ),
                1,
            )
            self.assertEqual(fake.requests, [])

    def test_codex_exact_transport(self):
        """Separa transporte y solicitud."""
        import sys
        from subprocess import CompletedProcess

        from pxp_harness.agents import (
            LaunchRequest,
        )
        from pxp_harness.codex import (
            CodexStrategy,
        )
        from pxp_harness.mcp import MCPServer

        with (
            tempfile.TemporaryDirectory() as temp
        ):
            root = Path(temp)
            base = root / "base ñ.md"
            base.write_text("Own base prompt")
            server = MCPServer(
                "docs",
                sys.executable,
                ('quote" and slash\\', "emoji🙂"),
                ("DOCS_TOKEN",),
            )
            request = LaunchRequest(
                root,
                "context",
                "user text",
                base,
                (server,),
            )
            with (
                patch(
                    "pxp_harness.codex."
                    "shutil.which",
                    return_value="/codex",
                ),
                patch(
                    "pxp_harness.codex."
                    "subprocess.run",
                    return_value=CompletedProcess(
                        [], 0
                    ),
                ) as spawn,
            ):
                self.assertEqual(
                    CodexStrategy().launch(
                        request
                    ),
                    0,
                )
            argv = spawn.call_args.args[0]
            self.assertEqual(argv[0], "/codex")
            self.assertEqual(
                argv[-1],
                "context\n"
                "User request: user text",
            )
            self.assertIn(
                "model_instructions_file="
                + json.dumps(
                    str(base), ensure_ascii=False
                ),
                argv,
            )
            encoded = json.dumps(
                list(server.args),
                ensure_ascii=False,
            )
            self.assertTrue(
                any(
                    arg.endswith(
                        "args=" + encoded
                    )
                    for arg in argv
                )
            )
            self.assertNotIn(
                "shell", spawn.call_args.kwargs
            )

    def test_mcp_binding_changes_with_mode(self):
        """Selecciona MCP por modo."""
        import sys

        from pxp_harness.mcp import (
            AddMCP,
            MCPServer,
        )

        with (
            tempfile.TemporaryDirectory() as temp
        ):
            root = Path(temp)
            initialize(root)
            AddMCP(
                "plan",
                MCPServer("docs", sys.executable),
            ).execute(root)
            fake = FakeStrategy()
            main(
                ["chat"], cwd=root, strategy=fake
            )
            self.assertEqual(
                [
                    s.name
                    for s in fake.requests[
                        -1
                    ].servers
                ],
                ["docs"],
            )
            main(["mode", "design"], cwd=root)
            main(
                ["chat"], cwd=root, strategy=fake
            )
            self.assertEqual(
                fake.requests[-1].servers, ()
            )
