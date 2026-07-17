"""Ported from test/store.test.ts."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone

import pytest

from graphkeeper.store import (
    PathSafetyError,
    assert_path_inside,
    ensure_graphkeeper_subdir,
    graph_file_path,
    read_store,
    resolve_repo_root,
    write_store,
)
from graphkeeper.types import CoChangeEdge, GraphifyEnrichment, GraphKeeperStore

from .conftest import cleanup


@pytest.fixture
def temp_dir():
    dirs = []

    def _make():
        raw = tempfile.mkdtemp(prefix="gk-store-test-")
        real = os.path.realpath(raw)
        dirs.append(real)
        return real

    yield _make
    for d in dirs:
        cleanup(d)


def _make_store(repo_path: str) -> GraphKeeperStore:
    return GraphKeeperStore(
        version=1,
        generated_at=datetime.now(timezone.utc).isoformat(),
        repo_path=repo_path,
        commits_analyzed=1,
        commits_skipped=0,
        co_change=[CoChangeEdge(a="a.py", b="b.py", count=1)],
        file_commit_counts={"a.py": 1, "b.py": 1},
        graphify=GraphifyEnrichment(enriched=False, version=None, skipped_reason="test"),
    )


class TestResolveRepoRoot:
    def test_resolves_valid_directory(self, temp_dir):
        d = temp_dir()
        assert resolve_repo_root(d) == d

    def test_raises_for_nonexistent_path(self):
        with pytest.raises(PathSafetyError):
            resolve_repo_root("/definitely/does/not/exist/xyz")

    def test_raises_when_path_is_file_not_directory(self, temp_dir):
        d = temp_dir()
        file_path = os.path.join(d, "file.txt")
        with open(file_path, "w", encoding="utf-8") as fh:
            fh.write("hi")
        with pytest.raises(PathSafetyError):
            resolve_repo_root(file_path)


class TestAssertPathInside:
    def test_passes_for_nested_path(self, temp_dir):
        d = temp_dir()
        child = os.path.join(d, "sub", "deep")
        assert_path_inside(child, d)  # does not raise

    def test_passes_when_child_equals_parent(self, temp_dir):
        d = temp_dir()
        assert_path_inside(d, d)  # does not raise

    def test_raises_when_symlink_escapes_parent(self, temp_dir):
        parent = temp_dir()
        outside = temp_dir()
        link = os.path.join(parent, "escape")
        os.symlink(outside, link)
        with pytest.raises(PathSafetyError):
            assert_path_inside(link, parent)


class TestEnsureGraphkeeperSubdir:
    def test_creates_graphkeeper_and_nested_subdirectories(self, temp_dir):
        repo = temp_dir()
        d = ensure_graphkeeper_subdir(repo, "graphify-raw")
        assert os.path.exists(d)
        assert d == os.path.join(repo, ".graphkeeper", "graphify-raw")

    def test_refuses_preexisting_malicious_symlink(self, temp_dir):
        repo = temp_dir()
        outside = temp_dir()
        os.symlink(outside, os.path.join(repo, ".graphkeeper"))
        with pytest.raises(PathSafetyError):
            ensure_graphkeeper_subdir(repo)


class TestWriteReadStore:
    def test_round_trips_store_through_disk(self, temp_dir):
        repo = temp_dir()
        store = _make_store(repo)
        written = write_store(repo, store)
        assert written == graph_file_path(repo)
        read_back = read_store(repo)
        assert [(e.a, e.b, e.count) for e in read_back.co_change] == [
            (e.a, e.b, e.count) for e in store.co_change
        ]
        assert read_back.repo_path == repo

    def test_read_store_respects_explicit_override_path(self, temp_dir):
        repo = temp_dir()
        store = _make_store(repo)
        custom_path = os.path.join(repo, "custom.json")
        with open(custom_path, "w", encoding="utf-8") as fh:
            json.dump(store.to_dict(), fh)
        read_back = read_store(repo, custom_path)
        assert read_back.commits_analyzed == 1

    def test_raises_path_safety_error_when_no_store_exists(self, temp_dir):
        repo = temp_dir()
        with pytest.raises(PathSafetyError):
            read_store(repo)
