"""Ensure the repository's ``src`` directory is importable in CLI runs.

Python imports ``sitecustomize`` automatically during interpreter startup when
it is present on ``sys.path``. Since the project keeps all importable packages
under ``src/`` and uses ``package-mode = false`` in uv, commands like
``python -m evaluation.scripts.run_batch_evaluation`` would otherwise fail
before the target module has a chance to adjust ``sys.path`` itself.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent / "src"

if _SRC_DIR.is_dir():
    src_path = str(_SRC_DIR)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

