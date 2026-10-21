"""Una prueba por contenedor aislado."""

import argparse
import importlib.util
import io
import json
import os
import re
import signal
import subprocess
import tarfile
import tempfile
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTRA = (
    "tools/test_docker.py",
    "tools/docker_case.py",
    "tools/docker_prepare.py",
    "ci/Dockerfile.debian",
    "ci/Dockerfile.arch",
    "tests/test_docker.py",
)


def clean(value):
    """Limita logs y oculta rutas y tokens."""
    value = re.sub(
        r"(ghp_|github_pat_|sk-)[\w-]+",
        "<redacted>",
        value,
    )
    value = re.sub(
        r"/[^\s\"\']+", "<path>", value
    )
    return value[-4000:]


def classify(code, result):
    """No acepta skips o ausencia de evidencia."""
    if code in (125, 126, 127) or code is None:
        return "UNAVAILABLE"
    if code == 0 and result == {"status": "PASS"}:
        return "PASS"
    return "FAIL"


def command(image, case, name=None):
    """Define límites sin dar acceso al host."""
    args = [
        "docker",
        "run",
        "--rm",
        "--init",
        "--name",
        name or "pxp-case-preview",
        "--network",
        "none",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--pids-limit",
        "256",
        "--memory",
        "1g",
        "--cpus",
        "2",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,"
        "size=512m,mode=1777",
        "--env",
        "HOME=/tmp/home",
        "--env",
        "PYTHONDONTWRITEBYTECODE=1",
        "--env",
        "PYTHONPATH=/src/src:/src/tests",
        "--workdir",
        "/src",
    ]
    if case in ("debian", "arch"):
        args += ["--user", "0:0"]
    else:
        args += [
            "--read-only",
            "--user",
            "10001:10001",
        ]
    if case == "arch":
        args += ["--cap-add", "CHOWN"]
    return args + [
        image,
        "python3",
        "tools/docker_case.py",
        case,
    ]


def execute(image, case, identifier):
    """Limita tiempo y limpia solo su UUID."""
    name = "pxp-case-" + uuid.uuid4().hex
    result = None
    code = None
    log = ""
    try:
        completed = subprocess.run(
            command(image, case, name),
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        code = completed.returncode
        log = clean(
            completed.stdout + completed.stderr
        )
        for line in completed.stdout.splitlines():
            if line.startswith("PXP_RESULT "):
                try:
                    result = json.loads(line[11:])
                except ValueError:
                    result = None
    except (OSError, subprocess.TimeoutExpired):
        pass
    finally:
        try:
            subprocess.run(
                ["docker", "rm", "-f", name],
                capture_output=True,
                timeout=15,
                check=False,
            )
        except (
            OSError,
            subprocess.TimeoutExpired,
        ):
            pass
    return {
        "id": identifier,
        "status": classify(code, result),
        "exit_code": code,
        "log": log,
    }


def snapshot():
    """Envía solo fuentes autorizadas, no Git."""
    spec = importlib.util.spec_from_file_location(
        "package", ROOT / "tools/package.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    files = module.source_files(ROOT)
    for name in EXTRA:
        path = ROOT / name
        if path.is_symlink():
            raise ValueError(
                "Source symlink refused"
            )
        files[name] = path.read_bytes()
    raw = io.BytesIO()
    with tarfile.open(
        fileobj=raw, mode="w"
    ) as archive:
        for name, content in sorted(
            files.items()
        ):
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mode = 0o644
            archive.addfile(
                info, io.BytesIO(content)
            )
    return raw.getvalue()


def reports(output, cases):
    """Escribe resultados sin logs ni secretos."""
    output.mkdir(parents=True, exist_ok=True)
    failed = sum(
        case["status"] != "PASS" for case in cases
    )
    data = {
        "status": "FAIL" if failed else "PASS",
        "cases": cases,
    }
    (output / "summary.json").write_text(
        json.dumps(data, indent=2) + "\n"
    )
    suite = ET.Element(
        "testsuite",
        tests=str(len(cases)),
        failures=str(failed),
    )
    for index, case in enumerate(cases):
        (
            output / f"case-{index:04}.json"
        ).write_text(json.dumps(case) + "\n")
        node = ET.SubElement(
            suite, "testcase", name=case["id"]
        )
        if case["status"] != "PASS":
            ET.SubElement(
                node,
                "failure",
                message=case["status"],
            )
    ET.ElementTree(suite).write(
        output / "junit.xml", encoding="utf-8"
    )
    return 1 if failed else 0


def main():
    """Separa build y runtime sin red."""
    parser = argparse.ArgumentParser(
        description=__doc__
    )
    parser.add_argument(
        "--suite",
        choices=["unit", "full", "native"],
        default="unit",
    )
    parser.add_argument(
        "--report-dir", type=Path, required=True
    )
    args = parser.parse_args()
    if args.report_dir.exists():
        parser.error(
            "Report directory must be new"
        )

    def interrupt(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    config = tempfile.TemporaryDirectory(
        prefix="pxp-docker-config-"
    )
    previous = os.environ.get("DOCKER_CONFIG")
    os.environ["DOCKER_CONFIG"] = config.name
    cases = []
    token = uuid.uuid4().hex
    images = []
    try:
        subprocess.run(
            ["docker", "info"],
            capture_output=True,
            check=True,
            timeout=15,
        )
        context = snapshot()
        for distro in (
            ["debian", "arch"]
            if args.suite != "unit"
            else ["debian"]
        ):
            image = (
                "pxp-ci-" + token + ":" + distro
            )
            images.append(image)
            built = subprocess.run(
                [
                    "docker",
                    "build",
                    "-t",
                    image,
                    "-f",
                    f"ci/Dockerfile.{distro}",
                    "-",
                ],
                input=context,
                capture_output=True,
                timeout=900,
                check=False,
            )
            if built.returncode:
                raise RuntimeError(
                    "image_build: "
                    + clean(
                        built.stderr.decode(
                            errors="replace"
                        )
                    )
                )
            if (
                distro == "debian"
                and args.suite != "native"
            ):
                discovery_name = (
                    "pxp-case-" + uuid.uuid4().hex
                )
                try:
                    discovery = subprocess.run(
                        command(
                            image,
                            "discover",
                            discovery_name,
                        ),
                        capture_output=True,
                        text=True,
                        timeout=30,
                        check=True,
                    )
                finally:
                    subprocess.run(
                        [
                            "docker",
                            "rm",
                            "-f",
                            discovery_name,
                        ],
                        capture_output=True,
                        timeout=15,
                        check=False,
                    )
                tests = json.loads(
                    discovery.stdout.strip()
                )
                if not tests or not all(
                    isinstance(item, str)
                    and item.startswith("test_")
                    for item in tests
                ):
                    raise RuntimeError(
                        "discovery"
                    )
                for test in tests + [
                    "wheel",
                    "engram",
                ]:
                    cases.append(
                        execute(image, test, test)
                    )
            if args.suite != "unit":
                cases.append(
                    execute(image, distro, distro)
                )
    except (
        OSError,
        ValueError,
        RuntimeError,
        KeyboardInterrupt,
        subprocess.SubprocessError,
    ) as exc:
        cases.append(
            {
                "id": "docker_setup",
                "reason": type(exc).__name__,
                "log": clean(
                    str(
                        getattr(exc, "stderr", "")
                    )
                    or str(exc)
                ),
                "status": "UNAVAILABLE",
                "exit_code": None,
            }
        )
    finally:
        for image in images:
            try:
                subprocess.run(
                    [
                        "docker",
                        "image",
                        "rm",
                        image,
                    ],
                    capture_output=True,
                    timeout=30,
                    check=False,
                )
            except (
                OSError,
                subprocess.TimeoutExpired,
            ):
                pass
        if previous is None:
            os.environ.pop("DOCKER_CONFIG", None)
        else:
            os.environ["DOCKER_CONFIG"] = previous
        config.cleanup()
    return reports(args.report_dir, cases)


if __name__ == "__main__":
    raise SystemExit(main())
