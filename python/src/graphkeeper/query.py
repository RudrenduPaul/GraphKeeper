"""
Query logic against a built GraphKeeper store: co-change lookups and
graphify-backed call-graph lookups.

Ported from src/query.ts.
"""
from __future__ import annotations

import os
import re
from typing import List, Optional

from .types import CallsQueryResult, CoChangeQueryResult, CoChangeResultRow, GraphKeeperStore, GraphifyNode


def _is_absolute(path_str: str) -> bool:
    """Cross-platform absolute-path check matching the semantics of Node's
    `path.isAbsolute`, which the TypeScript original (src/query.ts) relies
    on.

    On Windows, `os.path.isabs` disagrees with Node here for *root-relative*
    paths that have no drive letter (e.g. "/repo/src/a.py" or
    "\\repo\\src\\a.py"): Node's `path.isAbsolute` treats a leading path
    separator as absolute (resolved against the current drive), but
    `os.path.isabs` returns False for it, silently skipping relativization
    for exactly the POSIX-style absolute paths an MCP client is likely to
    pass. On POSIX this matches `os.path.isabs` exactly (leading "/").
    """
    if not path_str:
        return False
    if os.name == "nt":
        first = path_str[0]
        if first in ("\\", "/"):
            return True
        if len(path_str) > 2 and path_str[1] == ":" and path_str[2] in ("\\", "/"):
            return True
        return False
    return path_str.startswith("/")


def normalize_file_arg(store: GraphKeeperStore, file: str) -> str:
    """Normalizes a user-supplied file argument to the repo-relative form
    GraphKeeper stores paths in."""
    normalized = file
    if _is_absolute(normalized):
        try:
            rel = os.path.relpath(normalized, store.repo_path)
        except ValueError:
            # Windows-only: os.path.relpath raises when `normalized` and
            # `store.repo_path` are on different drives (e.g. repo on C:,
            # file arg on D:) -- there is no relative path between them.
            # The TypeScript original (path.relative) doesn't throw in this
            # case; it just returns the absolute target path unchanged,
            # which also fails the `not rel.startswith("..")` check below.
            # Mirror that by leaving `normalized` as-is instead of crashing.
            rel = None
        if rel is not None and not rel.startswith(".."):
            normalized = rel
    normalized = re.sub(r"^\./", "", normalized)
    return normalized.replace(os.sep, "/")


def query_co_change(store: GraphKeeperStore, file: str, limit: Optional[int] = None) -> CoChangeQueryResult:
    """Finds files that historically changed alongside `file`, ranked by
    co-change frequency (how many commits touched both)."""
    target = normalize_file_arg(store, file)
    results: List[CoChangeResultRow] = []
    for edge in store.co_change:
        if edge.a == target:
            results.append(CoChangeResultRow(file=edge.b, count=edge.count))
        elif edge.b == target:
            results.append(CoChangeResultRow(file=edge.a, count=edge.count))
    results.sort(key=lambda r: r.count, reverse=True)
    limited = results[:limit] if limit and limit > 0 else results
    return CoChangeQueryResult(file=target, results=limited)


def _normalize_symbol(s: str) -> str:
    return re.sub(r"\(\)\s*$", "", s.strip()).lower()


def find_graphify_node(nodes: List[GraphifyNode], symbol: str) -> Optional[GraphifyNode]:
    """Finds a graphify node whose label best matches `symbol` (exact match
    preferred, then case-insensitive)."""
    for n in nodes:
        if n.get("label") == symbol or n.get("label") == f"{symbol}()":
            return n
    target = _normalize_symbol(symbol)
    for n in nodes:
        if _normalize_symbol(str(n.get("label", ""))) == target:
            return n
    for n in nodes:
        node_id = n.get("id", "")
        if node_id == symbol or str(node_id).endswith(f"_{symbol}"):
            return n
    return None


def query_calls(store: GraphKeeperStore, symbol: str) -> CallsQueryResult:
    """Finds callers/callees of `symbol` using graphify's `calls` edges.
    Only meaningful when the build included graphify enrichment; otherwise
    reports why (never a silent empty result or a crash)."""
    if not store.graphify.enriched:
        return CallsQueryResult(
            symbol=symbol,
            available=False,
            unavailable_reason=(
                store.graphify.skipped_reason
                or "This build did not include graphify enrichment, so call-graph queries aren't "
                "available. Install graphify (`uv tool install graphifyy`) and re-run "
                "`graphkeeper build` to enable them."
            ),
            node=None,
            calls=[],
            called_by=[],
        )

    nodes_by_id = {n.get("id"): n for n in store.graphify.nodes}
    node = find_graphify_node(store.graphify.nodes, symbol)

    if not node:
        return CallsQueryResult(
            symbol=symbol,
            available=True,
            unavailable_reason=None,
            node=None,
            calls=[],
            called_by=[],
        )

    calls = [
        {"node": nodes_by_id.get(e.get("target")), "edge": e}
        for e in store.graphify.edges
        if e.get("relation") == "calls" and e.get("source") == node.get("id")
    ]
    called_by = [
        {"node": nodes_by_id.get(e.get("source")), "edge": e}
        for e in store.graphify.edges
        if e.get("relation") == "calls" and e.get("target") == node.get("id")
    ]

    return CallsQueryResult(
        symbol=symbol,
        available=True,
        unavailable_reason=None,
        node=node,
        calls=calls,
        called_by=called_by,
    )
