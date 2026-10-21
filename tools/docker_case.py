"""Ejecutor interno sin acceso al host."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def run(args, cwd):
    """Exige éxito sin shell ni descargas."""
    completed = subprocess.run(
        args,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )
    if completed.returncode:
        print(completed.stdout, file=sys.stderr)
        print(completed.stderr, file=sys.stderr)
        completed.check_returncode()


def identifiers(suite):
    """Descubre pruebas dentro de Docker."""
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from identifiers(test)
        else:
            yield test.id()


def wheel(root):
    """Construye e instala wheel sin conexión."""
    source = root / "source"
    shutil.copytree("/src", source)
    output = root / "wheel"
    run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-index",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(output),
            str(source),
        ],
        root,
    )
    target = root / "site"
    run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            "--target",
            str(target),
            str(next(output.glob("*.whl"))),
        ],
        root,
    )
    code = (
        "import sys;"
        "sys.path.insert(0,sys.argv[1]);"
        "from pxp_harness.cli import main;"
        "raise SystemExit(main(['init']))"
    )
    run(
        [sys.executable, "-c", code, str(target)],
        root,
    )
    assert (root / ".pxp/config.json").is_file()


def engram(root):
    """Verifica persistencia y separación real."""
    binary = Path("/opt/vendor/engram")
    for index in range(2):
        project = root / str(index)
        project.mkdir()
        process = subprocess.Popen(
            [str(binary), "mcp"],
            cwd=project,
            env={
                **os.environ,
                "ENGRAM_DATA_DIR": str(
                    project / ".pxp/engram"
                ),
                "ENGRAM_CLOUD_AUTOSYNC": "0",
                "ENGRAM_PROJECT": "",
            },
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )

        def call(identifier, method, params):
            request = {
                "jsonrpc": "2.0",
                "id": identifier,
                "method": method,
                "params": params,
            }
            process.stdin.write(
                json.dumps(request) + "\n"
            )
            process.stdin.flush()
            response = json.loads(
                process.stdout.readline()
            )
            assert "error" not in response
            assert not response["result"].get(
                "isError"
            )
            return response["result"]

        try:
            call(
                1,
                "initialize",
                {
                    "protocolVersion": (
                        "2024-11-05"
                    ),
                    "capabilities": {},
                    "clientInfo": {
                        "name": "pxp-docker",
                        "version": "0.2.0",
                    },
                },
            )
            process.stdin.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "method": (
                            "notifications/"
                            "initialized"
                        ),
                    }
                )
                + "\n"
            )
            process.stdin.flush()
            call(2, "tools/list", {})
            if index == 0:
                call(
                    3,
                    "tools/call",
                    {
                        "name": "mem_save",
                        "arguments": {
                            "title": (
                                "Docker isolation"
                            ),
                            "content": (
                                "unique739dtest"
                            ),
                            "capture_prompt": (
                                False
                            ),
                        },
                    },
                )
            found = call(
                4,
                "tools/call",
                {
                    "name": "mem_search",
                    "arguments": {
                        "query": "unique739dtest"
                    },
                },
            )
            assert (
                "Docker isolation"
                in json.dumps(found)
            ) == (index == 0)
            call(
                5,
                "tools/call",
                {
                    "name": "mem_context",
                    "arguments": {},
                },
            )
        finally:
            process.terminate()
            process.wait(timeout=5)


def native(root, distro):
    """Instala y elimina dentro del contenedor."""
    global_home = root / "codex"
    global_home.mkdir()
    sentinel = global_home / "config.toml"
    sentinel.write_text("global sentinel")
    os.environ["CODEX_HOME"] = str(global_home)
    if distro == "debian":
        asset = next(
            Path("/opt/packages").glob("*.deb")
        )
        install = ["dpkg", "-i", str(asset)]
        remove = [
            "dpkg",
            "--purge",
            "pxp-harness",
        ]
    else:
        asset = next(
            Path("/opt/packages").glob(
                "*.pkg.tar.zst"
            )
        )
        install = [
            "pacman",
            "-U",
            "--noconfirm",
            str(asset),
        ]
        remove = [
            "pacman",
            "-R",
            "--noconfirm",
            "pxp-harness",
        ]
    run(install, root)
    for args in (
        ["init"],
        ["memory", "enable"],
        ["memory", "show"],
    ):
        run(["/usr/bin/pxp", *args], root)
    assert (
        sentinel.read_text() == "global sentinel"
    )
    run(remove, root)
    assert not Path("/usr/bin/pxp").exists()
    assert (root / ".pxp/config.json").exists()
    assert (
        sentinel.read_text() == "global sentinel"
    )


def main():
    """Ejecuta un caso con evidencia mínima."""
    Path("/tmp/home").mkdir(exist_ok=True)
    case = sys.argv[1]
    sys.path.insert(0, "/src/tests")
    if case == "discover":
        suite = (
            unittest.defaultTestLoader.discover(
                "/src/tests"
            )
        )
        print(
            json.dumps(list(identifiers(suite)))
        )
        return 0
    if case.startswith("test_"):
        loader = unittest.defaultTestLoader
        suite = loader.loadTestsFromName(case)
        result = unittest.TextTestRunner(
            stream=sys.stderr, verbosity=0
        ).run(suite)
        success = (
            result.wasSuccessful()
            and result.testsRun == 1
            and not result.skipped
            and not result.expectedFailures
        )
    else:
        with (
            tempfile.TemporaryDirectory() as temp
        ):
            root = Path(temp)
            if case == "wheel":
                wheel(root)
            elif case == "engram":
                engram(root)
            elif case in ("debian", "arch"):
                native(root, case)
            else:
                raise ValueError("Unknown case")
        success = True
    print(
        "PXP_RESULT "
        + json.dumps(
            {
                "status": "PASS"
                if success
                else "FAIL"
            }
        )
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
