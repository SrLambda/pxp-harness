"""Aislamiento de prompts por proyecto."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess as CP
from unittest.mock import patch

from pxp_harness.cli import main


class IsolationTests(unittest.TestCase):
    """Conserva la configuración global."""

    def test_projects_keep_independent_prompts(
        self,
    ):
        """Las opciones solo viajan por argv."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            home = base / "codex-home"
            home.mkdir()
            config = home / "config.toml"
            config.write_text(
                "# GLOBAL SENTINEL\n"
                'model="existing"\n'
            )
            before = config.read_bytes()
            projects = []
            with patch.dict(
                os.environ,
                {
                    "CODEX_HOME": str(home),
                },
            ):
                for name in ("one", "two"):
                    root = base / name
                    root.mkdir()
                    self.assertEqual(
                        main(["init"], cwd=root),
                        0,
                    )
                    length = (
                        "50"
                        if name == "one"
                        else "79"
                    )
                    self.assertEqual(
                        main(
                            [
                                "standards",
                                "configure",
                                "--line-length",
                                length,
                            ],
                            cwd=root,
                        ),
                        0,
                    )
                    source = root / "base.txt"
                    source.write_text(
                        "BASE " + name
                    )
                    self.assertEqual(
                        main(
                            [
                                "prompt",
                                "set",
                                "plan",
                                "base.txt",
                            ],
                            cwd=root,
                        ),
                        0,
                    )
                    with (
                        patch(
                            (
                                "pxp_harness."
                                "codex."
                                "shutil.which"
                            ),
                            return_value="codex",
                        ),
                        patch(
                            (
                                "pxp_harness."
                                "codex."
                                "subprocess.run"
                            ),
                            return_value=CP(
                                [], 0
                            ),
                        ) as run,
                    ):
                        self.assertEqual(
                            main(
                                ["chat", "task"],
                                cwd=root,
                            ),
                            0,
                        )
                    argv = run.call_args.args[0]
                    self.assertEqual(
                        argv[2],
                        "model_instructions_file="
                        + json.dumps(str(source)),
                    )
                    projects.append(
                        (root, source)
                    )
                root, source = projects[0]

                def edit(argv, **kwargs):
                    """Simula guardar texto."""
                    Path(argv[-1]).write_text(
                        "EDITED"
                    )
                    return CP(argv, 0)

                with (
                    patch(
                        (
                            "pxp_harness.editor."
                            "shutil.which"
                        ),
                        return_value="nvim",
                    ),
                    patch(
                        (
                            "pxp_harness.editor."
                            "subprocess.run"
                        ),
                        side_effect=edit,
                    ),
                ):
                    self.assertEqual(
                        main(
                            ["prompt", "edit"],
                            cwd=root,
                        ),
                        0,
                    )
            self.assertEqual(
                config.read_bytes(), before
            )
            self.assertEqual(
                projects[1][1].read_text(),
                "BASE two",
            )
            for root, _ in projects:
                self.assertFalse(
                    (root / ".codex").exists()
                )
            self.assertEqual(
                set(home.iterdir()), {config}
            )
