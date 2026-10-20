"""Pruebas de proyectos existentes y Git local."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from pxp_harness.cli import main
from pxp_harness.project import (
    ProjectError,
    initialize,
)
from pxp_harness.repository import (
    ensure_git,
    find_project_root,
)


class RepositoryTests(unittest.TestCase):
    """Comprueba fallos sin cambios."""

    def setUp(self):
        """Crea una carpeta aislada."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_plain_init_needs_no_git(self):
        """Permite trabajar sin Git."""
        with patch(
            (
                "pxp_harness.repository."
                "shutil.which"
            ),
            return_value=None,
        ):
            self.assertEqual(
                main(["init"], cwd=self.root), 0
            )
        self.assertFalse(
            (self.root / ".git").exists()
        )

    def test_missing_git_creates_no_pxp(self):
        """Falla antes de escribir."""
        with patch(
            (
                "pxp_harness.repository."
                "shutil.which"
            ),
            return_value=None,
        ):
            self.assertEqual(
                main(
                    ["init", "--git"],
                    cwd=self.root,
                ),
                1,
            )
        self.assertFalse(
            (self.root / ".pxp").exists()
        )

    def test_git_init_failure_preserves_work(
        self,
    ):
        """No sobrescribe archivos ante fallos."""
        source = self.root / "work.txt"
        source.write_text("existing work")
        with (
            patch(
                (
                    "pxp_harness.repository."
                    "shutil.which"
                ),
                return_value="/usr/bin/git",
            ),
            patch(
                (
                    "pxp_harness.repository."
                    "subprocess.run"
                ),
                side_effect=[
                    CompletedProcess(
                        [], 128, "", ""
                    ),
                    CompletedProcess(
                        [], 128, "", ""
                    ),
                    CompletedProcess(
                        [], 1, "", ""
                    ),
                ],
            ) as run,
        ):
            with self.assertRaises(ProjectError):
                ensure_git(self.root)
        self.assertEqual(
            source.read_text(), "existing work"
        )
        self.assertFalse(
            (self.root / ".pxp").exists()
        )
        self.assertEqual(
            run.call_args.args[0],
            ["/usr/bin/git", "init", "--quiet"],
        )
        self.assertIs(
            run.call_args.kwargs["shell"], False
        )

    def test_non_git_keeps_local_directory(self):
        """No adopta carpetas ajenas sin Git."""
        initialize(self.root)
        child = self.root / "src"
        child.mkdir()
        self.assertEqual(
            find_project_root(child), child
        )

    def test_empty_ancestor_git_is_not_a_repo(
        self,
    ):
        """No confunde carpetas vacías con Git."""
        initialize(self.root)
        (self.root / ".git").mkdir()
        child = self.root / "new-project"
        child.mkdir()
        self.assertEqual(
            find_project_root(child), child
        )
        self.assertEqual(
            main(["init"], cwd=child), 0
        )
        self.assertTrue(
            (child / ".pxp/config.json").is_file()
        )


@unittest.skipUnless(
    shutil.which("git"), "Git is not installed"
)
class RealGitTests(unittest.TestCase):
    """Comprueba Git real y aislado."""

    def setUp(self):
        """Aísla repositorios e identidad."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = (
            Path(self.temp.name) / "mi ñ repo"
        )
        self.root.mkdir()

    def git(self, *args):
        """Ejecuta Git aislado."""
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("GIT_")
        }
        environment.update(
            {
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_NOSYSTEM": "1",
            }
        )
        return subprocess.run(
            [
                "git",
                "-c",
                "user.name=PXP Test",
                "-c",
                "user.email=test@example.invalid",
                *args,
            ],
            cwd=self.root,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    def commit_example(self):
        """Crea una historia mínima."""
        self.git("init", "--quiet")
        (self.root / "existing.txt").write_text(
            "existing work\n"
        )
        self.git("add", "existing.txt")
        self.git(
            "commit", "--quiet", "-m", "test"
        )

    def test_init_git_creates_empty_repo(self):
        """Crea Git y PXP sin publicar."""
        self.assertEqual(
            main(
                ["init", "--git"], cwd=self.root
            ),
            0,
        )
        self.assertTrue(
            (self.root / ".git").is_dir()
        )
        self.assertTrue(
            (
                self.root / ".pxp/config.json"
            ).is_file()
        )
        self.assertEqual(self.git("remote"), "")
        self.assertEqual(self.git("ls-files"), "")
        result = subprocess.run(
            [
                "git",
                "rev-parse",
                "--verify",
                "HEAD",
            ],
            cwd=self.root,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_existing_repo_is_not_reinitialized(
        self,
    ):
        """Conserva datos de Git."""
        self.commit_example()
        before = {
            name: (
                self.root / ".git" / name
            ).read_bytes()
            for name in (
                "HEAD",
                "index",
                "config",
            )
        }
        head = self.git("rev-parse", "HEAD")
        self.assertEqual(
            main(
                ["init", "--git"], cwd=self.root
            ),
            0,
        )
        self.assertEqual(
            self.git("rev-parse", "HEAD"), head
        )
        for name, content in before.items():
            self.assertEqual(
                (
                    self.root / ".git" / name
                ).read_bytes(),
                content,
            )
        self.assertEqual(
            (
                self.root / "existing.txt"
            ).read_text(),
            "existing work\n",
        )

    def test_subdirectory_uses_existing_root(
        self,
    ):
        """No crea repositorios anidados."""
        self.commit_example()
        child = self.root / "src"
        child.mkdir()
        self.assertEqual(
            main(["init", "--git"], cwd=child), 0
        )
        self.assertTrue(
            (
                self.root / ".pxp/config.json"
            ).is_file()
        )
        self.assertFalse(
            (child / ".git").exists()
        )
        self.assertFalse(
            (child / ".pxp").exists()
        )
        self.assertEqual(
            main(["mode", "design"], cwd=child), 0
        )

    def test_attach_preserves_pxp_configuration(
        self,
    ):
        """Conserva archivos existentes."""
        self.commit_example()
        initialize(self.root)
        path = self.root / ".pxp/config.json"
        config = path.read_bytes()
        artifact = self.root / (
            ".pxp/artifacts/requirements.md"
        )
        artifact.write_text("My requirements")
        self.assertEqual(
            main(["init"], cwd=self.root), 0
        )
        self.assertEqual(
            path.read_bytes(), config
        )
        self.assertEqual(
            artifact.read_text(),
            "My requirements",
        )

    def test_bare_repo_is_rejected(self):
        """Rechaza repositorios bare."""
        self.git("init", "--bare", "--quiet")
        self.assertEqual(
            main(
                ["init", "--git"], cwd=self.root
            ),
            1,
        )
        self.assertFalse(
            (self.root / ".pxp").exists()
        )

    def test_git_environment_does_not_redirect(
        self,
    ):
        """No utiliza GIT_DIR heredado."""
        other = self.root.parent / "other"
        other.mkdir()
        with patch.dict(
            os.environ,
            {
                "GIT_DIR": str(other / ".git"),
                "GIT_WORK_TREE": str(other),
            },
        ):
            self.assertEqual(
                main(
                    ["init", "--git"],
                    cwd=self.root,
                ),
                0,
            )
        self.assertTrue(
            (self.root / ".git").is_dir()
        )
        self.assertFalse(
            (other / ".git").exists()
        )

    def test_existing_worktree_is_supported(self):
        """Reconoce worktrees con archivo Git."""
        self.commit_example()
        target = self.root.parent / "worktree"
        self.git(
            "worktree",
            "add",
            "--detach",
            str(target),
            "HEAD",
        )
        self.assertTrue(
            (target / ".git").is_file()
        )
        child = target / "src"
        child.mkdir()
        self.assertEqual(
            main(["init", "--git"], cwd=child), 0
        )
        self.assertTrue(
            (
                target / ".pxp/config.json"
            ).is_file()
        )
        self.assertFalse(
            (child / ".git").exists()
        )

    def test_nested_pxp_keeps_its_boundary(self):
        """Conserva el límite del proyecto."""
        self.commit_example()
        child = self.root / "module"
        child.mkdir()
        initialize(child)
        nested = child / "src"
        nested.mkdir()
        self.assertEqual(
            find_project_root(nested), child
        )
        self.assertEqual(
            main(["init"], cwd=nested), 0
        )
        self.assertEqual(
            main(["init", "--git"], cwd=nested), 1
        )
        self.assertFalse(
            (child / ".git").exists()
        )
        self.assertFalse(
            (self.root / ".pxp").exists()
        )

    def test_attach_without_git_flag(self):
        """Añade PXP sin reinicializar Git."""
        self.commit_example()
        before = (
            self.root / ".git/config"
        ).read_bytes()
        self.assertEqual(
            main(["init"], cwd=self.root), 0
        )
        self.assertTrue(
            (
                self.root / ".pxp/config.json"
            ).is_file()
        )
        self.assertEqual(
            (
                self.root / ".git/config"
            ).read_bytes(),
            before,
        )

    def test_broken_git_metadata_is_preserved(
        self,
    ):
        """No reemplaza metadatos ajenos."""
        marker = self.root / ".git"
        marker.write_text("gitdir: missing\n")
        self.assertEqual(
            main(
                ["init", "--git"], cwd=self.root
            ),
            1,
        )
        self.assertEqual(
            marker.read_text(),
            "gitdir: missing\n",
        )
        self.assertFalse(
            (self.root / ".pxp").exists()
        )
