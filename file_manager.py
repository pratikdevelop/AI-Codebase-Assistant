"""
FileManager: handles reading, writing, creating, deleting,
and listing files inside the indexed project directory.

Security: all operations are strictly sandboxed to the indexed
project root — no path traversal outside it is allowed.
"""

import os
from pathlib import Path
from typing import Optional


class FileManager:
    def __init__(self):
        self._root: Optional[Path] = None

    def set_root(self, path: str):
        self._root = Path(path).resolve()

    def get_root(self) -> Optional[str]:
        return str(self._root) if self._root else None

    def _safe_path(self, relative_path: str) -> Path:
        """Resolve path and ensure it stays inside project root."""
        if not self._root:
            raise RuntimeError("No project indexed yet.")
        target = (self._root / relative_path).resolve()
        if not str(target).startswith(str(self._root)):
            raise PermissionError(f"Path traversal blocked: {relative_path}")
        return target

    # ── List ──────────────────────────────────────────────────────────────────

    def list_tree(self) -> dict:
        """Return the full file tree of the indexed project."""
        if not self._root:
            raise RuntimeError("No project indexed yet.")
        return self._build_tree(self._root)

    def _build_tree(self, path: Path) -> dict:
        IGNORE = {"node_modules", ".git", "__pycache__", ".venv", "venv",
                  "dist", "build", ".next", "vendor", "faiss_index"}
        node = {
            "name": path.name,
            "path": str(path.relative_to(self._root)),
            "type": "dir" if path.is_dir() else "file",
        }
        if path.is_dir():
            children = []
            try:
                for child in sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name)):
                    if child.name in IGNORE or child.name.startswith("."):
                        continue
                    children.append(self._build_tree(child))
            except PermissionError:
                pass
            node["children"] = children
        return node

    # ── Read ──────────────────────────────────────────────────────────────────

    def read_file(self, relative_path: str) -> dict:
        path = self._safe_path(relative_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")
        if not path.is_file():
            raise IsADirectoryError(f"Path is a directory: {relative_path}")
        content = path.read_text(encoding="utf-8", errors="replace")
        return {
            "path": relative_path,
            "content": content,
            "lines": content.count("\n") + 1,
            "size": path.stat().st_size,
        }

    # ── Write (create or overwrite) ───────────────────────────────────────────

    def write_file(self, relative_path: str, content: str) -> dict:
        path = self._safe_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        existed = path.exists()
        path.write_text(content, encoding="utf-8")
        return {
            "path": relative_path,
            "action": "updated" if existed else "created",
            "lines": content.count("\n") + 1,
            "size": path.stat().st_size,
        }

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete_file(self, relative_path: str) -> dict:
        path = self._safe_path(relative_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")
        path.unlink()
        return {"path": relative_path, "action": "deleted"}

    # ── Rename / Move ─────────────────────────────────────────────────────────

    def rename_file(self, old_path: str, new_path: str) -> dict:
        src = self._safe_path(old_path)
        dst = self._safe_path(new_path)
        if not src.exists():
            raise FileNotFoundError(f"File not found: {old_path}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        return {"old_path": old_path, "new_path": new_path, "action": "renamed"}