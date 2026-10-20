"""Pruebas del diagnóstico sin modelos."""

import importlib.util
import unittest
from pathlib import Path

PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "check_sandbox.py"
)
SPEC = importlib.util.spec_from_file_location(
    "check_sandbox", PATH
)
MODULE = importlib.util.module_from_spec(SPEC)


class SandboxTests(unittest.TestCase):
    """Distingue fallo y denegación."""

    @classmethod
    def setUpClass(cls):
        """Carga el diagnóstico independiente."""
        SPEC.loader.exec_module(MODULE)

    def test_startup_failure_is_unavailable(self):
        """Rechaza fallos de arranque."""
        self.assertEqual(
            MODULE.classify(None, False),
            "UNAVAILABLE",
        )

    def test_unexpected_write_fails(self):
        """Detecta escritura inesperada."""
        self.assertEqual(
            MODULE.classify(True, False), "FAIL"
        )

    def test_denial_passes(self):
        """Acepta denegación explícita."""
        self.assertEqual(
            MODULE.classify(False, False), "PASS"
        )

    def test_positive_control_must_succeed(self):
        """Exige un control positivo."""
        self.assertEqual(
            MODULE.classify(False, True), "FAIL"
        )

    def test_startup_output_is_not_denial(self):
        """Rechaza fallos con texto engañoso."""
        from subprocess import CompletedProcess

        result = CompletedProcess(
            [], 1, "", "Permission denied"
        )
        self.assertIsNone(
            MODULE.observation(result)
        )

    def test_network_denial_is_explicit(self):
        """Exige errno de seguridad reconocido."""
        from subprocess import CompletedProcess

        result = CompletedProcess(
            [],
            0,
            'PXP_ENTERED\n{"errno": 1}\n',
            "",
        )
        self.assertIs(
            MODULE.observation(result), False
        )

    def test_other_network_error(
        self,
    ):
        """Rechaza errores de conexión."""
        from subprocess import CompletedProcess

        result = CompletedProcess(
            [],
            0,
            'PXP_ENTERED\n{"errno": 111}\n',
            "",
        )
        self.assertIsNone(
            MODULE.observation(result)
        )

    def test_diagnose_cleans_temp(self):
        """Limpia temporales sin backend."""
        from subprocess import CompletedProcess
        from unittest.mock import patch

        seen = []

        def fake_run(argv, cwd):
            seen.append(cwd)
            output = (
                "codex-cli 0.162.1"
                if "--version" in argv
                else "Usage: sandbox --config"
            )
            return CompletedProcess(
                argv, 0, output, ""
            )

        with (
            patch.object(
                MODULE.os,
                "geteuid",
                return_value=1000,
            ),
            patch.dict(
                MODULE.os.environ, {}, clear=True
            ),
            patch.object(MODULE, "run", fake_run),
            patch.object(
                MODULE.socket, "socket"
            ) as sock,
            patch.object(
                MODULE,
                "probe",
                side_effect=[
                    True,
                    True,
                    None,
                    None,
                    None,
                ],
            ),
        ):
            listener = sock.return_value
            listener.getsockname.return_value = (
                "127.0.0.1",
                12345,
            )
            result = MODULE.diagnose(__file__)
        self.assertEqual(
            result["status"], "UNAVAILABLE"
        )
        self.assertTrue(seen)
        self.assertFalse(seen[0].exists())

    def test_socket_creation_unavailable(self):
        """Reporta red no disponible."""
        from subprocess import CompletedProcess
        from unittest.mock import patch

        response = CompletedProcess(
            [], 0, "--config", ""
        )
        with (
            patch.object(
                MODULE.os,
                "geteuid",
                return_value=1000,
            ),
            patch.dict(
                MODULE.os.environ, {}, clear=True
            ),
            patch.object(
                MODULE,
                "run",
                return_value=response,
            ),
            patch.object(
                MODULE.socket,
                "socket",
                side_effect=PermissionError(),
            ),
        ):
            result = MODULE.diagnose(__file__)
        self.assertEqual(
            result["reason"],
            "local_socket_unavailable",
        )
