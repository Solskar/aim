"""Command line interface to run OCR with Tesseract."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable


class TesseractNotAvailableError(RuntimeError):
    """Raised when Tesseract cannot be located on the system."""


def resolve_tesseract(executable: str | None = None) -> Path:
    """Return the path to the Tesseract executable.

    Parameters
    ----------
    executable:
        Optional explicit path provided by the user.

    Raises
    ------
    TesseractNotAvailableError
        If no executable can be found.
    """

    if executable:
        explicit = Path(executable).expanduser()
        if explicit.is_file():
            return explicit
        raise TesseractNotAvailableError(
            f"Le binaire Tesseract spécifié '{explicit}' est introuvable."
        )

    auto_detected = shutil.which("tesseract")
    if auto_detected:
        return Path(auto_detected)

    raise TesseractNotAvailableError(
        "Tesseract n'est pas disponible. Exécutez le script install.ps1 pour l'installer."
    )


def get_tesseract_version(executable: str | None = None) -> str:
    """Return the version string reported by Tesseract."""

    tesseract_path = resolve_tesseract(executable)
    completed = subprocess.run(
        [str(tesseract_path), "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def run_ocr(image_path: Path, *, lang: str = "eng", executable: str | None = None) -> str:
    """Extract text from an image using pytesseract."""

    from PIL import Image
    import pytesseract

    tesseract_path = resolve_tesseract(executable)
    pytesseract.pytesseract.tesseract_cmd = str(tesseract_path)

    with Image.open(image_path) as img:
        text = pytesseract.image_to_string(img, lang=lang)
    return text.strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aim-cli",
        description="Utilitaire OCR utilisant Tesseract et pytesseract.",
    )
    parser.add_argument(
        "image",
        nargs="?",
        help="Fichier image à analyser (PNG, JPEG, etc.).",
    )
    parser.add_argument(
        "--lang",
        default="eng",
        help="Code langue Tesseract à utiliser (defaut: eng).",
    )
    parser.add_argument(
        "--tesseract",
        help="Chemin personnalisé vers l'exécutable Tesseract.",
    )
    parser.add_argument(
        "--show-version",
        action="store_true",
        help="Affiche la version de Tesseract détectée et quitte.",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.show_version:
        try:
            print(get_tesseract_version(args.tesseract))
        except TesseractNotAvailableError as exc:
            parser.error(str(exc))
        except subprocess.CalledProcessError as exc:  # pragma: no cover - depends on system
            parser.error(f"Impossible d'interroger Tesseract: {exc}")
        return

    if not args.image:
        parser.error(
            "Vous devez fournir un fichier image ou utiliser l'option --show-version."
        )

    image_path = Path(args.image)
    if not image_path.exists():
        parser.error(f"Le fichier '{image_path}' est introuvable.")

    try:
        text = run_ocr(image_path, lang=args.lang, executable=args.tesseract)
    except TesseractNotAvailableError as exc:
        parser.error(str(exc))
    except subprocess.CalledProcessError as exc:  # pragma: no cover - depends on system
        parser.error(f"L'exécution de Tesseract a échoué: {exc}")
    except Exception as exc:  # pragma: no cover - unexpected runtime issues
        parser.error(f"Une erreur inattendue est survenue: {exc}")
    else:
        sys.stdout.write(text + "\n")


if __name__ == "__main__":  # pragma: no cover - module entry point
    main()
