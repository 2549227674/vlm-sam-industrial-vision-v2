# Phase 10.1: Image URL resolver — converts defect image_url to local absolute path.
#
# Used by EdgeVlmProvider subprocess mode to pass real image paths to child process.
# Security: rejects external URLs, path traversal, and paths outside allowed root.

from __future__ import annotations

import os
from pathlib import Path


def get_static_defects_root() -> Path:
    """Return the resolved local root for static defect images.

    Mirrors the logic in backend/app/main.py and backend/app/routers/edge.py:
    - If DEFECT_STORAGE_DIR env var is set, use it.
    - Otherwise use <repo>/backend/static/defects.
    """
    env = os.environ.get("DEFECT_STORAGE_DIR")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parent.parent / "static" / "defects"


def resolve_image_path(image_url: str) -> Path:
    """Resolve a defect image_url to a local absolute Path.

    Args:
        image_url: The image_url from a Defect row, e.g.
            "/static/defects/20260526/abc123.jpg"

    Returns:
        Resolved absolute Path to the local image file.

    Raises:
        ValueError: If the URL is external, uses path traversal,
            resolves outside the allowed root, or the file does not exist.
    """
    if not image_url or not image_url.strip():
        raise ValueError("image_url is empty")

    url = image_url.strip()

    # Reject external URLs
    if url.startswith("http://") or url.startswith("https://"):
        raise ValueError(f"External URL not allowed: {url}")

    # Reject absolute paths outside static
    if url.startswith("/") and not url.startswith("/static/defects/"):
        raise ValueError(f"URL must start with /static/defects/: {url}")

    # Strip /static/defects/ prefix to get relative path
    prefix = "/static/defects/"
    if url.startswith(prefix):
        relative = url[len(prefix):]
    else:
        # Treat as relative path from defects root
        relative = url

    if not relative:
        raise ValueError(f"No filename in image_url: {image_url}")

    # Reject path traversal
    if ".." in relative:
        raise ValueError(f"Path traversal rejected: {image_url}")

    root = get_static_defects_root()
    resolved = (root / relative).resolve()

    # Verify resolved path is inside the allowed root
    try:
        resolved.relative_to(root)
    except ValueError:
        raise ValueError(
            f"Resolved path {resolved} is outside allowed root {root}"
        )

    # Verify file exists
    if not resolved.is_file():
        raise ValueError(f"Image file not found: {resolved}")

    return resolved
