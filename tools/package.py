"""Construcción nativa local, sin red ni root."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
MAINTAINER = (
    "PXP Harness local builds "
    "<packaging@example.invalid>"
)
MODULES = (
    "__init__",
    "__main__",
    "cli",
    "editor",
    "memory",
    "project",
    "prompts",
    "repository",
    "standards",
)
TESTS = (
    "cli",
    "editor",
    "isolation",
    "packaging",
    "memory",
    "sandbox",
    "prompts",
    "quality",
    "repository",
    "standards",
)
FIXED = (
    "README.md",
    "pyproject.toml",
    "tools/package.py",
    "tools/check_sandbox.py",
    "docs/sandbox-test.md",
    "docs/memory.md",
    "packaging/engram/LICENSE",
    "packaging/engram/lock.json",
    "packaging/NOTICE",
    "packaging/launcher",
    "packaging/arch/PKGBUILD.in",
    (
        ".agents/skills/pxp-python-standards/"
        "SKILL.md"
    ),
)


def version(root: Path) -> str:
    """Lee la versión estable del proyecto."""
    data = tomllib.loads(
        (root / "pyproject.toml").read_text()
    )
    value = data["project"]["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", value):
        raise ValueError(
            "Use a stable X.Y.Z version."
        )
    return value


def source_files(root: Path) -> dict:
    """Incluye fuentes autorizadas."""
    names = [*FIXED]
    names += [
        f"src/pxp_harness/{name}.py"
        for name in MODULES
    ]
    names += [
        f"tests/test_{name}.py" for name in TESTS
    ]
    result = {}
    for name in names:
        path = root
        for part in Path(name).parts:
            path = path / part
            if path.is_symlink():
                raise ValueError(
                    "Source symlink refused."
                )
        result[name] = path.read_bytes()
    return result


def engram_payload(root, archive):
    """Verifica el binario fijado."""
    lock = json.loads(
        (
            root / "packaging/engram/lock.json"
        ).read_text()
    )
    raw = archive.read_bytes()
    if (
        hashlib.sha256(raw).hexdigest()
        != (lock["sha256"])
    ):
        raise ValueError(
            "Engram checksum mismatch."
        )
    license_data = (
        root / "packaging/engram/LICENSE"
    ).read_bytes()
    if (
        hashlib.sha256(license_data).hexdigest()
        != (lock["license_sha256"])
    ):
        raise ValueError(
            "Engram license mismatch."
        )
    with tarfile.open(
        fileobj=io.BytesIO(raw)
    ) as bundle:
        entry = bundle.getmember("engram")
        if not entry.isfile():
            raise ValueError(
                "Invalid Engram asset."
            )
        binary = bundle.extractfile(entry).read()
    if binary[:5] != b"\x7fELF\x02":
        raise ValueError("Expected 64-bit ELF.")
    if binary[18:20] != b"\x3e\x00":
        raise ValueError("Expected x86_64 ELF.")
    return {
        "usr/libexec/pxp-harness/engram": (
            binary,
            0o755,
        ),
        "usr/share/licenses/pxp-harness/"
        "ENGRAM-LICENSE": (license_data, 0o644),
        "usr/share/pxp-harness/engram.json": (
            json.dumps(lock, indent=2).encode(),
            0o644,
        ),
    }


def payload(root: Path, engram=None) -> dict:
    """Prepara archivos privados de la app."""
    sources = source_files(root)
    result = {}
    for name in MODULES:
        path = f"pxp_harness/{name}.py"
        result[
            "usr/share/pxp-harness/" + path
        ] = (sources["src/" + path], 0o644)
    result["usr/bin/pxp"] = (
        sources["packaging/launcher"],
        0o755,
    )
    result[
        "usr/share/doc/pxp-harness/README.md"
    ] = (sources["README.md"], 0o644)
    for document in (
        "sandbox-test.md",
        "memory.md",
    ):
        result[
            "usr/share/doc/pxp-harness/docs/"
            + document
        ] = (sources["docs/" + document], 0o644)
    notice = (sources["packaging/NOTICE"], 0o644)
    result[
        "usr/share/doc/pxp-harness/copyright"
    ] = notice
    result[
        "usr/share/licenses/pxp-harness/NOTICE"
    ] = notice
    skill = (
        "usr/share/pxp-harness/skills/"
        "pxp-python-standards/SKILL.md"
    )
    result[skill] = (sources[FIXED[-1]], 0o644)
    archive = engram or (
        root / "vendor/engram.tar.gz"
    )
    if engram is not None or archive.exists():
        result.update(
            engram_payload(root, archive)
        )
    return result


def stage(root: Path, destination: Path) -> None:
    """Escribe en el staging explícito."""
    destination = destination.resolve()
    if destination == Path("/"):
        raise ValueError(
            "Never stage into system root."
        )
    for name, (data, mode) in payload(
        root
    ).items():
        target = destination
        for part in Path(name).parts:
            target = target / part
            if target.is_symlink():
                raise ValueError(
                    "Staging symlink refused."
                )
        target.parent.mkdir(
            parents=True, exist_ok=True
        )
        with target.open("xb") as output:
            output.write(data)
        target.chmod(mode)


def compressed_tar(
    files: dict, epoch: int
) -> bytes:
    """Normaliza permisos, dueño y fecha."""
    raw = io.BytesIO()
    with tarfile.open(
        fileobj=raw,
        mode="w",
        format=tarfile.USTAR_FORMAT,
    ) as archive:
        directories = set()
        for name in files:
            for parent in Path(name).parents:
                if str(parent) != ".":
                    directories.add(
                        parent.as_posix()
                    )
        for name in sorted(directories):
            info = tarfile.TarInfo(name)
            info.type = tarfile.DIRTYPE
            info.mode = 0o755
            info.mtime = epoch
            archive.addfile(info)
        for name, (data, mode) in sorted(
            files.items()
        ):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = mode
            info.mtime = epoch
            archive.addfile(
                info, io.BytesIO(data)
            )
    result = io.BytesIO()
    with gzip.GzipFile(
        fileobj=result,
        mode="wb",
        filename="",
        mtime=epoch,
        compresslevel=9,
    ) as stream:
        stream.write(raw.getvalue())
    return result.getvalue()


def deb(
    root: Path,
    epoch: int,
    maintainer: str,
    engram=None,
) -> bytes:
    """Construye un paquete Debian 2.0."""
    release = version(root)
    if engram is None:
        candidate = root / "vendor/engram.tar.gz"
        if candidate.exists():
            engram = candidate
    files = payload(root, engram)
    installed = (
        sum(
            len(data)
            for data, _ in files.values()
        )
        + 1023
    ) // 1024
    architecture = "amd64" if engram else "all"
    control = (
        "Package: pxp-harness\n"
        f"Version: {release}-1\n"
        "Section: devel\nPriority: optional\n"
        f"Architecture: {architecture}\n"
        f"Maintainer: {maintainer}\n"
        "Depends: python3 (>= 3.10)\n"
        "Recommends: git, neovim\n"
        "Suggests: ruff (>= 0.16.4)\n"
        f"Installed-Size: {installed}\n"
        "Homepage: https://github.com/"
        "SrLambda/pxp-harness\n"
        "Description: Project context "
        "for Codex CLI\n"
        " Project-local modes, prompts "
        "and standards.\n"
    )
    postinst = (
        "#!/bin/sh\nset -e\n"
        'if [ "$1" = configure ]; then\n'
        "  py3compile -p pxp-harness "
        "/usr/share/pxp-harness/pxp_harness\n"
        "fi\n"
    )
    prerm = (
        "#!/bin/sh\nset -e\n"
        "py3clean -p pxp-harness "
        "/usr/share/pxp-harness/pxp_harness\n"
    )
    checksums = "".join(
        hashlib.md5(data).hexdigest()
        + "  "
        + name
        + "\n"
        for name, (data, _) in sorted(
            files.items()
        )
    )
    metadata = {
        "control": (control.encode(), 0o644),
        "postinst": (postinst.encode(), 0o755),
        "prerm": (prerm.encode(), 0o755),
        "md5sums": (checksums.encode(), 0o644),
    }
    members = {
        "debian-binary": b"2.0\n",
        "control.tar.gz": compressed_tar(
            metadata, epoch
        ),
        "data.tar.gz": compressed_tar(
            files, epoch
        ),
    }
    result = bytearray(b"!<arch>\n")
    for name, data in members.items():
        header = (
            f"{name + '/':<16}{epoch:<12}"
            f"{0:<6}{0:<6}{'100644':<8}"
            f"{len(data):<10}`\n"
        ).encode("ascii")
        if len(header) != 60:
            raise ValueError("Invalid ar header.")
        result.extend(header)
        result.extend(data)
        if len(data) % 2:
            result.extend(b"\n")
    return bytes(result)


def build_arch(
    folder: Path, output: Path, epoch: int
) -> Path:
    """Ejecuta makepkg sin instalar nada."""
    executable = shutil.which("makepkg")
    if executable is None:
        raise ValueError("makepkg not available.")
    with tempfile.TemporaryDirectory(
        prefix="pxp-arch-"
    ) as temporary:
        work = Path(temporary)
        for path in folder.iterdir():
            shutil.copy2(path, work / path.name)
        environment = dict(os.environ)
        environment["PKGDEST"] = str(work)
        environment["SOURCE_DATE_EPOCH"] = str(
            epoch
        )
        subprocess.run(
            [
                executable,
                "--cleanbuild",
                "--noconfirm",
            ],
            cwd=work,
            env=environment,
            check=True,
            shell=False,
        )
        packages = list(
            work.glob("*.pkg.tar.zst")
        )
        if len(packages) != 1:
            raise ValueError(
                "Expected one Arch package."
            )
        destination = output / packages[0].name
        shutil.copy2(packages[0], destination)
    return destination


def build(
    root: Path,
    output: Path,
    epoch: int,
    maintainer: str,
    arch=False,
    engram=None,
) -> None:
    """Construye paquetes y recetas nativas."""
    if engram is None:
        candidate = root / "vendor/engram.tar.gz"
        if candidate.exists():
            engram = candidate
    if output.exists() and any(output.iterdir()):
        raise ValueError(
            "Output directory must be empty."
        )
    output.mkdir(parents=True, exist_ok=True)
    release = version(root)
    source_name = (
        f"pxp-harness-{release}-source.tar.gz"
    )
    sources = {
        f"pxp-harness-{release}/{name}": (
            data,
            0o644,
        )
        for name, data in source_files(
            root
        ).items()
    }
    if engram is not None:
        engram_payload(root, engram)
        sources[
            f"pxp-harness-{release}/"
            "vendor/engram.tar.gz"
        ] = (engram.read_bytes(), 0o644)
    source = output / source_name
    source.write_bytes(
        compressed_tar(sources, epoch)
    )
    digest = hashlib.sha256(
        source.read_bytes()
    ).hexdigest()
    recipe = (
        (root / "packaging/arch/PKGBUILD.in")
        .read_text()
        .replace("@VERSION@", release)
        .replace("@SHA256@", digest)
        .replace(
            "@ARCH@",
            "x86_64" if engram else "any",
        )
    )
    folder = output / "arch"
    folder.mkdir()
    (folder / "PKGBUILD").write_text(recipe)
    shutil.copy2(source, folder / source_name)
    architecture = "amd64" if engram else "all"
    package = (
        output / f"pxp-harness_{release}-1_"
        f"{architecture}.deb"
    )
    package.write_bytes(
        deb(root, epoch, maintainer, engram)
    )
    bundle = output / (
        f"pxp-harness-{release}-arch-build.tar.gz"
    )
    bundle.write_bytes(
        compressed_tar(
            {
                "PKGBUILD": (
                    recipe.encode(),
                    0o644,
                ),
                source_name: (
                    source.read_bytes(),
                    0o644,
                ),
            },
            epoch,
        )
    )
    artifacts = [source, package, bundle]
    if arch:
        artifacts.append(
            build_arch(folder, output, epoch)
        )
    hashes = {
        path.name: hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in artifacts
    }
    manifest = {
        "version": release,
        "engram": json.loads(
            (
                root
                / "packaging/engram/lock.json"
            ).read_text()
        )
        if engram
        else None,
        "builder_python": sys.version.split()[0],
        "package_release": 1,
        "source_date_epoch": epoch,
        "maintainer": maintainer,
        "sha256": hashes,
        "codex_config": "project-local .pxp only",
        "license_notice": (
            "Upstream full notice absent"
        ),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    (output / "SHA256SUMS").write_text(
        "".join(
            f"{value}  {name}\n"
            for name, value in sorted(
                hashes.items()
            )
        )
    )


def main() -> int:
    """Ejecuta el modo solicitado."""
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(
        dest="action", required=True
    )
    package = sub.add_parser("build")
    package.add_argument(
        "--output", type=Path, required=True
    )
    package.add_argument(
        "--arch", action="store_true"
    )
    package.add_argument(
        "--epoch",
        type=int,
        default=int(
            os.environ.get(
                "SOURCE_DATE_EPOCH", "1700000000"
            )
        ),
    )
    package.add_argument(
        "--maintainer", default=MAINTAINER
    )
    package.add_argument(
        "--engram-archive", type=Path
    )
    install = sub.add_parser("stage")
    install.add_argument(
        "--destdir", type=Path, required=True
    )
    args = parser.parse_args()
    try:
        if args.action == "stage":
            stage(ROOT, args.destdir)
        else:
            if not 0 <= args.epoch <= 4294967295:
                raise ValueError(
                    "Epoch outside gzip range."
                )
            if not re.fullmatch(
                r"[^<>\n]+ <[^<>\n@]+@[^<>\n@]+>",
                args.maintainer,
            ):
                raise ValueError(
                    "Invalid maintainer field."
                )
            build(
                ROOT,
                args.output,
                args.epoch,
                args.maintainer,
                args.arch,
                args.engram_archive,
            )
    except (
        OSError,
        ValueError,
        subprocess.SubprocessError,
    ) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
