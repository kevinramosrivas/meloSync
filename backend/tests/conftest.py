"""Pytest configuration and path setup."""

from pathlib import Path
import sys

# Ensure backend and backend/src are discoverable
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))
