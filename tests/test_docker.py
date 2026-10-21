"""Contrato de aislamiento de cada prueba."""

import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

PATH = (
    Path(__file__).resolve().parents[1]
    / "tools/test_docker.py"
)
SPEC = importlib.util.spec_from_file_location(
    "docker_runner", PATH
)
MODULE = importlib.util.module_from_spec(SPEC)


class DockerTests(unittest.TestCase):
    """Prueba el runner sin Docker."""

    @classmethod
    def setUpClass(cls):
        """Carga el orquestador sin ejecutarlo."""
        SPEC.loader.exec_module(MODULE)

    def test_runtime_has_no_host_access(self):
        """Exige límites explícitos."""
        argv = MODULE.command("image", "case")
        for item in (
            "--rm",
            "--read-only",
            "none",
            "ALL",
            "10001:10001",
            "no-new-privileges=true",
        ):
            self.assertIn(item, argv)
        for item in ("--privileged", "--volume"):
            self.assertNotIn(item, argv)
        self.assertNotIn("docker.sock", str(argv))

    def test_unavailable_is_not_success(self):
        """No convierte errores Docker en PASS."""
        self.assertEqual(
            MODULE.classify(125, None),
            "UNAVAILABLE",
        )
        self.assertEqual(
            MODULE.classify(0, None), "FAIL"
        )

    def test_skips_are_not_green(self):
        """Rechaza pruebas omitidas."""
        self.assertEqual(
            MODULE.classify(
                0, {"status": "SKIP"}
            ),
            "FAIL",
        )

    def test_timeout_cleans_own_container(self):
        """Solo elimina el contenedor propio."""
        with patch.object(
            MODULE.subprocess,
            "run",
            side_effect=[
                subprocess.TimeoutExpired([], 1),
                subprocess.CompletedProcess(
                    [], 0
                ),
            ],
        ) as run:
            result = MODULE.execute(
                "image", "case", "example"
            )
        self.assertEqual(
            result["status"], "UNAVAILABLE"
        )
        cleanup = run.call_args.args[0]
        self.assertEqual(
            cleanup[:3], ["docker", "rm", "-f"]
        )
        self.assertTrue(
            cleanup[-1].startswith("pxp-case-")
        )

    def test_logs_are_bounded_and_scrubbed(self):
        """Oculta rutas y tokens conocidos."""
        value = MODULE.clean(
            "/home/private/file ghp_abc123 "
            + "x" * 10000
        )
        self.assertLessEqual(len(value), 4000)
        self.assertNotIn("/home/private", value)
        self.assertNotIn("ghp_abc123", value)

    def test_snapshot_excludes_private_state(
        self,
    ):
        """No envía Git ni bases de memoria."""
        import io
        import tarfile

        with tarfile.open(
            fileobj=io.BytesIO(MODULE.snapshot())
        ) as source:
            names = source.getnames()
        self.assertIn(
            "src/pxp_harness/cli.py", names
        )
        for name in names:
            self.assertNotIn(".git/", name)
            self.assertNotIn(".pxp/", name)
            self.assertNotIn(".env", name)

    def test_native_error_is_visible(self):
        """Conserva diagnóstico nativo."""
        import contextlib
        import io

        util = importlib.util
        spec = util.spec_from_file_location(
            "docker_inner",
            PATH.parent / "docker_case.py",
        )
        inner = importlib.util.module_from_spec(
            spec
        )
        spec.loader.exec_module(inner)
        output = io.StringIO()
        completed = subprocess.CompletedProcess(
            [], 1, "", "native diagnostic"
        )
        with (
            patch.object(
                inner.subprocess,
                "run",
                return_value=completed,
            ),
            contextlib.redirect_stderr(output),
            self.assertRaises(
                subprocess.CalledProcessError
            ),
        ):
            inner.run(
                ["package-manager"], Path("/tmp")
            )
        self.assertIn(
            "native diagnostic", output.getvalue()
        )

    def test_arch_capability_is_narrow(self):
        """Permite CHOWN solo al gestor Arch."""
        arch = MODULE.command("image", "arch")
        self.assertIn("--cap-add", arch)
        self.assertIn("CHOWN", arch)
        for case in ("debian", "wheel", "case"):
            self.assertNotIn(
                "--cap-add",
                MODULE.command("image", case),
            )

    def test_runner_context_is_step_scoped(self):
        """No usa runner.temp en env del job."""
        workflow = (
            PATH.parents[1]
            / ".github/workflows/docker-tests.yml"
        ).read_text()
        job_env = workflow.split("    env:\n", 1)[
            1
        ].split("    steps:\n", 1)[0]
        self.assertNotIn("runner.temp", job_env)
        self.assertIn(
            "path: ${{ runner.temp }}"
            "/pxp-docker-",
            workflow,
        )
        self.assertIn(
            '--report-dir "$RUNNER_TEMP/'
            "pxp-docker-",
            workflow,
        )
