"""Shared pytest setup.

Several tests and scripts under `backend/` resolve dataset/policy paths as
plain relative strings (e.g. ``Path("dataset/Policy_agent/...")``), which
only exist under the repository root, not under `backend/`. Force the
working directory so `pytest` behaves the same whether invoked from the
repo root or from `backend/`.
"""

from __future__ import annotations

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
os.chdir(_REPO_ROOT)
