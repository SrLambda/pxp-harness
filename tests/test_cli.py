"""Pruebas de la interfaz de terminal."""

import json
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from pxp_harness.cli import main
from pxp_harness.project import ARTIFACTS, MODES


class CliTests(unittest.TestCase):
    """Comprueba los comandos del proyecto."""

    def setUp(self):
        """Prepara un proyecto temporal."""
        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        """Elimina el proyecto temporal."""
        self.temp_dir.cleanup()

    def run_cli(self, *args):
        """Ejecuta un comando aislado."""
        return main(list(args), cwd=self.root)

    def test_init_templates(
        self,
    ):
        """Comprueba el resultado esperado."""
        self.assertEqual(self.run_cli("init"), 0)
        config = json.loads(
            (
                self.root / ".pxp/config.json"
            ).read_text()
        )
        self.assertEqual(
            config["active_mode"], "plan"
        )
        self.assertEqual(
            set(config["artifacts"]),
            set(ARTIFACTS),
        )
        for filename in ARTIFACTS.values():
            self.assertTrue(
                (
                    self.root
                    / ".pxp/artifacts"
                    / filename
                ).is_file()
            )

    def test_init_preserves_content(
        self,
    ):
        """Comprueba el resultado esperado."""
        self.run_cli("init")
        artifact = (
            self.root
            / ".pxp/artifacts/requirements.md"
        )
        artifact.write_text("User requirements\n")
        self.run_cli("init")
        self.assertEqual(
            artifact.read_text(),
            "User requirements\n",
        )

    def test_mode_lists_nine_distinct_modes(self):
        """Comprueba el resultado esperado."""
        self.run_cli("init")
        self.assertEqual(self.run_cli("mode"), 0)
        self.assertEqual(len(MODES), 9)
        self.assertEqual(
            len({mode["id"] for mode in MODES}), 9
        )

    def test_mode_sets_and_persists_a_mode(self):
        """Comprueba el resultado esperado."""
        self.run_cli("init")
        self.assertEqual(
            self.run_cli(
                "mode", "implementation-code"
            ),
            0,
        )
        config = json.loads(
            (
                self.root / ".pxp/config.json"
            ).read_text()
        )
        self.assertEqual(
            config["active_mode"],
            "implementation-code",
        )

    def test_mode_rejects_unknown_id(self):
        """Comprueba el resultado esperado."""
        self.run_cli("init")
        self.assertEqual(
            self.run_cli("mode", "not-a-mode"), 2
        )

    def test_chat_context(
        self,
    ):
        """Comprueba el resultado esperado."""
        self.run_cli("init")
        with patch(
            "pxp_harness.cli.shutil.which",
            return_value="/usr/bin/codex",
        ):
            with patch(
                "pxp_harness.cli.subprocess.run",
                return_value=CompletedProcess(
                    [], 0
                ),
            ) as run:
                self.assertEqual(
                    self.run_cli(
                        "chat", "Help me plan"
                    ),
                    0,
                )
        args, kwargs = run.call_args
        self.assertEqual(
            args[0][0], "/usr/bin/codex"
        )
        self.assertEqual(kwargs["cwd"], self.root)
        self.assertNotIn("shell", kwargs)
        prompt = args[0][-1]
        self.assertIn("plan", prompt)
        for filename in ARTIFACTS.values():
            self.assertIn(filename, prompt)
        self.assertIn("Help me plan", prompt)

    def test_chat_missing_codex(
        self,
    ):
        """Comprueba el resultado esperado."""
        self.run_cli("init")
        with patch(
            "pxp_harness.cli.shutil.which",
            return_value=None,
        ):
            self.assertEqual(
                self.run_cli("chat", "hello"), 1
            )

    def test_commands_require_initialization(
        self,
    ):
        """Comprueba el resultado esperado."""
        self.assertEqual(self.run_cli("mode"), 1)
        self.assertEqual(
            self.run_cli("chat", "hello"), 1
        )

    def test_standards_configure(self):
        """Configura y muestra el perfil local."""
        self.run_cli("init")
        self.assertEqual(
            self.run_cli(
                "standards",
                "configure",
                "--profile",
                "wide",
                "--line-length",
                "79",
                "--doc-language",
                "en",
            ),
            0,
        )
        self.assertEqual(
            self.run_cli("standards"), 0
        )

    def test_standards_reject_overrides(self):
        """Rechaza ajustes implícitos."""
        self.run_cli("init")
        self.assertEqual(
            self.run_cli(
                "standards",
                "check",
                "--line-length",
                "79",
            ),
            1,
        )

    def test_chat_includes_profile(self):
        """Transmite el perfil a Codex."""
        self.run_cli("init")
        self.run_cli(
            "standards",
            "configure",
            "--profile",
            "wide",
            "--line-length",
            "79",
        )
        with (
            patch(
                "pxp_harness.cli.shutil.which",
                return_value="codex",
            ),
            patch(
                "pxp_harness.cli.subprocess.run",
                return_value=CompletedProcess(
                    [], 0
                ),
            ) as run,
        ):
            self.run_cli("chat", "continue")
        prompt = run.call_args.args[0][-1]
        self.assertIn("79 columns", prompt)
        self.assertIn("profile: wide", prompt)


if __name__ == "__main__":
    unittest.main()
