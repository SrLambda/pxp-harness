"""Verificación estricta del ancho del código."""

import unittest
from pathlib import Path


class QualityTests(unittest.TestCase):
    """No permite excepciones por URL o cadena."""

    def test_python_lines_fit(self):
        """Limita todo Python a 50 columnas."""
        root = Path(__file__).resolve().parents[1]
        for directory in ("src", "tests"):
            for path in (root / directory).rglob(
                "*.py"
            ):
                lines = path.read_text(
                    encoding="utf-8"
                ).splitlines()
                for number, line in enumerate(
                    lines, 1
                ):
                    with self.subTest(
                        path=path, line=number
                    ):
                        self.assertLessEqual(
                            len(
                                line.expandtabs(8)
                            ),
                            50,
                        )
