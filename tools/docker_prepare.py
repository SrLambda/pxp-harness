"""Prepara dependencias fuera del runtime."""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path("/src")


def main():
    """Valida la dependencia fijada."""
    lock = json.loads(
        (
            ROOT / "packaging/engram/lock.json"
        ).read_text()
    )
    asset = Path("/opt/vendor/engram.tar.gz")
    asset.parent.mkdir(
        parents=True, exist_ok=True
    )
    with urllib.request.urlopen(
        lock["url"], timeout=60
    ) as response:
        raw = response.read(64 * 1024 * 1024)
    if (
        hashlib.sha256(raw).hexdigest()
        != (lock["sha256"])
    ):
        raise ValueError(
            "Engram checksum mismatch"
        )
    asset.write_bytes(raw)
    spec = importlib.util.spec_from_file_location(
        "package", ROOT / "tools/package.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    payload = module.engram_payload(ROOT, asset)
    binary = asset.parent / "engram"
    binary.write_bytes(
        payload["usr/libexec/pxp-harness/engram"][
            0
        ]
    )
    binary.chmod(0o755)
    command = [
        sys.executable,
        "tools/package.py",
        "build",
        "--engram-archive",
        str(asset),
        "--output",
        "/opt/packages",
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    if len(sys.argv) > 1:
        subprocess.run(
            [
                "makepkg",
                "--cleanbuild",
                "--noconfirm",
                "--nocheck",
            ],
            cwd="/opt/packages/arch",
            env={
                **os.environ,
                "PKGDEST": "/opt/packages",
            },
            check=True,
        )


if __name__ == "__main__":
    main()
