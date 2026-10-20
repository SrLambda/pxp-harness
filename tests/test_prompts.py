"""Pruebas de instrucciones base por modo."""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from pxp_harness.cli import main
from pxp_harness.project import (
    ProjectError,
    initialize,
)
from pxp_harness.prompts import (
    clear_prompt,
    load_prompt,
    set_prompt,
)


class PromptTests(unittest.TestCase):
    """Valida archivos y lanzamiento de Codex."""

    def setUp(self):
        """Crea un proyecto temporal."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        initialize(self.root)
        self.source = self.root / "mi prompt.txt"
        self.source.write_text(
            "Instrucción base privada.\n",
            encoding="utf-8",
        )

    def cli(self, *args):
        """Ejecuta un comando en el proyecto."""
        return main(list(args), cwd=self.root)

    def test_unconfigured_is_unchanged(self):
        """No crea configuración al consultar."""
        self.assertIsNone(
            load_prompt(self.root, "plan")
        )
        path = self.root / ".pxp/prompts.json"
        self.assertFalse(path.exists())

    def test_set_relative_and_clear(self):
        """Persiste rutas portátiles por modo."""
        set_prompt(
            self.root, "plan", str(self.source)
        )
        path = self.root / ".pxp/prompts.json"
        data = json.loads(path.read_text())
        self.assertEqual(
            data, {"plan": "mi prompt.txt"}
        )
        self.assertEqual(
            load_prompt(self.root, "plan"),
            self.source,
        )
        clear_prompt(self.root, "plan")
        self.assertIsNone(
            load_prompt(self.root, "plan")
        )
        self.assertTrue(self.source.exists())

    def test_chat_uses_native_override(self):
        """Separa instrucciones de la petición."""
        name = "base " + chr(92) + '"ñ🙂".txt'
        source = self.root / name
        source.write_text("BASE_SECRET")
        set_prompt(self.root, "plan", str(source))
        with (
            patch(
                "pxp_harness.cli.shutil.which",
                return_value="/usr/bin/codex",
            ),
            patch(
                "pxp_harness.cli.subprocess.run",
                return_value=CompletedProcess(
                    [], 0
                ),
            ) as run,
        ):
            self.assertEqual(
                self.cli("chat", "user request"),
                0,
            )
        argv = run.call_args.args[0]
        self.assertEqual(
            argv[:2], ["/usr/bin/codex", "-c"]
        )
        self.assertEqual(
            argv[2],
            "model_instructions_file="
            + json.dumps(
                str(source), ensure_ascii=False
            ),
        )
        if sys.version_info >= (3, 11):
            import tomllib

            parsed = tomllib.loads(argv[2])
            self.assertEqual(
                parsed["model_instructions_file"],
                str(source),
            )
        self.assertIn("user request", argv[-1])
        self.assertNotIn("BASE_SECRET", argv[-1])
        self.assertNotIn(
            "developer_instructions",
            " ".join(argv),
        )
        self.assertEqual(
            run.call_args.kwargs["cwd"], self.root
        )
        self.assertNotIn(
            "shell", run.call_args.kwargs
        )

    def test_revalidate_before_launch(self):
        """Revalida archivos antes de iniciar."""
        set_prompt(
            self.root, "plan", str(self.source)
        )
        self.source.unlink()
        with patch(
            "pxp_harness.cli.subprocess.run"
        ) as run:
            self.assertEqual(
                self.cli("chat", "hi"), 1
            )
        run.assert_not_called()

    def test_invalid_files_do_not_write(self):
        """Rechaza contenido inválido."""
        for content in (
            b"",
            b"  \n",
            b"\xff",
            b"x\x00",
        ):
            self.source.write_bytes(content)
            with self.subTest(content=content):
                with self.assertRaises(
                    ProjectError
                ):
                    set_prompt(
                        self.root,
                        "plan",
                        "mi prompt.txt",
                    )
        with self.assertRaises(ProjectError):
            set_prompt(self.root, "plan", ".")
        path = self.root / ".pxp/prompts.json"
        self.assertFalse(path.exists())

    def test_unknown_modes_are_rejected(self):
        """No guarda modos desconocidos."""
        with self.assertRaises(ProjectError):
            set_prompt(
                self.root,
                "unknown",
                "mi prompt.txt",
            )

    def test_escape_and_symlinks_are_rejected(
        self,
    ):
        """Rechaza enlaces y rutas externas."""
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "external.txt"
            outside.write_text("EXTERNAL")
            with self.assertRaises(ProjectError):
                set_prompt(
                    self.root,
                    "plan",
                    str(outside),
                )
            linked = self.root / "linked.txt"
            linked.symlink_to(outside)
            with self.assertRaises(ProjectError):
                set_prompt(
                    self.root,
                    "plan",
                    "linked.txt",
                )

    def test_invalid_config_does_not_launch(self):
        """No filtra contenido al fallar JSON."""
        path = self.root / ".pxp/prompts.json"
        for text in (
            "{SECRET",
            "[]",
            '{"plan": []}',
            '{"unknown": "x"}',
        ):
            path.write_text(text)
            with patch(
                "pxp_harness.cli.subprocess.run"
            ) as run:
                self.assertEqual(
                    self.cli("chat", "hi"), 1
                )
            run.assert_not_called()

    def test_cli_set_show_clear(self):
        """Permite configurar sin editar JSON."""
        self.assertEqual(
            self.cli(
                "prompt",
                "set",
                "plan",
                "mi prompt.txt",
            ),
            0,
        )
        self.assertEqual(
            self.cli("prompt", "show"), 0
        )
        self.assertEqual(
            self.cli("prompt", "show", "plan"), 0
        )
        self.assertEqual(
            self.cli("prompt", "clear", "plan"), 0
        )

    def test_mode_changes_next_launch_only(self):
        """Cambiar modo no inicia procesos."""
        second = self.root / "design.txt"
        second.write_text("OTHER_BASE")
        set_prompt(
            self.root, "plan", "mi prompt.txt"
        )
        set_prompt(
            self.root, "design", "design.txt"
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
            self.cli("mode", "design")
            run.assert_not_called()
            self.cli("chat", "task")
        argv = run.call_args.args[0]
        self.assertIn(str(second), argv[2])
        self.assertNotIn("OTHER_BASE", argv[-1])

    def test_config_symlink_is_rejected(self):
        """No modifica configuración enlazada."""
        target = self.root / "existing.json"
        target.write_text("{}")
        config = self.root / ".pxp/prompts.json"
        config.symlink_to(target)
        with self.assertRaises(ProjectError):
            set_prompt(
                self.root, "plan", "mi prompt.txt"
            )
        self.assertEqual(target.read_text(), "{}")

    def test_unreadable_prompt_never_launches(
        self,
    ):
        """Falla antes de ejecutar Codex."""
        set_prompt(
            self.root, "plan", "mi prompt.txt"
        )
        original = Path.open
        source = self.source

        def read(path, *args, **kwargs):
            """Simula lectura denegada."""
            if path == source:
                raise PermissionError("PRIVATE")
            return original(path, *args, **kwargs)

        with (
            patch.object(Path, "open", read),
            patch(
                "pxp_harness.cli.subprocess.run"
            ) as run,
        ):
            self.assertEqual(
                self.cli("chat", "task"), 1
            )
        run.assert_not_called()

    def test_large_prompt_is_rejected(self):
        """Limita la lectura del archivo."""
        self.source.write_bytes(
            b"a" * (1024**2 + 1)
        )
        with self.assertRaises(ProjectError):
            set_prompt(
                self.root, "plan", "mi prompt.txt"
            )

    def test_other_mode_can_be_unconfigured(self):
        """No exige configurar los nueve modos."""
        set_prompt(
            self.root, "design", "mi prompt.txt"
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
            self.cli("chat", "task")
        argv = run.call_args.args[0]
        self.assertEqual(len(argv), 2)
        self.assertNotIn("-c", argv)

    def test_errors_do_not_print_prompt_text(
        self,
    ):
        """No revela texto rechazado."""
        set_prompt(
            self.root, "plan", "mi prompt.txt"
        )
        self.source.write_bytes(b"SECRET\x00")
        error = io.StringIO()
        with (
            redirect_stderr(error),
            patch(
                "pxp_harness.cli.subprocess.run"
            ) as run,
        ):
            self.assertEqual(
                self.cli("chat", "task"), 1
            )
        run.assert_not_called()
        self.assertNotIn(
            "SECRET", error.getvalue()
        )
        self.assertNotIn(
            str(self.source), error.getvalue()
        )

    def test_set_preserves_existing_work(self):
        """No cambia estándares ni otros modos."""
        config = self.root / ".pxp/config.json"
        before = config.read_bytes()
        source = self.source.read_bytes()
        set_prompt(
            self.root, "plan", "mi prompt.txt"
        )
        set_prompt(
            self.root, "design", "mi prompt.txt"
        )
        initialize(self.root)
        clear_prompt(self.root, "plan")
        self.assertEqual(
            config.read_bytes(), before
        )
        self.assertEqual(
            self.source.read_bytes(), source
        )
        self.assertEqual(
            load_prompt(self.root, "design"),
            self.source,
        )

    def test_del_path_is_rejected(self):
        """Rechaza DEL en nombres de archivo."""
        name = "base" + chr(127) + ".txt"
        (self.root / name).write_text("BASE")
        with self.assertRaises(ProjectError):
            set_prompt(self.root, "plan", name)
        config = self.root / ".pxp/prompts.json"
        self.assertFalse(config.exists())

    def test_saved_del_path_never_launches(self):
        """Rechaza DEL también desde JSON."""
        name = "base" + chr(127) + ".txt"
        (self.root / name).write_text("BASE")
        config = self.root / ".pxp/prompts.json"
        config.write_text(
            json.dumps(
                {
                    "plan": name,
                }
            )
        )
        with patch(
            "pxp_harness.cli.subprocess.run"
        ) as run:
            self.assertEqual(
                self.cli("chat", "task"), 1
            )
        run.assert_not_called()
