"""AIM OCR helper package."""

from __future__ import annotations

from importlib import metadata

try:
    __version__ = metadata.version("aim")
except metadata.PackageNotFoundError:  # pragma: no cover - during local execution only
    __version__ = "0.1.0"

__all__ = ["__version__"]
