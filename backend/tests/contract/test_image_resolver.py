"""Phase 10.1: image resolver contract tests.

Tests for backend/app/services/image_resolver.py — URL to local path resolution.
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from backend.app.services.image_resolver import resolve_image_path


# ── Valid resolution ───────────────────────────────────────────────────────

def test_valid_relative_url_resolves(tmp_path):
    """Valid /static/defects/YYYYMMDD/file.jpg resolves to local absolute path."""
    # Create a fake image
    subdir = tmp_path / "20260526"
    subdir.mkdir(parents=True)
    img = subdir / "test.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg")

    with patch(
        "backend.app.services.image_resolver.get_static_defects_root",
        return_value=tmp_path,
    ):
        result = resolve_image_path("/static/defects/20260526/test.jpg")
        assert result == img.resolve()
        assert result.is_absolute()
        assert result.is_file()


def test_valid_relative_path_resolves(tmp_path):
    """Relative path without /static/defects/ prefix also works."""
    subdir = tmp_path / "20260526"
    subdir.mkdir(parents=True)
    img = subdir / "abc.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg")

    with patch(
        "backend.app.services.image_resolver.get_static_defects_root",
        return_value=tmp_path,
    ):
        result = resolve_image_path("20260526/abc.jpg")
        assert result == img.resolve()


# ── Missing file ───────────────────────────────────────────────────────────

def test_missing_file_raises(tmp_path):
    """Missing image file raises ValueError."""
    with patch(
        "backend.app.services.image_resolver.get_static_defects_root",
        return_value=tmp_path,
    ):
        with pytest.raises(ValueError, match="not found"):
            resolve_image_path("/static/defects/20260526/nonexistent.jpg")


# ── Path traversal ─────────────────────────────────────────────────────────

def test_path_traversal_rejected(tmp_path):
    """Path traversal with .. is rejected."""
    with patch(
        "backend.app.services.image_resolver.get_static_defects_root",
        return_value=tmp_path,
    ):
        with pytest.raises(ValueError, match="traversal"):
            resolve_image_path("/static/defects/../../etc/passwd")


def test_double_dot_in_filename_rejected(tmp_path):
    """Path with .. in middle is rejected."""
    with patch(
        "backend.app.services.image_resolver.get_static_defects_root",
        return_value=tmp_path,
    ):
        with pytest.raises(ValueError, match="traversal"):
            resolve_image_path("/static/defects/20260526/../../../etc/passwd")


# ── External URLs ──────────────────────────────────────────────────────────

def test_http_url_rejected():
    """http:// URL is rejected."""
    with pytest.raises(ValueError, match="External URL"):
        resolve_image_path("http://example.com/image.jpg")


def test_https_url_rejected():
    """https:// URL is rejected."""
    with pytest.raises(ValueError, match="External URL"):
        resolve_image_path("https://example.com/image.jpg")


# ── Path outside root ──────────────────────────────────────────────────────

def test_absolute_path_outside_root_rejected(tmp_path):
    """Absolute path not starting with /static/defects/ is rejected."""
    with pytest.raises(ValueError, match="must start with"):
        resolve_image_path("/etc/passwd")


# ── Empty input ────────────────────────────────────────────────────────────

def test_empty_string_raises():
    """Empty image_url raises ValueError."""
    with pytest.raises(ValueError, match="empty"):
        resolve_image_path("")


def test_none_like_empty():
    """Whitespace-only image_url raises ValueError."""
    with pytest.raises(ValueError, match="empty"):
        resolve_image_path("   ")


# ── Nested directory traversal attempt ─────────────────────────────────────

def test_encoded_traversal_rejected(tmp_path):
    """Path that resolves outside root via absolute target is rejected."""
    # Create a file outside root
    outside = tmp_path.parent / "secret.jpg"
    outside.write_bytes(b"secret")

    with patch(
        "backend.app.services.image_resolver.get_static_defects_root",
        return_value=tmp_path,
    ):
        # This should fail because the resolved path won't be under tmp_path
        with pytest.raises(ValueError):
            resolve_image_path(f"/static/defects/../../../{outside.name}")
