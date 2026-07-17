"""Ported from test/cli-lib.test.ts."""
from __future__ import annotations

import json

import pytest

from graphkeeper.formatters import (
    format_build_json,
    format_build_text,
    format_calls_json,
    format_calls_text,
    format_co_change_json,
    format_co_change_text,
    parse_positive_int,
)
from graphkeeper.types import (
    BuildResult,
    CallsQueryResult,
    CoChangeEdge,
    CoChangeQueryResult,
    CoChangeResultRow,
    GraphifyEnrichment,
    GraphKeeperStore,
)


class TestParsePositiveInt:
    def test_parses_valid_positive_integer(self):
        assert parse_positive_int("42", "--limit") == 42

    def test_raises_for_zero(self):
        with pytest.raises(ValueError, match="Invalid --limit"):
            parse_positive_int("0", "--limit")

    def test_raises_for_negative(self):
        with pytest.raises(ValueError, match="Invalid --limit"):
            parse_positive_int("-5", "--limit")

    def test_raises_for_non_numeric(self):
        with pytest.raises(ValueError, match="Invalid --limit"):
            parse_positive_int("abc", "--limit")


def _make_store(graphify=None) -> GraphKeeperStore:
    return GraphKeeperStore(
        version=1,
        generated_at="2026-01-01T00:00:00.000Z",
        repo_path="/repo",
        commits_analyzed=10,
        commits_skipped=0,
        co_change=[CoChangeEdge(a="a.py", b="b.py", count=3)],
        file_commit_counts={"a.py": 3},
        graphify=graphify
        or GraphifyEnrichment(enriched=False, version=None, skipped_reason="graphify not installed"),
    )


class TestFormatBuild:
    def test_mentions_co_change_stats_and_skip_reason(self):
        result = BuildResult(store=_make_store(), output_path="/repo/.graphkeeper/graph.json")
        text = format_build_text(result)
        assert "10 commit" in text
        assert "graphify enrichment: skipped" in text
        assert "graphify not installed" in text

    def test_reports_enriched_node_edge_counts(self):
        result = BuildResult(
            store=_make_store(
                graphify=GraphifyEnrichment(
                    enriched=True,
                    version="0.9.16",
                    skipped_reason=None,
                    nodes=[{"id": "n1", "label": "a.py"}],
                    edges=[],
                )
            ),
            output_path="/repo/.graphkeeper/graph.json",
        )
        text = format_build_text(result)
        assert "graphify enrichment: included (v0.9.16)" in text
        assert "1 node" in text

    def test_emits_valid_parseable_json(self):
        result = BuildResult(store=_make_store(), output_path="/repo/.graphkeeper/graph.json")
        parsed = json.loads(format_build_json(result))
        assert parsed["commitsAnalyzed"] == 10
        assert parsed["graphify"]["enriched"] is False


class TestFormatCoChange:
    def test_lists_ranked_results(self):
        result = CoChangeQueryResult(file="a.py", results=[CoChangeResultRow(file="b.py", count=4)])
        assert "b.py" in format_co_change_text(result)

    def test_explains_empty_result_clearly(self):
        result = CoChangeQueryResult(file="a.py", results=[])
        assert "no co-change data found" in format_co_change_text(result)

    def test_emits_valid_json(self):
        result = CoChangeQueryResult(file="a.py", results=[CoChangeResultRow(file="b.py", count=4)])
        parsed = json.loads(format_co_change_json(result))
        assert parsed == {"file": "a.py", "results": [{"file": "b.py", "count": 4}]}


class TestFormatCalls:
    def test_explains_unavailability(self):
        result = CallsQueryResult(
            symbol="add",
            available=False,
            unavailable_reason="graphify enrichment is required for this query type.",
            node=None,
            calls=[],
            called_by=[],
        )
        text = format_calls_text(result)
        assert "not available" in text
        assert "graphify enrichment is required" in text

    def test_reports_no_match_found(self):
        result = CallsQueryResult(
            symbol="ghost", available=True, unavailable_reason=None, node=None, calls=[], called_by=[]
        )
        assert 'No symbol matching "ghost"' in format_calls_text(result)

    def test_lists_callers_and_callees_when_found(self):
        result = CallsQueryResult(
            symbol="add",
            available=True,
            unavailable_reason=None,
            node={"id": "src_a_add", "label": "add()", "source_file": "src/a.py"},
            calls=[
                {
                    "node": {"id": "src_a_helper", "label": "helper()"},
                    "edge": {"source": "src_a_add", "target": "src_a_helper", "relation": "calls"},
                }
            ],
            called_by=[
                {
                    "node": {"id": "src_b_sum3", "label": "sum3()"},
                    "edge": {"source": "src_b_sum3", "target": "src_a_add", "relation": "calls"},
                }
            ],
        )
        text = format_calls_text(result)
        assert "add()" in text
        assert "--> helper()" in text
        assert "<-- sum3()" in text

    def test_falls_back_to_raw_edge_target_source_when_node_unresolved(self):
        result = CallsQueryResult(
            symbol="add",
            available=True,
            unavailable_reason=None,
            node={"id": "src_a_add", "label": "add()"},
            calls=[{"node": None, "edge": {"source": "src_a_add", "target": "src_unresolved", "relation": "calls"}}],
            called_by=[],
        )
        assert "--> src_unresolved" in format_calls_text(result)

    def test_emits_valid_json(self):
        result = CallsQueryResult(
            symbol="add", available=True, unavailable_reason=None, node=None, calls=[], called_by=[]
        )
        parsed = json.loads(format_calls_json(result))
        assert parsed["symbol"] == "add"
        assert parsed["available"] is True
