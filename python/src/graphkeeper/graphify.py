"""
Optional enrichment from graphify (https://github.com/Graphify-Labs/graphify,
PyPI package `graphifyy`)'s symbol/import/call-graph extraction.

Ported from src/graphify.ts. Every `graphify` invocation uses an argv list
passed directly to the OS (`subprocess.run`, `shell=False`), never a shell
string, for the same reason as `git.py`. Detection and extraction failures
never raise -- every failure mode is reported back via `skipped_reason` so
`build()` can proceed in co-change-only mode, matching the TypeScript
source's "never throws" contract.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import PurePosixPath

from .store import GRAPHIFY_RAW_DIR_NAME, PathSafetyError, assert_path_inside, ensure_graphkeeper_subdir
from .types import GraphifyEnrichment

DEFAULT_TIMEOUT_S = 5 * 60

_VERSION_RE = re.compile(r"graphify\s+([\w.-]+)", re.IGNORECASE)


def detect_graphify() -> dict:
    """Detects whether graphify is installed and on PATH, by running
    `graphify --version`. Returns `{"installed": bool, "version": str |
    None}`."""
    try:
        result = subprocess.run(
            ["graphify", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return {"installed": False, "version": None}

    if result.returncode != 0:
        return {"installed": False, "version": None}

    match = _VERSION_RE.search(result.stdout or "")
    if match:
        version = match.group(1)
    else:
        version = (result.stdout or "").strip() or "unknown"
    return {"installed": True, "version": version}


def run_graphify_enrichment(repo_root: str) -> GraphifyEnrichment:
    """Runs `graphify extract <repo_root> --code-only --no-cluster --out
    <dir>` (graphify's own headless, no-LLM, no-API-key CLI path for local
    AST-based symbol/import/call-graph extraction) and merges its
    `graph.json` output into a GraphifyEnrichment. Never raises: any failure
    is reported back via `skipped_reason` so `build()` can proceed in
    co-change-only mode.

    `--out` is pointed at a directory inside the caller-managed
    `.graphkeeper/` tree, so graphify's own output never lands outside it.
    """
    detected = detect_graphify()
    if not detected["installed"]:
        return GraphifyEnrichment(
            enriched=False,
            version=None,
            skipped_reason=(
                "graphify was not found on PATH. Install it with `uv tool install graphifyy` "
                "(or `pipx install graphifyy`) for symbol/call-graph enrichment; GraphKeeper "
                "works fine without it, in co-change-only mode."
            ),
        )

    try:
        raw_dir = ensure_graphkeeper_subdir(repo_root, GRAPHIFY_RAW_DIR_NAME)
    except PathSafetyError as err:
        return GraphifyEnrichment(
            enriched=False,
            version=detected["version"],
            skipped_reason=f"Could not prepare a safe output directory for graphify: {err}",
        )

    try:
        extract_result = subprocess.run(
            ["graphify", "extract", repo_root, "--code-only", "--no-cluster", "--out", raw_dir],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=DEFAULT_TIMEOUT_S,
            check=False,
        )
    except (FileNotFoundError, OSError) as err:
        return GraphifyEnrichment(
            enriched=False,
            version=detected["version"],
            skipped_reason=f"graphify extract failed to run: {err}",
        )
    except subprocess.TimeoutExpired as err:
        return GraphifyEnrichment(
            enriched=False,
            version=detected["version"],
            skipped_reason=f"graphify extract failed to run: {err}",
        )

    if extract_result.returncode != 0:
        stderr_tail = " ".join((extract_result.stderr or "").strip().split("\n")[-3:]).strip()
        suffix = f": {stderr_tail}" if stderr_tail else ""
        return GraphifyEnrichment(
            enriched=False,
            version=detected["version"],
            skipped_reason=f"graphify extract exited with status {extract_result.returncode}{suffix}",
        )

    graph_json_path = os.path.join(raw_dir, "graphify-out", "graph.json")
    try:
        assert_path_inside(graph_json_path, repo_root)
    except PathSafetyError as err:
        return GraphifyEnrichment(
            enriched=False,
            version=detected["version"],
            skipped_reason=f"graphify's output path failed a safety check: {err}",
        )

    if not os.path.exists(graph_json_path):
        return GraphifyEnrichment(
            enriched=False,
            version=detected["version"],
            skipped_reason=f'graphify extract completed but did not produce a graph.json at "{graph_json_path}".',
        )

    try:
        with open(graph_json_path, "r", encoding="utf-8") as fh:
            raw = fh.read()
        parsed = json.loads(raw)
    except (OSError, json.JSONDecodeError) as err:
        return GraphifyEnrichment(
            enriched=False,
            version=detected["version"],
            skipped_reason=f"Could not parse graphify's graph.json: {err}",
        )

    nodes = parsed.get("nodes") if isinstance(parsed, dict) else None
    edges = parsed.get("edges") if isinstance(parsed, dict) else None
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return GraphifyEnrichment(
            enriched=False,
            version=detected["version"],
            skipped_reason="graphify's graph.json did not have the expected {nodes, edges} shape.",
        )

    # graphify reports `source_file` relative to its own --out directory,
    # not the scanned target. Because that --out directory lives nested
    # inside .graphkeeper/ (so graphify's own output never escapes it, per
    # this project's path-safety guard), those paths come back as
    # "../../src/a.py" instead of "src/a.py". Rewrite them relative to
    # repo_root so they line up with the co-change paths GraphKeeper mines
    # from git log.
    def rewrite_source_file(item: dict) -> dict:
        source_file = item.get("source_file")
        if not source_file:
            return item
        absolute = os.path.normpath(os.path.join(raw_dir, source_file))
        rewritten = os.path.relpath(absolute, repo_root)
        rewritten = str(PurePosixPath(*rewritten.split(os.sep)))
        return {**item, "source_file": rewritten}

    return GraphifyEnrichment(
        enriched=True,
        version=detected["version"],
        skipped_reason=None,
        nodes=[rewrite_source_file(n) for n in nodes],
        edges=[rewrite_source_file(e) for e in edges],
    )
