"""
Test helpers for building throwaway git repos, ported from test/test-helpers.ts.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List


def run_git(repo_dir: str, args: List[str]) -> None:
    result = subprocess.run(["git", "-C", repo_dir, *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")


def make_temp_git_repo() -> str:
    """Creates a throwaway git repo with an initial commit, for tests.
    Caller must clean up with `cleanup()`.

    Returns the *realpath* of the temp dir: on macOS, the system temp dir
    lives under `/var`, itself a symlink to `/private/var`. GraphKeeper's
    own `resolve_repo_root` follows symlinks (by design, for path-traversal
    safety), so tests must compare against the same realpath'd form or every
    equality assertion on a returned repo path spuriously fails on macOS.
    """
    raw_dir = tempfile.mkdtemp(prefix="graphkeeper-test-")
    real_dir = os.path.realpath(raw_dir)
    run_git(real_dir, ["init", "-q"])
    run_git(
        real_dir,
        ["-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "--allow-empty", "-q", "-m", "init"],
    )
    return real_dir


def write_file(repo_dir: str, rel_path: str, content: str) -> None:
    full = Path(repo_dir) / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def commit_all(repo_dir: str, message: str) -> None:
    run_git(repo_dir, ["add", "-A"])
    run_git(repo_dir, ["-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-q", "-m", message])


def cleanup(directory: str) -> None:
    shutil.rmtree(directory, ignore_errors=True)
