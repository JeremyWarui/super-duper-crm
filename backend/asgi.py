"""The ASGI app for hosts that load a module from this folder, such as Vercel."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from backend.main import app  # noqa: E402

__all__ = ["app"]
