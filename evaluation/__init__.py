"""Shim package that exposes ``src/evaluation`` for ``python -m`` execution."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
_PKG = _SRC / "evaluation"

src_path = str(_SRC)
if src_path not in sys.path:
    sys.path.insert(0, src_path)

__path__ = [str(_PKG)]
