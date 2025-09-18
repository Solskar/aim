"""Tests pour le module aim.cli."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from aim import cli


class ResolveTesseractTests(unittest.TestCase):
    def test_explicit_path_missing(self) -> None:
        with self.assertRaises(cli.TesseractNotAvailableError):
            cli.resolve_tesseract("C:/invalid/tesseract.exe")

    @mock.patch("shutil.which", return_value=None)
    def test_auto_detection_missing(self, which: mock.Mock) -> None:
        with self.assertRaises(cli.TesseractNotAvailableError):
            cli.resolve_tesseract()
        which.assert_called_once_with("tesseract")


class GetTesseractVersionTests(unittest.TestCase):
    @mock.patch("aim.cli.subprocess.run")
    @mock.patch("aim.cli.resolve_tesseract")
    def test_get_tesseract_version(self, resolve: mock.Mock, run: mock.Mock) -> None:
        resolve.return_value = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")
        run.return_value = mock.Mock(stdout="tesseract 5.0.0", returncode=0)

        version = cli.get_tesseract_version()

        self.assertEqual(version, "tesseract 5.0.0")
        run.assert_called_once()
        args, kwargs = run.call_args
        self.assertIn("--version", args[0])
        self.assertTrue(kwargs["check"])  # type: ignore[index]


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
