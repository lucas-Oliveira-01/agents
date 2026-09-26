from __future__ import annotations

import hashlib
import os
import subprocess
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


_SKIP_DIRS = {".git", ".audit", "node_modules", "__pycache__", ".pytest_cache"}
_BINARY_PROBE = 8192


class DiscoverySecurityError(RuntimeError):
    """Raised when a target contains an unsafe filesystem entry."""


@dataclass(frozen=True)
class FileRecord:
    path: str
    size: int
    sha256: Optional[str]
    binary: bool


@dataclass(frozen=True)
class GitMetadata:
    is_repository: bool
    revision: Optional[str]
    branch: Optional[str]
    working_tree_dirty: Optional[bool]
    tracked_paths: Tuple[str, ...]
    remote_url: Optional[str]


@dataclass(frozen=True)
class DiscoverySnapshot:
    root: Path
    files: Tuple[FileRecord, ...]
    git: GitMetadata

    @property
    def file_count(self) -> int:
        return len(self.files)

    def file(self, relative_path: str) -> Optional[FileRecord]:
        wanted = relative_path.replace(os.sep, "/")
        return next((item for item in self.files if item.path == wanted), None)


def _run_git(root: Path, *args: str) -> Tuple[bool, str]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return False, ""
    return completed.returncode == 0, completed.stdout.strip()


def _is_binary(path: Path) -> bool:
    try:
        data = path.read_bytes()[:_BINARY_PROBE]
    except OSError:
        return False
    return b"\x00" in data


def _sha256(path: Path) -> Optional[str]:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _validate_entry(path: Path) -> None:
    """Reject filesystem entries that could escape or block discovery."""
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise DiscoverySecurityError(f"Unable to inspect target entry: {path}") from exc
    if stat.S_ISLNK(mode):
        raise DiscoverySecurityError(f"Symlink entries are not permitted during discovery: {path}")
    if not stat.S_ISREG(mode):
        raise DiscoverySecurityError(f"Special filesystem entries are not permitted during discovery: {path}")


def _discover_files(root: Path) -> Tuple[FileRecord, ...]:
    records = []
    for current_root, dirs, filenames in os.walk(root, followlinks=False):
        for dirname in list(dirs):
            candidate = Path(current_root) / dirname
            if candidate.is_symlink():
                raise DiscoverySecurityError(
                    f"Symlink directories are not permitted during discovery: {candidate}"
                )
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS)
        for filename in sorted(filenames):
            path = Path(current_root) / filename
            _validate_entry(path)
            try:
                size = path.stat().st_size
            except OSError:
                continue
            relative = path.relative_to(root).as_posix()
            records.append(
                FileRecord(
                    path=relative,
                    size=size,
                    sha256=_sha256(path),
                    binary=_is_binary(path),
                )
            )
    return tuple(records)


def _discover_git(root: Path) -> GitMetadata:
    ok, inside = _run_git(root, "rev-parse", "--is-inside-work-tree")
    if not ok or inside.lower() != "true":
        return GitMetadata(False, None, None, None, (), None)

    _, revision = _run_git(root, "rev-parse", "HEAD")
    _, branch = _run_git(root, "branch", "--show-current")
    _, remote_url = _run_git(root, "remote", "get-url", "origin")
    status_ok, status = _run_git(root, "status", "--porcelain=v1", "--untracked-files=all")
    _, tracked = _run_git(root, "ls-files")

    return GitMetadata(
        is_repository=True,
        revision=revision or None,
        branch=branch or None,
        working_tree_dirty=(bool(status) if status_ok else None),
        tracked_paths=tuple(line for line in tracked.splitlines() if line),
        remote_url=remote_url or None,
    )


def discover(root: str) -> DiscoverySnapshot:
    project_root = Path(root).expanduser().resolve()
    if not project_root.is_dir():
        raise ValueError(f"Target is not a directory: {project_root}")
    return DiscoverySnapshot(
        root=project_root,
        files=_discover_files(project_root),
        git=_discover_git(project_root),
    )
