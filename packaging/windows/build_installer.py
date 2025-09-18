"""Build a Windows installer that bundles Tesseract."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional
from urllib.request import urlopen
import zipfile

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - fallback for Python < 3.11
    import tomli as tomllib  # type: ignore

DEFAULT_TESSERACT_URL = (
    "https://github.com/UB-Mannheim/tesseract/releases/download/"
    "v5.3.3.20231005/Tesseract-OCR-w64-5.3.3.20231005.zip"
)


def project_root() -> Path:
    """Return the repository root (two directories up from this file)."""

    return Path(__file__).resolve().parents[2]


def load_version(root: Path) -> str:
    """Extract the project version from pyproject.toml."""

    pyproject = root / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = data.get("project", {})
    version = project.get("version")
    if not version:
        raise RuntimeError("Impossible de récupérer la version depuis pyproject.toml")
    return str(version)


def run_pyinstaller(root: Path, dist_dir: Path, build_dir: Path, *, onefile: bool) -> None:
    """Invoke PyInstaller to build the application."""

    src_dir = root / "src"
    assets_dir = root / "assets"
    if not assets_dir.exists():
        raise RuntimeError("Le dossier assets/ est introuvable")

    add_data = f"{assets_dir}{os.pathsep}assets"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "rapid-shot-overlay",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(build_dir / "pyinstaller"),
        "--specpath",
        str(build_dir / "pyinstaller"),
        "--collect-submodules",
        "heat_overlay",
        "--collect-submodules",
        "cv2",
        "--collect-submodules",
        "PySide6",
        "--hidden-import",
        "pytesseract",
        "--hidden-import",
        "dxcam",
        "--add-data",
        add_data,
        "-p",
        str(src_dir),
        str(src_dir / "heat_overlay" / "app.py"),
    ]
    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")
    cmd.append("--noconsole")
    subprocess.check_call(cmd)


def _clean_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def ensure_bundle(dist_dir: Path, *, onefile: bool) -> tuple[Path, Path]:
    """Return the directory that must be shipped and the executable path."""

    if onefile:
        exe_path = dist_dir / "rapid-shot-overlay.exe"
        if not exe_path.exists():
            raise RuntimeError("Exécutable PyInstaller introuvable (rapid-shot-overlay.exe)")
        bundle_dir = dist_dir / "rapid-shot-overlay-bundle"
        if bundle_dir.exists():
            shutil.rmtree(bundle_dir)
        bundle_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(exe_path, bundle_dir / exe_path.name)
        return bundle_dir, bundle_dir / exe_path.name
    bundle_dir = dist_dir / "rapid-shot-overlay"
    exe_path = bundle_dir / "rapid-shot-overlay.exe"
    if not exe_path.exists():
        raise RuntimeError("Exécutable PyInstaller introuvable dans dist/rapid-shot-overlay/")
    return bundle_dir, exe_path


def download_tesseract(url: str, cache_dir: Path, *, skip_download: bool) -> Path:
    """Download and extract the portable Tesseract build."""

    cache_dir.mkdir(parents=True, exist_ok=True)
    archive_name = Path(url).name
    archive_path = cache_dir / archive_name
    if not archive_path.exists():
        if skip_download:
            raise RuntimeError(
                "Archive Tesseract absente du cache et téléchargement désactivé"
            )
        print(f"Téléchargement de Tesseract depuis {url} ...")
        with urlopen(url) as response, archive_path.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    extract_dir = cache_dir / "tesseract-portable"
    if extract_dir.exists():
        return extract_dir
    print(f"Extraction de {archive_path} ...")
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(cache_dir)
    candidate_dir: Optional[Path] = None
    for path in cache_dir.iterdir():
        if path.is_dir() and (path / "tesseract.exe").exists():
            candidate_dir = path
            break
    if candidate_dir is None:
        raise RuntimeError("Impossible de localiser tesseract.exe dans l'archive téléchargée")
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    shutil.move(str(candidate_dir), str(extract_dir))
    return extract_dir


def copy_tesseract(portable_dir: Path, bundle_dir: Path) -> Path:
    """Copy the portable Tesseract folder next to the executable."""

    target = bundle_dir / "tesseract"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(portable_dir, target)
    return target


def build_installer(
    script_path: Path,
    *,
    bundle_dir: Path,
    version: str,
    output_dir: Path,
    iscc_executable: str,
) -> None:
    """Invoke Inno Setup compiler if available."""

    if sys.platform != "win32":
        print("Compilation Inno Setup ignorée (plateforme non Windows)")
        return
    if shutil.which(iscc_executable) is None:
        print(f"Inno Setup introuvable sur PATH ({iscc_executable}) -> étape ignorée")
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        iscc_executable,
        f"/DMyAppVersion={version}",
        f"/DDistDir={bundle_dir}",
        f"/DOutputDir={output_dir}",
        str(script_path),
    ]
    subprocess.check_call(cmd)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Construit un exécutable PyInstaller et un installeur Windows"
    )
    parser.add_argument(
        "--tesseract-url",
        default=DEFAULT_TESSERACT_URL,
        help="URL de l'archive portable de Tesseract",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Ne pas télécharger Tesseract (utilise le cache existant)",
    )
    parser.add_argument(
        "--skip-pyinstaller",
        action="store_true",
        help="Suppose que dist/ contient déjà la build PyInstaller",
    )
    parser.add_argument(
        "--skip-installer",
        action="store_true",
        help="N'exécute pas Inno Setup même s'il est disponible",
    )
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="Construit l'exécutable PyInstaller en mode --onefile",
    )
    parser.add_argument(
        "--iscc",
        default="iscc",
        help="Chemin vers l'exécutable Inno Setup Compiler",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = project_root()
    dist_dir = root / "dist"
    build_dir = root / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    if not args.skip_pyinstaller:
        _clean_directory(dist_dir)
        run_pyinstaller(root, dist_dir, build_dir, onefile=args.onefile)
    bundle_dir, exe_path = ensure_bundle(dist_dir, onefile=args.onefile)
    print(f"Exécutable PyInstaller: {exe_path}")
    tesseract_dir = download_tesseract(
        args.tesseract_url, build_dir / "tesseract", skip_download=args.skip_download
    )
    copied_dir = copy_tesseract(tesseract_dir, bundle_dir)
    print(f"Tesseract copié dans: {copied_dir}")
    version = load_version(root)
    print(f"Version détectée: {version}")
    if args.skip_installer:
        print("Étape Inno Setup explicitement ignorée")
        return
    script_path = root / "packaging" / "windows" / "rapid-shot-overlay.iss"
    output_dir = dist_dir / "installer"
    build_installer(
        script_path,
        bundle_dir=bundle_dir,
        version=version,
        output_dir=output_dir,
        iscc_executable=args.iscc,
    )


if __name__ == "__main__":  # pragma: no cover - script entry point
    main()
