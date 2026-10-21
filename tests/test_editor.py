"""Pruebas de edición y lectura con NeoVim."""

import os
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from pxp_harness.cli import main
from pxp_harness.project import initialize
from pxp_harness.prompts import (
    load_prompt,
    set_prompt,
)


class EditorTests(unittest.TestCase):
    """No inicia editores ni modelos reales."""

    def setUp(self):
        """Crea un proyecto temporal."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        initialize(self.root)

    def cli(self, *args):
        """Ejecuta comandos en el proyecto."""
        return main(list(args), cwd=self.root)

    def test_edit_creates_valid_association(self):
        """Asocia tras guardar texto válido."""

        def save(argv, **kwargs):
            """Simula guardar texto."""
            Path(argv[-1]).write_text("BASE")
            return CompletedProcess(argv, 0)

        with (
            patch(
                "pxp_harness.editor.shutil.which",
                return_value="/usr/bin/nvim",
            ),
            patch(
                (
                    "pxp_harness.editor."
                    "subprocess.run"
                ),
                side_effect=save,
            ) as run,
        ):
            self.assertEqual(
                self.cli("prompt", "edit"), 0
            )
        path = self.root / ".pxp/prompts/plan.md"
        self.assertEqual(
            load_prompt(self.root, "plan"), path
        )
        self.assertEqual(
            run.call_args.args[0],
            ["/usr/bin/nvim", "--", str(path)],
        )
        self.assertIs(
            run.call_args.kwargs["shell"], False
        )

    def test_cancel_keeps_unconfigured_draft(
        self,
    ):
        """No activa borradores vacíos."""
        with (
            patch(
                "pxp_harness.editor.shutil.which",
                return_value="nvim",
            ),
            patch(
                (
                    "pxp_harness.editor."
                    "subprocess.run"
                ),
                return_value=CompletedProcess(
                    [], 0
                ),
            ),
        ):
            self.assertEqual(
                self.cli("prompt", "edit"), 1
            )
        self.assertIsNone(
            load_prompt(self.root, "plan")
        )
        path = self.root / ".pxp/prompts/plan.md"
        self.assertEqual(path.read_text(), "")

    def test_missing_nvim_creates_no_draft(self):
        """No escribe si falta NeoVim."""
        with patch(
            "pxp_harness.editor.shutil.which",
            return_value=None,
        ):
            self.assertEqual(
                self.cli("prompt", "edit"), 1
            )
        self.assertFalse(
            (self.root / ".pxp/prompts").exists()
        )

    def test_editor_failure_does_not_associate(
        self,
    ):
        """Conserva el borrador sin activarlo."""
        with (
            patch(
                "pxp_harness.editor.shutil.which",
                return_value="nvim",
            ),
            patch(
                (
                    "pxp_harness.editor."
                    "subprocess.run"
                ),
                return_value=CompletedProcess(
                    [], 7
                ),
            ),
        ):
            self.assertEqual(
                self.cli("prompt", "edit"), 7
            )
        self.assertIsNone(
            load_prompt(self.root, "plan")
        )

    def test_view_is_readonly_and_preserves_files(
        self,
    ):
        """Consulta sin modificar archivos."""
        source = self.root / "mi base ñ.txt"
        source.write_text("BASE")
        set_prompt(self.root, "plan", str(source))
        config = self.root / ".pxp/prompts.json"
        before = config.read_bytes()
        with (
            patch(
                "pxp_harness.editor.shutil.which",
                return_value="/usr/bin/nvim",
            ),
            patch(
                (
                    "pxp_harness.editor."
                    "subprocess.run"
                ),
                return_value=CompletedProcess(
                    [], 0
                ),
            ) as run,
        ):
            self.assertEqual(
                self.cli(
                    "prompt", "view", "plan"
                ),
                0,
            )
        self.assertEqual(
            run.call_args.args[0],
            [
                "/usr/bin/nvim",
                "--clean",
                "-R",
                "-M",
                "-n",
                "-i",
                "NONE",
                "--",
                str(source),
            ],
        )
        self.assertEqual(
            source.read_text(), "BASE"
        )
        self.assertEqual(
            config.read_bytes(), before
        )

    def test_unconfigured_view_starts_no_editor(
        self,
    ):
        """No crea un archivo al consultar."""
        with (
            patch(
                "pxp_harness.editor.shutil.which",
                return_value="nvim",
            ),
            patch(
                (
                    "pxp_harness.editor."
                    "subprocess.run"
                ),
            ) as run,
        ):
            self.assertEqual(
                self.cli("prompt", "view"), 1
            )
        run.assert_not_called()
        self.assertFalse(
            (self.root / ".pxp/prompts").exists()
        )

    def test_existing_draft_is_not_overwritten(
        self,
    ):
        """Conserva borradores previos."""
        path = self.root / ".pxp/prompts/plan.md"
        path.parent.mkdir()
        path.write_text("MY DRAFT")
        with (
            patch(
                "pxp_harness.editor.shutil.which",
                return_value="nvim",
            ),
            patch(
                (
                    "pxp_harness.editor."
                    "subprocess.run"
                ),
                return_value=CompletedProcess(
                    [], 0
                ),
            ),
        ):
            self.assertEqual(
                self.cli("prompt", "edit"), 0
            )
        self.assertEqual(
            path.read_text(), "MY DRAFT"
        )

    def test_draft_symlink_is_rejected(self):
        """No escribe fuera del proyecto."""
        outside = self.root / "external"
        outside.mkdir()
        directory = self.root / ".pxp/prompts"
        directory.symlink_to(outside)
        with (
            patch(
                "pxp_harness.editor.shutil.which",
                return_value="nvim",
            ),
            patch(
                (
                    "pxp_harness.editor."
                    "subprocess.run"
                ),
            ) as run,
        ):
            self.assertEqual(
                self.cli("prompt", "edit"), 1
            )
        run.assert_not_called()
        self.assertEqual(
            list(outside.iterdir()), []
        )

    def test_chat_uses_native_tui_and_neovim(
        self,
    ):
        """Conserva la TUI nativa de Codex."""
        original = dict(os.environ)
        with (
            patch(
                "pxp_harness.codex.shutil.which",
                return_value="/usr/bin/codex",
            ),
            patch(
                "pxp_harness.codex."
                "subprocess.run",
                return_value=CompletedProcess(
                    [], 0
                ),
            ) as run,
        ):
            self.assertEqual(
                self.cli("chat", "task"), 0
            )
        args = run.call_args.args[0]
        kwargs = run.call_args.kwargs
        self.assertEqual(
            args[0], "/usr/bin/codex"
        )
        self.assertNotIn("exec", args)
        self.assertEqual(
            kwargs["env"]["EDITOR"], "nvim"
        )
        self.assertEqual(
            kwargs["env"]["VISUAL"], "nvim"
        )
        self.assertNotIn("capture_output", kwargs)
        self.assertNotIn("stdin", kwargs)
        self.assertEqual(
            dict(os.environ), original
        )

    def test_editor_launch_error_keeps_draft(
        self,
    ):
        """No activa texto si el proceso falla."""
        with (
            patch(
                "pxp_harness.editor.shutil.which",
                return_value="nvim",
            ),
            patch(
                (
                    "pxp_harness.editor."
                    "subprocess.run"
                ),
                side_effect=OSError(
                    "cannot launch"
                ),
            ),
        ):
            self.assertEqual(
                self.cli("prompt", "edit"), 1
            )
        self.assertIsNone(
            load_prompt(self.root, "plan")
        )
        self.assertTrue(
            (
                self.root / ".pxp/prompts/plan.md"
            ).is_file()
        )

    def test_edit_can_repair_empty_prompt(self):
        """Repara texto sin cambiar rutas."""
        source = self.root / "existing.txt"
        source.write_text("BASE")
        set_prompt(self.root, "plan", str(source))
        config = self.root / ".pxp/prompts.json"
        before = config.read_bytes()
        source.write_text("")

        def save(argv, **kwargs):
            """Simula una corrección manual."""
            Path(argv[-1]).write_text("FIXED")
            return CompletedProcess(argv, 0)

        with (
            patch(
                "pxp_harness.editor.shutil.which",
                return_value="nvim",
            ),
            patch(
                (
                    "pxp_harness.editor."
                    "subprocess.run"
                ),
                side_effect=save,
            ),
        ):
            self.assertEqual(
                self.cli("prompt", "edit"), 0
            )
        self.assertEqual(
            config.read_bytes(), before
        )
        self.assertEqual(
            source.read_text(), "FIXED"
        )

    def test_edit_uses_active_mode(self):
        """Usa el modo activo."""
        self.cli("mode", "design")

        def save(argv, **kwargs):
            """Simula guardar el borrador."""
            Path(argv[-1]).write_text("DESIGN")
            return CompletedProcess(argv, 0)

        with (
            patch(
                "pxp_harness.editor.shutil.which",
                return_value="nvim",
            ),
            patch(
                (
                    "pxp_harness.editor."
                    "subprocess.run"
                ),
                side_effect=save,
            ),
        ):
            self.assertEqual(
                self.cli("prompt", "edit"), 0
            )
        self.assertEqual(
            load_prompt(self.root, "design"),
            self.root / ".pxp/prompts/design.md",
        )
        self.assertIsNone(
            load_prompt(self.root, "plan")
        )

    def test_draft_file_symlink_is_rejected(self):
        """No modifica destinos de enlaces."""
        source = self.root / "external.txt"
        source.write_text("KEEP")
        directory = self.root / ".pxp/prompts"
        directory.mkdir()
        (directory / "plan.md").symlink_to(source)
        with (
            patch(
                "pxp_harness.editor.shutil.which",
                return_value="nvim",
            ),
            patch(
                (
                    "pxp_harness.editor."
                    "subprocess.run"
                ),
            ) as run,
        ):
            self.assertEqual(
                self.cli("prompt", "edit"), 1
            )
        run.assert_not_called()
        self.assertEqual(
            source.read_text(), "KEEP"
        )

    def test_interrupt_keeps_draft(
        self,
    ):
        """Cancelar no activa el borrador."""
        with (
            patch(
                "pxp_harness.editor.shutil.which",
                return_value="nvim",
            ),
            patch(
                (
                    "pxp_harness.editor."
                    "subprocess.run"
                ),
                side_effect=KeyboardInterrupt,
            ),
        ):
            self.assertEqual(
                self.cli("prompt", "edit"), 130
            )
        self.assertIsNone(
            load_prompt(self.root, "plan")
        )
