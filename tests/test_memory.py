"""Memoria explícita y aislada por proyecto."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pxp_harness.cli import main
from pxp_harness.project import initialize


class MemoryTests(unittest.TestCase):
    """No modifica la configuración global."""

    def setUp(self):
        """Crea un proyecto temporal."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        initialize(self.root)

    def test_disabled_preserves_chat(self):
        """No añade herramientas sin activar."""
        from pxp_harness.codex import (
            memory_arguments as arguments,
        )

        self.assertEqual(arguments(self.root), [])

    def test_enable_and_disable(self):
        """Guarda solo la preferencia local."""
        executable = Path(__file__).resolve()
        self.assertEqual(
            main(
                [
                    "memory",
                    "enable",
                    "--executable",
                    str(executable),
                ],
                cwd=self.root,
            ),
            1,
        )
        with patch(
            "pxp_harness.memory.os.access",
            return_value=True,
        ):
            self.assertEqual(
                main(
                    [
                        "memory",
                        "enable",
                        "--executable",
                        str(executable),
                    ],
                    cwd=self.root,
                ),
                0,
            )
        self.assertEqual(
            main(
                ["memory", "disable"],
                cwd=self.root,
            ),
            0,
        )
        data = json.loads(
            (
                self.root / ".pxp/memory.json"
            ).read_text()
        )
        self.assertFalse(data["enabled"])

    def test_malformed_fails_closed(self):
        """No ignora configuración incorrecta."""
        from pxp_harness.codex import (
            memory_arguments as arguments,
        )
        from pxp_harness.project import (
            ProjectError,
        )

        (
            self.root / ".pxp/memory.json"
        ).write_text('{"enabled": "false"}')
        with self.assertRaises(ProjectError):
            arguments(self.root)

    def test_project_argv_and_global_isolation(
        self,
    ):
        """Conserva prompt y config global."""
        import os
        from subprocess import CompletedProcess

        import pxp_harness.codex as cli

        other = self.root / "second project"
        other.mkdir()
        initialize(other)
        sentinel = self.root / "global.toml"
        sentinel.write_bytes(b"global sentinel")
        binary = str(Path(__file__).resolve())
        with patch(
            "pxp_harness.memory.os.access",
            return_value=True,
        ):
            main(
                [
                    "memory",
                    "enable",
                    "--executable",
                    binary,
                ],
                cwd=self.root,
            )
            main(
                [
                    "memory",
                    "enable",
                    "--executable",
                    binary,
                ],
                cwd=other,
            )
            from pxp_harness.codex import (
                memory_arguments as arguments,
            )

            first = arguments(self.root)
            second = arguments(other)
            self.assertIn(
                'ENGRAM_CLOUD_AUTOSYNC = "0"',
                " ".join(first),
            )
            self.assertNotEqual(first, second)
            self.assertIn(
                str(self.root / ".pxp/engram"),
                " ".join(first),
            )
            with (
                patch.dict(
                    os.environ,
                    {
                        "CODEX_HOME": str(
                            self.root
                        )
                    },
                ),
                patch.object(
                    cli.shutil,
                    "which",
                    return_value="/codex",
                ),
                patch.object(
                    cli.subprocess,
                    "run",
                    return_value=CompletedProcess(
                        [], 0
                    ),
                ) as launch,
            ):
                self.assertEqual(
                    main(
                        ["chat", "hello"],
                        cwd=self.root,
                    ),
                    0,
                )
            argv = launch.call_args.args[0]
            self.assertTrue(
                argv[-1].endswith(
                    "User request: hello"
                )
            )
            self.assertNotIn(
                "mem_search", argv[-1]
            )
        self.assertEqual(
            sentinel.read_bytes(),
            b"global sentinel",
        )
        self.assertFalse(
            (self.root / ".codex").exists()
        )

    def test_symlink_database_is_rejected(self):
        """No redirige la memoria."""
        from pxp_harness.codex import (
            memory_arguments as arguments,
        )
        from pxp_harness.project import (
            ProjectError,
        )

        (self.root / ".pxp/engram").symlink_to(
            self.root, target_is_directory=True
        )
        with self.assertRaises(ProjectError):
            arguments(self.root)
