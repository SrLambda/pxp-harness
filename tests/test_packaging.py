"""Pruebas de paquetes nativos sin instalación."""

import gzip
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from importlib.util import (
    module_from_spec,
    spec_from_file_location,
)
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/package.py"


def deb_members(path):
    """Lee el archivo ar independiente."""
    result = {}
    with path.open("rb") as source:
        if source.read(8) != b"!<arch>\n":
            raise AssertionError(
                "Invalid ar archive"
            )
        while header := source.read(60):
            if len(header) != 60:
                raise AssertionError(
                    "Invalid header"
                )
            name = (
                header[:16]
                .decode()
                .strip()
                .rstrip("/")
            )
            name = name.strip()
            size = int(header[48:58].strip())
            result[name] = source.read(size)
            if size % 2:
                source.read(1)
    return result


@unittest.skipIf(
    sys.version_info < (3, 11),
    "Native builder requires Python 3.11+",
)
class PackagingTests(unittest.TestCase):
    """Comprueba archivos y staging."""

    def setUp(self):
        """Prepara salidas aisladas."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "out"

    def build(self, output=None):
        """Construye sin red ni privilegios."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "build",
                "--output",
                str(output or self.output),
                "--epoch",
                "1700000000",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            result.returncode, 0, result.stderr
        )

    def test_deb_and_source_are_reproducible(
        self,
    ):
        """Comprueba bytes reproducibles."""
        self.build()
        other = Path(self.temp.name) / "second"
        self.build(other)
        for path in self.output.glob("*"):
            if path.suffix in {".deb", ".gz"}:
                self.assertEqual(
                    path.read_bytes(),
                    (
                        other / path.name
                    ).read_bytes(),
                )

    def test_deb_content_and_staged_launcher(
        self,
    ):
        """Comprueba el paquete sin instalar."""
        self.build()
        package = next(self.output.glob("*.deb"))
        entries = deb_members(package)
        self.assertEqual(
            entries["debian-binary"], b"2.0\n"
        )
        with tarfile.open(
            fileobj=io.BytesIO(
                gzip.decompress(
                    entries["control.tar.gz"]
                )
            )
        ) as archive:
            control = (
                archive.extractfile("control")
                .read()
                .decode()
            )
            self.assertIn(
                "Architecture: all", control
            )
            self.assertIn(
                "Depends: python3 (>= 3.10)",
                control,
            )
        stage = Path(self.temp.name) / "stage"
        with tarfile.open(
            fileobj=io.BytesIO(
                gzip.decompress(
                    entries["data.tar.gz"]
                )
            )
        ) as archive:
            names = archive.getnames()
            for member in archive.getmembers():
                self.assertEqual(member.uid, 0)
                self.assertEqual(member.gid, 0)
            archive.extractall(
                stage, filter="data"
            )
        launcher = stage / "usr/bin/pxp"
        self.assertTrue(
            launcher.stat().st_mode & 0o111
        )
        result = subprocess.run(
            [
                sys.executable,
                str(launcher),
                "--help",
            ],
            cwd=self.temp.name,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("prompt", result.stdout)
        self.assertFalse(
            any(
                "/.codex/" in name
                or "/.pxp/" in name
                for name in names
            )
        )
        self.assertFalse(
            any(
                name.endswith(".pyc")
                for name in names
            )
        )

    def test_arch_recipe_uses_local_pinned_source(
        self,
    ):
        """Exige un checksum de la fuente."""
        self.build()
        recipe = self.output / "arch/PKGBUILD"
        text = recipe.read_text()
        self.assertIn("arch=('any')", text)
        self.assertNotIn("SKIP", text)
        self.assertNotIn("curl ", text)
        self.assertNotIn("sudo ", text)
        manifest = json.loads(
            (
                self.output / "manifest.json"
            ).read_text()
        )
        self.assertEqual(
            manifest["version"], "0.1.0"
        )
        self.assertIn("sha256", manifest)

    def test_source_excludes_local_state(self):
        """Solo incorpora archivos autorizados."""
        self.build()
        source = next(
            self.output.glob("*-source.tar.gz")
        )
        with tarfile.open(source) as archive:
            names = archive.getnames()
        for forbidden in (
            "/.git/",
            "/.pxp/",
            "/.codex/",
            "/__pycache__/",
            "/.venv/",
            "/outputs/",
        ):
            self.assertFalse(
                any(
                    forbidden in name
                    for name in names
                ),
                forbidden,
            )

    def test_stage_rejects_symlink_redirect(self):
        """Rechaza redirecciones del staging."""
        stage = Path(self.temp.name) / "stage"
        stage.mkdir()
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (stage / "usr").symlink_to(outside)
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "stage",
                "--destdir",
                str(stage),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(
            list(outside.iterdir()), []
        )

    def test_arch_receives_the_fixed_epoch(self):
        """Transmite la fecha a makepkg."""
        spec = spec_from_file_location(
            "pxp_package_builder", SCRIPT
        )
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(
            module,
            "build_arch",
            side_effect=ValueError("intercept"),
        ) as run:
            with self.assertRaises(ValueError):
                module.build(
                    ROOT,
                    self.output,
                    1700000000,
                    module.MAINTAINER,
                    True,
                )
        self.assertEqual(
            run.call_args.args,
            (
                self.output / "arch",
                self.output,
                1700000000,
            ),
        )
