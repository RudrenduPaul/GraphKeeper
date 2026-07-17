"""Ported from test/graphify.test.ts. Mocks subprocess.run the same way the
TypeScript suite mocks node:child_process's spawnSync."""
from __future__ import annotations

import json
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from graphkeeper.graphify import detect_graphify, run_graphify_enrichment

from .conftest import cleanup, make_temp_git_repo


def _completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


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


class TestDetectGraphify:
    def test_reports_installed_with_parsed_version(self):
        with patch("graphkeeper.graphify.subprocess.run", return_value=_completed(0, "graphify 0.9.16\n")):
            result = detect_graphify()
        assert result == {"installed": True, "version": "0.9.16"}

    def test_reports_not_installed_when_binary_missing(self):
        with patch("graphkeeper.graphify.subprocess.run", side_effect=FileNotFoundError()):
            result = detect_graphify()
        assert result == {"installed": False, "version": None}

    def test_reports_not_installed_when_command_exits_nonzero(self):
        with patch("graphkeeper.graphify.subprocess.run", return_value=_completed(1, "", "boom")):
            result = detect_graphify()
        assert result["installed"] is False


class TestRunGraphifyEnrichment:
    def test_skips_gracefully_when_not_installed(self, temp_repo):
        repo = temp_repo()
        with patch("graphkeeper.graphify.subprocess.run", side_effect=FileNotFoundError()):
            result = run_graphify_enrichment(repo)
        assert result.enriched is False
        assert "not found on PATH" in result.skipped_reason
        assert result.nodes == []

    def test_skips_gracefully_when_extract_exits_nonzero(self, temp_repo):
        repo = temp_repo()

        def side_effect(cmd, **kwargs):
            if cmd[1] == "--version":
                return _completed(0, "graphify 0.9.16\n")
            return _completed(1, "", "error: path not found\n")

        with patch("graphkeeper.graphify.subprocess.run", side_effect=side_effect):
            result = run_graphify_enrichment(repo)
        assert result.enriched is False
        assert "exited with status 1" in result.skipped_reason

    def test_merges_nodes_edges_when_extraction_succeeds(self, temp_repo):
        repo = temp_repo()

        def side_effect(cmd, **kwargs):
            if cmd[1] == "--version":
                return _completed(0, "graphify 0.9.16\n")
            out_idx = cmd.index("--out")
            raw_dir = cmd[out_idx + 1]
            graph_out_dir = os.path.join(raw_dir, "graphify-out")
            os.makedirs(graph_out_dir, exist_ok=True)
            with open(os.path.join(graph_out_dir, "graph.json"), "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "nodes": [{"id": "src_a", "label": "a.py", "file_type": "code"}],
                        "edges": [{"source": "src_a", "target": "src_a", "relation": "contains", "confidence": "EXTRACTED"}],
                    },
                    fh,
                )
            return _completed(0, "wrote graph.json")

        with patch("graphkeeper.graphify.subprocess.run", side_effect=side_effect):
            result = run_graphify_enrichment(repo)
        assert result.enriched is True
        assert result.version == "0.9.16"
        assert len(result.nodes) == 1
        assert len(result.edges) == 1

    def test_rewrites_source_file_relative_to_repo_root(self, temp_repo):
        repo = temp_repo()

        def side_effect(cmd, **kwargs):
            if cmd[1] == "--version":
                return _completed(0, "graphify 0.9.16\n")
            out_idx = cmd.index("--out")
            raw_dir = cmd[out_idx + 1]
            graph_out_dir = os.path.join(raw_dir, "graphify-out")
            os.makedirs(graph_out_dir, exist_ok=True)
            # graphify reports source_file relative to its own --out dir,
            # which here is nested two levels inside the repo
            # (.graphkeeper/graphify-raw).
            with open(os.path.join(graph_out_dir, "graph.json"), "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "nodes": [{"id": "src_a", "label": "a.py", "source_file": "../../src/a.py"}],
                        "edges": [
                            {"source": "src_a", "target": "src_a", "relation": "contains", "source_file": "../../src/a.py"}
                        ],
                    },
                    fh,
                )
            return _completed(0, "")

        with patch("graphkeeper.graphify.subprocess.run", side_effect=side_effect):
            result = run_graphify_enrichment(repo)
        assert result.nodes[0]["source_file"] == "src/a.py"
        assert result.edges[0]["source_file"] == "src/a.py"

    def test_skips_gracefully_when_graph_json_malformed(self, temp_repo):
        repo = temp_repo()

        def side_effect(cmd, **kwargs):
            if cmd[1] == "--version":
                return _completed(0, "graphify 0.9.16\n")
            out_idx = cmd.index("--out")
            raw_dir = cmd[out_idx + 1]
            graph_out_dir = os.path.join(raw_dir, "graphify-out")
            os.makedirs(graph_out_dir, exist_ok=True)
            with open(os.path.join(graph_out_dir, "graph.json"), "w", encoding="utf-8") as fh:
                fh.write("{ not valid json")
            return _completed(0, "")

        with patch("graphkeeper.graphify.subprocess.run", side_effect=side_effect):
            result = run_graphify_enrichment(repo)
        assert result.enriched is False
        assert "Could not parse" in result.skipped_reason

    def test_skips_gracefully_when_spawning_extract_itself_errors(self, temp_repo):
        repo = temp_repo()

        def side_effect(cmd, **kwargs):
            if cmd[1] == "--version":
                return _completed(0, "graphify 0.9.16\n")
            raise FileNotFoundError("spawn graphify ENOENT")

        with patch("graphkeeper.graphify.subprocess.run", side_effect=side_effect):
            result = run_graphify_enrichment(repo)
        assert result.enriched is False
        assert "graphify extract failed to run" in result.skipped_reason

    def test_skips_gracefully_when_extract_succeeds_but_writes_no_graph_json(self, temp_repo):
        repo = temp_repo()

        def side_effect(cmd, **kwargs):
            if cmd[1] == "--version":
                return _completed(0, "graphify 0.9.16\n")
            # Reports success but (unrealistically) writes nothing.
            return _completed(0, "")

        with patch("graphkeeper.graphify.subprocess.run", side_effect=side_effect):
            result = run_graphify_enrichment(repo)
        assert result.enriched is False
        assert "did not produce a graph.json" in result.skipped_reason

    def test_skips_gracefully_when_graph_json_has_unexpected_shape(self, temp_repo):
        repo = temp_repo()

        def side_effect(cmd, **kwargs):
            if cmd[1] == "--version":
                return _completed(0, "graphify 0.9.16\n")
            out_idx = cmd.index("--out")
            raw_dir = cmd[out_idx + 1]
            graph_out_dir = os.path.join(raw_dir, "graphify-out")
            os.makedirs(graph_out_dir, exist_ok=True)
            with open(os.path.join(graph_out_dir, "graph.json"), "w", encoding="utf-8") as fh:
                json.dump({"nodes": "not-an-array"}, fh)
            return _completed(0, "")

        with patch("graphkeeper.graphify.subprocess.run", side_effect=side_effect):
            result = run_graphify_enrichment(repo)
        assert result.enriched is False
        assert "did not have the expected" in result.skipped_reason

    def test_skips_gracefully_when_graphkeeper_dir_is_preexisting_escaping_symlink(self, temp_repo):
        repo = temp_repo()
        outside = temp_repo()
        os.symlink(outside, os.path.join(repo, ".graphkeeper"))

        with patch("graphkeeper.graphify.subprocess.run", return_value=_completed(0, "graphify 0.9.16\n")):
            result = run_graphify_enrichment(repo)
        assert result.enriched is False
        assert "Could not prepare a safe output directory" in result.skipped_reason
