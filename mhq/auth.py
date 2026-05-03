from __future__ import annotations

import os
from pathlib import Path

from mhq.exceptions import ITMatrixConfigError


def resolve_key(key: str | None, key_file: str | os.PathLike[str] | None) -> str:
    """Resolve an API key from an explicit value, environment, or `.itmkey` file."""

    if key:
        return key.strip()
    env_key = os.getenv("ITM_KEY")
    if env_key:
        return env_key.strip()
    file_path = Path(key_file) if key_file is not None else Path.cwd() / ".itmkey"
    if file_path.exists():
        return file_path.read_text(encoding="utf-8").strip()
    raise ITMatrixConfigError("Provide an ITMatrix API key, set ITM_KEY, or create .itmkey in the project root.")


def resolve_base_url(base_url: str | None) -> str:
    """Resolve and normalize the HTTP base URL."""

    return (base_url or os.getenv("ITM_BASE_URL") or "https://api.itmatrix.io").rstrip("/")
