"""Styles package exports."""

from pathlib import Path


def load_stylesheet() -> str:
    """Reads and returns the Apple Music dark QSS stylesheet."""
    qss_path = Path(__file__).parent / "apple_music_dark.qss"
    if qss_path.exists():
        return qss_path.read_text(encoding="utf-8")
    return ""
