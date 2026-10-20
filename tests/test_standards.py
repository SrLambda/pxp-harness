"""Pruebas de estándares por proyecto."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pxp_harness.project import (
    ProjectError,
    initialize,
)
from pxp_harness.standards import (
    configure,
    load_standards,
    run_checks,
)


class StandardsTests(unittest.TestCase):
    """Comprueba perfiles, límites y seguridad."""

    def setUp(self):
        """Crea un proyecto aislado."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        initialize(self.root)

    def test_legacy_defaults_do_not_write(self):
        """Lee sin migrar archivos."""
        value = load_standards(self.root)
        self.assertEqual(value["line_length"], 50)
        path = self.root / ".pxp/standards.json"
        self.assertFalse(path.exists())

    def test_profile_overrides_persist(self):
        """Conserva cada perfil."""
        configure(self.root, "wide", 79, "en")
        value = load_standards(self.root)
        self.assertEqual(value["profile"], "wide")
        self.assertEqual(value["line_length"], 79)
        self.assertEqual(
            value["doc_language"], "en"
        )
        configure(
            self.root, "default", None, None
        )
        self.assertEqual(
            load_standards(self.root)[
                "line_length"
            ],
            50,
        )

    def test_invalid_config_is_rejected(self):
        """No acepta booleanos como longitudes."""
        path = self.root / ".pxp/standards.json"
        path.write_text(
            json.dumps(
                {
                    "active_profile": "bad",
                    "profiles": {
                        "bad": {
                            "line_length": True,
                            "doc_language": "es",
                        }
                    },
                }
            )
        )
        with self.assertRaises(ProjectError):
            load_standards(self.root)

    def test_missing_ruff_does_not_modify(self):
        """La ausencia de Ruff es accionable."""
        with patch(
            (
                "pxp_harness.standards."
                "shutil.which"
            ),
            return_value=None,
        ):
            with self.assertRaises(ProjectError):
                run_checks(self.root, apply=True)

    def test_strict_limit_includes_long_urls(
        self,
    ):
        """No permite excepciones de E501."""
        source = self.root / "example.py"
        source.write_text("# https://" + "a" * 60)
        with (
            patch(
                (
                    "pxp_harness.standards."
                    "shutil.which"
                ),
                return_value="/usr/bin/ruff",
            ),
            patch(
                (
                    "pxp_harness.standards."
                    "subprocess.run"
                ),
            ) as run,
        ):
            run.return_value.returncode = 0
            self.assertEqual(
                run_checks(self.root), 1
            )

    def test_symlink_config_is_rejected(self):
        """Rechaza enlaces de configuración."""
        external = self.root / "external.json"
        external.write_text("{}")
        path = self.root / ".pxp/standards.json"
        path.symlink_to(external)
        with self.assertRaises(ProjectError):
            configure(
                self.root, "default", 79, None
            )

    def test_unknown_active_is_rejected(self):
        """Rechaza perfiles inexistentes."""
        path = self.root / ".pxp/standards.json"
        path.write_text(
            json.dumps(
                {
                    "active_profile": "missing",
                    "profiles": {
                        "default": {
                            "line_length": 50,
                            "doc_language": "es",
                        }
                    },
                }
            )
        )
        with self.assertRaises(ProjectError):
            load_standards(self.root)

    def test_unknown_fields_are_rejected(self):
        """No ejecuta comandos configurados."""
        path = self.root / ".pxp/standards.json"
        path.write_text('{"command": "echo hi"}')
        with self.assertRaises(ProjectError):
            load_standards(self.root)

    def test_invalid_names_do_not_write(self):
        """Rechaza nombres con rutas."""
        with self.assertRaises(ProjectError):
            configure(
                self.root, "../bad", 50, "es"
            )
        self.assertFalse(
            (
                self.root / ".pxp/standards.json"
            ).exists()
        )

    def test_init_preserves_standards(self):
        """Inicializar conserva perfiles."""
        configure(self.root, "wide", 79, "en")
        path = self.root / ".pxp/standards.json"
        before = path.read_bytes()
        initialize(self.root)
        self.assertEqual(
            before, path.read_bytes()
        )

    def test_source_symlinks_are_excluded(self):
        """No edita archivos enlazados."""
        from pxp_harness.standards import (
            python_files,
        )

        source = self.root / "sample.py"
        source.write_text("x=1\n")
        (self.root / "linked.py").symlink_to(
            source
        )
        self.assertEqual(
            python_files(self.root), [source]
        )

    def test_malformed_json_is_rejected(self):
        """No reemplaza JSON dañado."""
        path = self.root / ".pxp/standards.json"
        path.write_text("{")
        with self.assertRaises(ProjectError):
            configure(
                self.root, "default", 50, "es"
            )
        self.assertEqual(path.read_text(), "{")

    def test_invalid_profile_values(self):
        """Valida tipos y límites."""
        for length in (True, 0, 321, "50"):
            with self.subTest(length=length):
                with self.assertRaises(
                    ProjectError
                ):
                    configure(
                        self.root,
                        "bad",
                        length,
                        "es",
                    )
        with self.assertRaises(ProjectError):
            configure(self.root, "bad", 50, [])

    def test_real_ruff_apply_and_check(self):
        """Comprueba Ruff real si existe."""
        import shutil

        if shutil.which("ruff") is None:
            self.skipTest("Ruff is not installed")
        source = self.root / "sample.py"
        source.write_text(
            '"""Módulo de ejemplo."""\nvalue=1\n',
            encoding="utf-8",
        )
        before = source.read_bytes()
        self.assertEqual(run_checks(self.root), 1)
        self.assertEqual(
            source.read_bytes(), before
        )
        self.assertEqual(
            run_checks(self.root, apply=True), 0
        )
        self.assertIn(
            "value = 1", source.read_text()
        )
        self.assertEqual(run_checks(self.root), 0)
