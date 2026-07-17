"""
Shared types for GraphKeeper's local knowledge-graph store.

The store is a single JSON file, `.graphkeeper/graph.json`, containing:
 - co-change data mined from `git log` (GraphKeeper's own contribution)
 - optionally, symbol/call-graph data merged in from graphify, if graphify
   is installed and enrichment succeeded (see graphkeeper/graphify.py)

Ported from src/types.ts. Field names here are snake_case (Python
convention); `GraphKeeperStore.to_dict()` / `.from_dict()` translate to and
from the camelCase JSON schema the npm CLI also reads and writes, so a
`.graphkeeper/graph.json` built by either distribution can be read by the
other.

graphify node/edge shapes are kept as plain `Dict[str, Any]` rather than a
fixed dataclass, matching the TypeScript source's own `[key: string]:
unknown` index signature -- graphify's own `graph.json` output can carry
fields this project doesn't know about in advance, and round-tripping them
through a fixed schema would silently drop them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

GraphifyNode = Dict[str, Any]
GraphifyEdge = Dict[str, Any]


@dataclass
class CoChangeEdge:
    """One unordered pair of files that changed together in one or more commits."""

    a: str
    b: str
    count: int


@dataclass
class GraphifyEnrichment:
    """Result of attempting graphify enrichment during a build."""

    enriched: bool
    version: Optional[str]
    skipped_reason: Optional[str]
    nodes: List[GraphifyNode] = field(default_factory=list)
    edges: List[GraphifyEdge] = field(default_factory=list)


@dataclass
class GraphKeeperStore:
    """The full on-disk store written to `.graphkeeper/graph.json`."""

    version: int
    generated_at: str
    repo_path: str
    commits_analyzed: int
    commits_skipped: int
    co_change: List[CoChangeEdge]
    file_commit_counts: Dict[str, int]
    graphify: GraphifyEnrichment

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "generatedAt": self.generated_at,
            "repoPath": self.repo_path,
            "commitsAnalyzed": self.commits_analyzed,
            "commitsSkipped": self.commits_skipped,
            "coChange": [{"a": e.a, "b": e.b, "count": e.count} for e in self.co_change],
            "fileCommitCounts": self.file_commit_counts,
            "graphify": {
                "enriched": self.graphify.enriched,
                "version": self.graphify.version,
                "skippedReason": self.graphify.skipped_reason,
                "nodes": self.graphify.nodes,
                "edges": self.graphify.edges,
            },
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "GraphKeeperStore":
        graphify_raw = data.get("graphify") or {}
        graphify = GraphifyEnrichment(
            enriched=bool(graphify_raw.get("enriched", False)),
            version=graphify_raw.get("version"),
            skipped_reason=graphify_raw.get("skippedReason"),
            nodes=list(graphify_raw.get("nodes") or []),
            edges=list(graphify_raw.get("edges") or []),
        )
        co_change = [
            CoChangeEdge(a=e["a"], b=e["b"], count=e["count"]) for e in (data.get("coChange") or [])
        ]
        return GraphKeeperStore(
            version=data.get("version", 1),
            generated_at=data.get("generatedAt", ""),
            repo_path=data.get("repoPath", ""),
            commits_analyzed=data.get("commitsAnalyzed", 0),
            commits_skipped=data.get("commitsSkipped", 0),
            co_change=co_change,
            file_commit_counts=dict(data.get("fileCommitCounts") or {}),
            graphify=graphify,
        )


@dataclass
class BuildOptions:
    """Options for `build()`. Mirrors src/types.ts's `BuildOptions`."""

    max_files_per_commit: Optional[int] = None
    """Skip commits touching more than this many files (default: 100)."""

    skip_graphify: bool = False
    """Skip graphify enrichment even if graphify is installed."""

    graphify_timeout_ms: Optional[int] = None
    """Present for parity with the TypeScript `BuildOptions` type. Not
    currently wired to a real timeout override in either the TypeScript
    source or this port -- `graphify.py`'s enrichment timeout is a fixed
    constant, same as upstream. Kept here rather than silently dropped, so a
    future fix lands in one obvious place."""


@dataclass
class BuildResult:
    store: GraphKeeperStore
    output_path: str


@dataclass
class CoChangeResultRow:
    file: str
    count: int


@dataclass
class CoChangeQueryResult:
    file: str
    results: List[CoChangeResultRow]


@dataclass
class CallsQueryResult:
    symbol: str
    available: bool
    unavailable_reason: Optional[str]
    node: Optional[GraphifyNode]
    calls: List[Dict[str, Any]]
    called_by: List[Dict[str, Any]]
