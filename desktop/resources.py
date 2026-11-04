"""Portable resource paths for development and PyInstaller builds."""
from pathlib import Path
import sys

def project_root() -> Path:
    # PyInstaller extracts bundled read-only resources under _MEIPASS.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent

def asset_path(*parts: str) -> Path:
    return project_root() / "assets" / Path(*parts)

# Made By PeterParker 🕷️
