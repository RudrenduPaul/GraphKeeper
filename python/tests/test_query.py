"""Ported from test/query.test.ts."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from graphkeeper.query import find_graphify_node, normalize_file_arg, query_calls, query_co_change
from graphkeeper.types import CoChangeEdge, GraphifyEnrichment, GraphKeeperStore


def _make_store(
    repo_path: str = "/repo",
    graphify: Optional[GraphifyEnrichment] = None,
) -> GraphKeeperStore:
    return GraphKeeperStore(
        version=1,
        generated_at=datetime.now(timezone.utc).isoformat(),
        repo_path=repo_path,
        commits_analyzed=3,
        commits_skipped=0,
        co_change=[
            CoChangeEdge(a="src/a.py", b="src/b.py", count=5),
            CoChangeEdge(a="src/a.py", b="src/c.py", count=2),
            CoChangeEdge(a="src/x.py", b="src/y.py", count=9),
        ],
        file_commit_counts={"src/a.py": 5, "src/b.py": 5, "src/c.py": 2},
        graphify=graphify or GraphifyEnrichment(enriched=False, version=None, skipped_reason=None),
    )


class TestNormalizeFileArg:
    def test_strips_leading_dot_slash(self):
        assert normalize_file_arg(_make_store(), "./src/a.py") == "src/a.py"

    def test_relativizes_absolute_path_under_repo_path(self):
        assert normalize_file_arg(_make_store(repo_path="/repo"), "/repo/src/a.py") == "src/a.py"

    def test_leaves_absolute_path_outside_repo_path_unchanged(self):
        assert normalize_file_arg(_make_store(repo_path="/repo"), "/other/src/a.py") == "/other/src/a.py"


class TestQueryCoChange:
    def test_finds_co_change_partners_ranked_by_count(self):
        result = query_co_change(_make_store(), "src/a.py")
        assert [(r.file, r.count) for r in result.results] == [("src/b.py", 5), ("src/c.py", 2)]

    def test_matches_edge_regardless_of_side(self):
        result = query_co_change(_make_store(), "src/y.py")
        assert [(r.file, r.count) for r in result.results] == [("src/x.py", 9)]

    def test_returns_empty_for_file_with_no_co_change_history(self):
        result = query_co_change(_make_store(), "src/never-changed.py")
        assert result.results == []

    def test_respects_limit(self):
        result = query_co_change(_make_store(), "src/a.py", limit=1)
        assert len(result.results) == 1
        assert result.results[0].file == "src/b.py"


_NODES = [
    {"id": "src_a_add", "label": "add()", "file_type": "code", "source_file": "src/a.py"},
    {"id": "src_b_sum3", "label": "sum3()", "file_type": "code", "source_file": "src/b.py"},
    {"id": "src_a", "label": "a.py", "file_type": "code", "source_file": "src/a.py"},
]


class TestFindGraphifyNode:
    def test_matches_exact_label_with_parens(self):
        assert find_graphify_node(_NODES, "add()")["id"] == "src_a_add"

    def test_matches_bare_symbol_without_parens(self):
        assert find_graphify_node(_NODES, "add")["id"] == "src_a_add"

    def test_matches_case_insensitively(self):
        assert find_graphify_node(_NODES, "ADD")["id"] == "src_a_add"

    def test_returns_none_when_nothing_matches(self):
        assert find_graphify_node(_NODES, "doesNotExist") is None


class TestQueryCalls:
    def test_reports_unavailable_with_build_skip_reason(self):
        store = _make_store(
            graphify=GraphifyEnrichment(enriched=False, version=None, skipped_reason="graphify not installed")
        )
        result = query_calls(store, "add")
        assert result.available is False
        assert result.unavailable_reason == "graphify not installed"
        assert result.calls == []

    def test_returns_node_none_when_symbol_not_found_in_enriched_build(self):
        store = _make_store(
            graphify=GraphifyEnrichment(enriched=True, version="0.9.16", skipped_reason=None, nodes=_NODES)
        )
        result = query_calls(store, "nonexistentSymbol")
        assert result.available is True
        assert result.node is None

    def test_returns_callers_and_callees_for_found_symbol(self):
        edges = [
            {"source": "src_b_sum3", "target": "src_a_add", "relation": "calls", "confidence": "EXTRACTED"},
            {"source": "src_a", "target": "src_a_add", "relation": "contains", "confidence": "EXTRACTED"},
        ]
        store = _make_store(
            graphify=GraphifyEnrichment(enriched=True, version="0.9.16", skipped_reason=None, nodes=_NODES, edges=edges)
        )
        result = query_calls(store, "add")
        assert result.available is True
        assert result.node["id"] == "src_a_add"
        assert result.calls == []
        assert len(result.called_by) == 1
        assert result.called_by[0]["node"]["id"] == "src_b_sum3"

    def test_returns_callees_with_null_node_when_target_not_in_node_set(self):
        edges = [{"source": "src_a_add", "target": "src_unresolved_helper", "relation": "calls", "confidence": "INFERRED"}]
        store = _make_store(
            graphify=GraphifyEnrichment(enriched=True, version="0.9.16", skipped_reason=None, nodes=_NODES, edges=edges)
        )
        result = query_calls(store, "add")
        assert len(result.calls) == 1
        assert result.calls[0]["node"] is None
        assert result.calls[0]["edge"]["target"] == "src_unresolved_helper"
