"""File system utilities for session workspaces."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

from .sessions import ensure_within


def list_directory(base: Path, path: Path) -> Dict[str, object]:
    """Return metadata for files inside *path* relative to *base*."""

    target = ensure_within(base, path)
    items: List[Dict[str, object]] = []
    for entry in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        stat = entry.stat()
        items.append(
            {
                "name": entry.name,
                "path": str(entry.relative_to(base)),
                "isDir": entry.is_dir(),
                "size": stat.st_size,
                "modified": stat.st_mtime,
            }
        )
    return {
        "path": str(target.relative_to(base)),
        "items": items,
    }


def read_file(base: Path, path: Path) -> str:
    target = ensure_within(base, path)
    if target.is_dir():
        raise IsADirectoryError(str(path))
    return target.read_text(encoding="utf-8")


def write_file(base: Path, path: Path, content: str) -> None:
    target = ensure_within(base, path)
    if target.is_dir():
        raise IsADirectoryError(str(path))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def create_directory(base: Path, path: Path) -> None:
    target = ensure_within(base, path)
    target.mkdir(parents=True, exist_ok=True)


def delete_path(base: Path, path: Path) -> None:
    target = ensure_within(base, path)
    if target.is_dir():
        for root, dirs, files in os.walk(target, topdown=False):
            for name in files:
                (Path(root) / name).unlink()
            for name in dirs:
                (Path(root) / name).rmdir()
        target.rmdir()
    else:
        target.unlink(missing_ok=True)
