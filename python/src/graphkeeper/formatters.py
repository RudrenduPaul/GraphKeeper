"""
Human-readable and JSON output formatters, plus small CLI argument-parsing
helpers.

Ported from src/cli-lib.ts.
"""
from __future__ import annotations

import json

from .types import BuildResult, CallsQueryResult, CoChangeQueryResult


def parse_positive_int(raw: str, flag_name: str) -> int:
    stripped = raw.strip()
    try:
        n = int(stripped)
    except ValueError:
        n = None
    if n is None or n <= 0 or str(n) != stripped:
        raise ValueError(f'Invalid {flag_name} value "{raw}". Expected a positive integer.')
    return n


def format_build_text(result: BuildResult) -> str:
    store = result.store
    lines = [f"GraphKeeper build complete: {store.repo_path}", ""]
    skipped_note = (
        f" ({store.commits_skipped} commit(s) skipped: too many files changed)"
        if store.commits_skipped > 0
        else ""
    )
    lines.append(
        f"Co-change graph: {store.commits_analyzed} commit(s) analyzed, "
        f"{len(store.co_change)} file pair(s) found{skipped_note}"
    )
    if store.graphify.enriched:
        version = store.graphify.version or "unknown"
        lines.append(
            f"graphify enrichment: included (v{version}) -- "
            f"{len(store.graphify.nodes)} node(s), {len(store.graphify.edges)} edge(s)"
        )
    else:
        lines.append(f"graphify enrichment: skipped -- {store.graphify.skipped_reason or 'unknown reason'}")
    lines.append("")
    lines.append(f"Wrote {result.output_path}")
    return "\n".join(lines)


def format_build_json(result: BuildResult) -> str:
    store = result.store
    payload = {
        "repoPath": store.repo_path,
        "outputPath": result.output_path,
        "generatedAt": store.generated_at,
        "commitsAnalyzed": store.commits_analyzed,
        "commitsSkipped": store.commits_skipped,
        "coChangePairs": len(store.co_change),
        "graphify": {
            "enriched": store.graphify.enriched,
            "version": store.graphify.version,
            "skippedReason": store.graphify.skipped_reason,
            "nodes": len(store.graphify.nodes),
            "edges": len(store.graphify.edges),
        },
    }
    return json.dumps(payload, indent=2)


def format_co_change_text(result: CoChangeQueryResult) -> str:
    lines = [f'Files that historically change alongside "{result.file}":', ""]
    if not result.results:
        lines.append("  (no co-change data found for this file -- check the path, or run `graphkeeper build` first)")
    else:
        for r in result.results:
            lines.append(f"  {str(r.count).rjust(4)}  {r.file}")
    return "\n".join(lines)


def format_co_change_json(result: CoChangeQueryResult) -> str:
    payload = {"file": result.file, "results": [{"file": r.file, "count": r.count} for r in result.results]}
    return json.dumps(payload, indent=2)


def format_calls_text(result: CallsQueryResult) -> str:
    if not result.available:
        return "\n".join(
            [
                f'Call-graph query for "{result.symbol}" is not available.',
                "",
                result.unavailable_reason or "graphify enrichment is required for this query type.",
            ]
        )
    if not result.node:
        return f'No symbol matching "{result.symbol}" was found in the graphify graph.'

    label = result.node.get("label", result.symbol)
    source_file = result.node.get("source_file") or "unknown location"
    lines = [f"{label} ({source_file})", ""]
    lines.append(f"Calls ({len(result.calls)}):")
    for c in result.calls:
        node = c.get("node")
        edge = c.get("edge") or {}
        target = node.get("label") if node else edge.get("target")
        lines.append(f"  --> {target}")
    lines.append("")
    lines.append(f"Called by ({len(result.called_by)}):")
    for c in result.called_by:
        node = c.get("node")
        edge = c.get("edge") or {}
        source = node.get("label") if node else edge.get("source")
        lines.append(f"  <-- {source}")
    return "\n".join(lines)


def format_calls_json(result: CallsQueryResult) -> str:
    payload = {
        "symbol": result.symbol,
        "available": result.available,
        "unavailableReason": result.unavailable_reason,
        "node": result.node,
        "calls": result.calls,
        "calledBy": result.called_by,
    }
    return json.dumps(payload, indent=2)
