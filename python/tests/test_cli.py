"""Ported from test/cli.test.ts. Runs the real `python -m graphkeeper.cli`
entry point as a subprocess, same end-to-end style as the TypeScript suite
running `node dist/cli.js`."""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from .conftest import cleanup, commit_all, make_temp_git_repo, write_file


def run_cli_process(args, cwd=None):
    result = subprocess.run(
        [sys.executable, "-m", "graphkeeper.cli", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )
    return result.stdout, result.stderr, result.returncode


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


def test_help_lists_build_and_query_subcommands():
    stdout, _stderr, status = run_cli_process(["--help"])
    assert status == 0
    assert "build" in stdout
    assert "query" in stdout
    assert "graphkeeper" in stdout


def test_prints_version():
    stdout, _stderr, status = run_cli_process(["--version"])
    assert status == 0
    assert stdout.strip() == "0.1.0"


def test_exits_2_on_nonexistent_path():
    stdout, stderr, status = run_cli_process(["build", "/definitely/not/a/real/path/xyz"])
    assert status == 2
    assert stdout == ""
    assert "does not exist" in stderr


def test_exits_2_when_target_not_a_git_repo(temp_repo):
    d = temp_repo()
    cleanup(d)
    os.makedirs(d, exist_ok=True)
    try:
        _stdout, stderr, status = run_cli_process(["build", d])
        assert status == 2
        assert "not a git repository" in stderr
    finally:
        cleanup(d)


def test_builds_repo_end_to_end_and_reports_co_change(temp_repo):
    repo = temp_repo()
    write_file(repo, "a.py", "1")
    write_file(repo, "b.py", "1")
    commit_all(repo, "add a and b")

    stdout, _stderr, status = run_cli_process(["build", repo, "--no-graphify", "--json"], cwd=repo)
    assert status == 0
    parsed = json.loads(stdout)
    assert parsed["commitsAnalyzed"] > 0
    assert parsed["graphify"]["enriched"] is False


def test_queries_co_change_after_build_and_exits_0_with_results(temp_repo):
    repo = temp_repo()
    write_file(repo, "a.py", "1")
    write_file(repo, "b.py", "1")
    commit_all(repo, "add a and b")
    run_cli_process(["build", repo, "--no-graphify"], cwd=repo)

    stdout, _stderr, status = run_cli_process(["query", "co-change", "a.py", "--json"], cwd=repo)
    assert status == 0
    parsed = json.loads(stdout)
    assert parsed["results"][0]["file"] == "b.py"


def test_queries_calls_without_enrichment_exits_1_with_clear_explanation(temp_repo):
    repo = temp_repo()
    write_file(repo, "a.py", "1")
    commit_all(repo, "add a")
    run_cli_process(["build", repo, "--no-graphify"], cwd=repo)

    stdout, _stderr, status = run_cli_process(["query", "calls", "someSymbol", "--json"], cwd=repo)
    assert status == 1
    parsed = json.loads(stdout)
    assert parsed["available"] is False
    assert parsed["unavailableReason"]


def test_exits_2_when_no_graph_exists_yet(temp_repo):
    repo = temp_repo()
    _stdout, stderr, status = run_cli_process(["query", "co-change", "a.py"], cwd=repo)
    assert status == 2
    assert 'Run "graphkeeper build" first' in stderr
