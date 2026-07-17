"""Ported from test/build.test.ts."""
from __future__ import annotations

import os

import pytest

from graphkeeper.build import build
from graphkeeper.store import graph_file_path, read_store
from graphkeeper.types import BuildOptions

from .conftest import cleanup, commit_all, make_temp_git_repo, write_file


@pytest.fixture
def temp_repo():
    dirs = []

    def _make():
        d = make_temp_git_repo()
        dirs.append(d)
        return d

    yield _make
    for d in dirs:
        cleanup(d)


def test_mines_co_change_and_writes_store(temp_repo):
    repo = temp_repo()
    write_file(repo, "a.py", "1")
    write_file(repo, "b.py", "1")
    commit_all(repo, "add a and b together")

    result = build(repo, BuildOptions(skip_graphify=True))

    assert result.output_path == graph_file_path(repo)
    assert os.path.exists(result.output_path)
    assert result.store.commits_analyzed > 0
    assert any(
        (e.a == "a.py" and e.b == "b.py") or (e.a == "b.py" and e.b == "a.py") for e in result.store.co_change
    )
    assert result.store.graphify.enriched is False
    assert "--no-graphify" in (result.store.graphify.skipped_reason or "")


def test_persists_store_readable_back(temp_repo):
    repo = temp_repo()
    write_file(repo, "x.py", "1")
    commit_all(repo, "add x")
    build(repo, BuildOptions(skip_graphify=True))

    read_back = read_store(repo)
    assert read_back.version == 1
    assert read_back.repo_path == repo


def test_honors_max_files_per_commit(temp_repo):
    repo = temp_repo()
    for i in range(10):
        write_file(repo, f"f{i}.py", "1")
    commit_all(repo, "touch 10 files")

    result = build(repo, BuildOptions(skip_graphify=True, max_files_per_commit=5))
    assert result.store.commits_skipped == 1
    assert result.store.co_change == []
