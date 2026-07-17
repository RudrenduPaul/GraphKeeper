"""
Mines `git log` history for file-level co-change: pairs of files that were
modified together in the same commit.

Ported from src/git.ts. Every `git` invocation uses an argv list passed
directly to the OS (`subprocess.run`, `shell=False`), never a shell string,
so commit messages, file paths, or repo paths can never be interpreted as
shell syntax.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .types import CoChangeEdge

# Marker used to split `git log` output into per-commit chunks. Chosen to be
# extremely unlikely to appear in a commit message or file path.
COMMIT_MARKER = "@@GK-COMMIT@@"

DEFAULT_MAX_FILES_PER_COMMIT = 100


class GitError(Exception):
    pass


def _run_git(repo_path: str, args: List[str]) -> "subprocess.CompletedProcess[str]":
    try:
        return subprocess.run(
            ["git", "-C", repo_path, *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as err:
        raise GitError("git is not installed or not on PATH.") from err
    except OSError as err:
        raise GitError(f"Failed to run git: {err}") from err


def assert_is_git_repo(repo_path: str) -> None:
    """Raises GitError if `repo_path` is not inside a git working tree."""
    result = _run_git(repo_path, ["rev-parse", "--is-inside-work-tree"])
    if result.returncode != 0:
        raise GitError(f'"{repo_path}" is not a git repository. {result.stderr.strip()}'.strip())


def unquote_git_path(raw: str) -> str:
    """Unquotes a git `--name-only` path entry. Git C-quotes paths
    containing unusual bytes (non-ASCII when core.quotePath is on, quotes,
    backslashes, control characters) by wrapping them in double quotes with
    backslash/octal escapes. Plain paths are returned unchanged."""
    if len(raw) < 2 or raw[0] != '"' or raw[-1] != '"':
        return raw
    inner = raw[1:-1]
    # Octal escapes are individual *bytes* of a (possibly multi-byte UTF-8)
    # sequence, so this must accumulate raw bytes and UTF-8-decode once at
    # the end -- decoding each escaped byte independently would mangle any
    # non-ASCII character spanning more than one byte.
    byte_values: List[int] = []
    i = 0
    n = len(inner)
    while i < n:
        ch = inner[i]
        if ch != "\\":
            # core.quotePath=true escapes every byte >= 0x80, so an
            # unescaped character here is always plain ASCII.
            byte_values.append(ord(ch))
            i += 1
            continue
        nxt = inner[i + 1] if i + 1 < n else None
        if nxt is None:
            byte_values.append(ord(ch))
            i += 1
            continue
        if "0" <= nxt <= "7":
            octal = inner[i + 1 : i + 4]
            try:
                code = int(octal, 8)
            except ValueError:
                code = ord(nxt)
            byte_values.append(code)
            i += 4
            continue
        if nxt == "n":
            byte_values.append(0x0A)
        elif nxt == "t":
            byte_values.append(0x09)
        elif nxt == "\\":
            byte_values.append(0x5C)
        elif nxt == '"':
            byte_values.append(0x22)
        else:
            byte_values.append(ord(nxt))
        i += 2
    return bytes(byte_values).decode("utf-8")


def _has_no_nul_byte(p: str) -> bool:
    """True if every character code in `p` is non-zero (i.e. no embedded
    NUL bytes)."""
    return "\0" not in p


def _is_safe_tracked_path(p: str) -> bool:
    """Rejects path entries that could escape the repo tree or aren't real
    tracked files."""
    if not p:
        return False
    if not _has_no_nul_byte(p):
        return False
    if p.startswith("/") or p.startswith("~"):
        return False
    segments = p.split("/")
    if any(s == ".." for s in segments):
        return False
    return True


@dataclass
class CoChangeMiningResult:
    co_change: List[CoChangeEdge] = field(default_factory=list)
    file_commit_counts: Dict[str, int] = field(default_factory=dict)
    commits_analyzed: int = 0
    commits_skipped: int = 0


def mine_co_change(repo_path: str, max_files_per_commit: Optional[int] = None) -> CoChangeMiningResult:
    """Mines `git log` history for file-level co-change: pairs of files that
    were modified together in the same commit. This is GraphKeeper's own
    signal, distinct from (and complementary to) symbol/call-graph
    extraction."""
    effective_max = max_files_per_commit if max_files_per_commit is not None else DEFAULT_MAX_FILES_PER_COMMIT
    assert_is_git_repo(repo_path)

    result = _run_git(
        repo_path,
        [
            "-c",
            "core.quotePath=true",
            "log",
            "--no-merges",
            f"--pretty=format:{COMMIT_MARKER}%H",
            "--name-only",
        ],
    )
    if result.returncode != 0:
        raise GitError(f"git log failed: {result.stderr.strip()}")

    stdout = result.stdout or ""
    if stdout.strip() == "":
        return CoChangeMiningResult()

    # Keyed by (a, b) tuples -- each commit's own file list is sorted before
    # pairing, so a < b lexicographically within every pair, making the
    # tuple an unambiguous key across all commits (no JSON-stringify trick
    # needed, unlike the TypeScript original, since Python tuples are
    # natively hashable).
    pair_counts: Dict[tuple, int] = {}
    file_commit_counts: Dict[str, int] = {}
    commits_analyzed = 0
    commits_skipped = 0

    chunks = stdout.split(COMMIT_MARKER)[1:]
    for chunk in chunks:
        newline_index = chunk.find("\n")
        files_raw = "" if newline_index == -1 else chunk[newline_index + 1 :]
        seen = []
        seen_set = set()
        for line in files_raw.split("\n"):
            candidate = line.strip()
            if not candidate:
                continue
            unquoted = unquote_git_path(candidate)
            if not _is_safe_tracked_path(unquoted):
                continue
            if unquoted not in seen_set:
                seen_set.add(unquoted)
                seen.append(unquoted)
        files = sorted(seen)

        if len(files) == 0:
            continue
        if len(files) > effective_max:
            commits_skipped += 1
            continue

        commits_analyzed += 1
        for f in files:
            file_commit_counts[f] = file_commit_counts.get(f, 0) + 1
        for idx in range(len(files)):
            for jdx in range(idx + 1, len(files)):
                a, b = files[idx], files[jdx]
                key = (a, b)
                pair_counts[key] = pair_counts.get(key, 0) + 1

    co_change = [CoChangeEdge(a=a, b=b, count=count) for (a, b), count in pair_counts.items()]
    co_change.sort(key=lambda e: e.count, reverse=True)

    return CoChangeMiningResult(
        co_change=co_change,
        file_commit_counts=file_commit_counts,
        commits_analyzed=commits_analyzed,
        commits_skipped=commits_skipped,
    )
