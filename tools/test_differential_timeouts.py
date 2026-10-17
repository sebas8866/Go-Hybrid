"""Timeouts are corpus disagreements, not reasons to abandon the remaining cases."""

import contextlib
import io
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import differential_loop


class DifferentialTimeoutTests(unittest.TestCase):
    def test_checker_timeout_returns_failed_reject_case(self):
        with patch.object(
            differential_loop.subprocess, "run",
            side_effect=subprocess.TimeoutExpired("hyb check", 60),
        ):
            ok, detail = differential_loop.checker_rejects("hyb", "input.hy", "A1")

        self.assertFalse(ok)
        self.assertIn("checker timed out", detail)

    def test_build_timeout_returns_failed_case(self):
        with patch.object(
            differential_loop.subprocess, "run",
            side_effect=subprocess.TimeoutExpired("hyb build", 300),
        ):
            ok, detail = differential_loop.build_and_run("hyb", "input.hy", "/tmp")

        self.assertFalse(ok)
        self.assertIn("build timed out", detail)

    def test_run_timeout_returns_failed_case(self):
        completed = subprocess.CompletedProcess(["hyb", "build"], 0, "", "")
        with patch.object(
            differential_loop.subprocess, "run",
            side_effect=[completed, subprocess.TimeoutExpired("a.out", 60)],
        ), patch.object(differential_loop.os.path, "exists", return_value=True):
            ok, detail = differential_loop.build_and_run("hyb", "input.hy", "/tmp")

        self.assertFalse(ok)
        self.assertIn("run timed out", detail)

    def test_first_case_timeout_does_not_skip_later_cases(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            binary = root / "hyb"
            binary.write_text("fake; subprocess is mocked", encoding="utf-8")
            corpus = root / "corpus"
            corpus.mkdir()
            for name in ("01-times-out.hy", "02-runs.hy"):
                (corpus / name).write_text(
                    "// EXPECTED-VERDICT: ACCEPT\nfn main() {}\n", encoding="utf-8"
                )

            completed = subprocess.CompletedProcess(["hyb"], 0, "", "")
            output = io.StringIO()
            with patch.object(
                differential_loop.subprocess,
                "run",
                side_effect=[
                    subprocess.TimeoutExpired("hyb build", 300),
                    completed,
                    completed,
                ],
            ) as run, patch.object(
                differential_loop.os.path, "exists", return_value=True
            ), patch.object(
                sys, "argv", ["differential_loop", "--bin", str(binary), "--corpus", str(corpus)]
            ), contextlib.redirect_stdout(output):
                result = differential_loop.main()

        self.assertEqual(result, 1)
        self.assertEqual(run.call_count, 3)
        self.assertIn("FAIL  01-times-out.hy", output.getvalue())
        self.assertIn("PASS  02-runs.hy", output.getvalue())
        self.assertIn("differential accept-side (build+run): 1/2", output.getvalue())


if __name__ == "__main__":
    unittest.main()
