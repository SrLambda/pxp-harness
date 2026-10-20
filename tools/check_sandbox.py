"""Diagnóstico local sin modelos ni secretos."""

import argparse
import errno
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = """
import errno, json, pathlib, socket, sys
print('PXP_ENTERED', flush=True)
try:
    if sys.argv[1] == 'write':
        pathlib.Path('sentinel').write_text('new')
    else:
        s = socket.create_connection(
            ('127.0.0.1', int(sys.argv[2])), 2)
        s.close()
except OSError as exc:
    print(json.dumps({'errno': exc.errno}))
else:
    print(json.dumps({'allowed': True}))
"""


def classify(allowed, expected):
    """Exige ejecución antes del veredicto."""
    if allowed is None:
        return "UNAVAILABLE"
    return (
        "PASS" if allowed == expected else "FAIL"
    )


def run(argv, cwd):
    """Ejecuta sin shell y con límite."""
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def observation(result):
    """Valida el resultado del proceso."""
    if result is None or result.returncode != 0:
        return None
    lines = result.stdout.splitlines()
    if "PXP_ENTERED" not in lines:
        return None
    try:
        data = json.loads(lines[-1])
    except (ValueError, IndexError):
        return None
    if data == {"allowed": True}:
        return True
    if data.get("errno") in (
        errno.EACCES,
        errno.EPERM,
        errno.EROFS,
    ):
        return False
    return None


def probe(prefix, root, action, port):
    """Prueba escritura o conexión local."""
    command = [
        sys.executable,
        "-c",
        SCRIPT,
        action,
        str(port),
    ]
    return observation(
        run(prefix + command, root)
    )


def diagnose(codex):
    """Comprueba ambos controles."""
    report = {
        "schema_version": 1,
        "status": "UNAVAILABLE",
        "policy_tamper": "NOT_TESTED",
        "checks": {},
    }
    if os.geteuid() == 0 or os.getenv(
        "SUDO_USER"
    ):
        report["reason"] = "root_or_sudo_refused"
        return report
    path = Path(codex)
    if (
        not path.is_absolute()
        or not path.is_file()
    ):
        report["reason"] = (
            "explicit_binary_required"
        )
        return report
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        version = run(
            [str(path), "--version"], root
        )
        help_result = run(
            [str(path), "sandbox", "--help"], root
        )
        if (
            version is None
            or version.returncode
            or help_result is None
            or help_result.returncode
        ):
            report["reason"] = "cli_unavailable"
            return report
        match = re.search(
            r"codex-cli ([0-9.]+)", version.stdout
        )
        report["version"] = (
            match.group(1) if match else "unknown"
        )
        help_text = help_result.stdout
        if "--config" not in help_text:
            report["reason"] = "unsupported_cli"
            return report
        base = [str(path), "sandbox"]
        if "linux" in help_text.split():
            base.append("linux")
        listener = None
        try:
            listener = socket.socket()
            listener.bind(("127.0.0.1", 0))
            listener.listen(16)
            port = listener.getsockname()[1]
            sentinel = root / "sentinel"
            controls = {}
            for action in ("write", "network"):
                controls[action] = probe(
                    [], root, action, port
                )
            if not all(
                value is True
                for value in controls.values()
            ):
                report["reason"] = (
                    "control_failed"
                )
                return report
            for mode, action, expected in (
                ("read-only", "write", False),
                (
                    "workspace-write",
                    "write",
                    True,
                ),
                ("read-only", "network", False),
            ):
                sentinel.write_text("old")
                prefix = base + [
                    "-c",
                    f'sandbox_mode="{mode}"',
                    "-c",
                    "sandbox_workspace_write."
                    "network_access=false",
                    "--",
                ]
                allowed = probe(
                    prefix, root, action, port
                )
                if action == "write":
                    changed = (
                        sentinel.read_text()
                        != "old"
                    )
                    if changed:
                        allowed = True
                key = f"{mode}:{action}"
                report["checks"][key] = classify(
                    allowed, expected
                )
        except OSError:
            report["reason"] = (
                "local_socket_unavailable"
            )
            return report
        finally:
            if listener is not None:
                listener.close()
    values = list(report["checks"].values())
    report["status"] = (
        "FAIL"
        if "FAIL" in values
        else "UNAVAILABLE"
        if "UNAVAILABLE" in values
        else "PASS"
    )
    report["reason"] = (
        "basic_checks_only"
        if report["status"] == "PASS"
        else "inspect_native_sandbox_in_vm"
    )
    return report


def main():
    """Genera JSON sin datos sensibles."""
    parser = argparse.ArgumentParser(
        description=__doc__
    )
    parser.add_argument("--codex", required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = diagnose(args.codex)
    output = json.dumps(result, indent=2) + "\n"
    if args.report:
        with args.report.open("x") as stream:
            stream.write(output)
    else:
        print(output, end="")
    return {
        "PASS": 0,
        "FAIL": 1,
        "UNAVAILABLE": 2,
    }[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
