"""
Builds (or rebuilds) the GraphKeeper store for a repo.

Ported from src/build.ts.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .git import mine_co_change
from .graphify import run_graphify_enrichment
from .store import resolve_repo_root, write_store
from .types import BuildOptions, BuildResult, GraphifyEnrichment, GraphKeeperStore


def build(target_path: str, options: Optional[BuildOptions] = None) -> BuildResult:
    """Builds (or rebuilds) the GraphKeeper store for a repo: mines `git
    log` for file-level co-change, optionally enriches it with graphify's
    symbol/call graph if graphify is installed, and writes the merged
    result to `.graphkeeper/graph.json`."""
    opts = options or BuildOptions()
    repo_root = resolve_repo_root(target_path)

    mined = mine_co_change(repo_root, opts.max_files_per_commit)

    if opts.skip_graphify:
        graphify = GraphifyEnrichment(
            enriched=False,
            version=None,
            skipped_reason="graphify enrichment skipped via --no-graphify.",
        )
    else:
        graphify = run_graphify_enrichment(repo_root)

    store = GraphKeeperStore(
        version=1,
        generated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        repo_path=repo_root,
        commits_analyzed=mined.commits_analyzed,
        commits_skipped=mined.commits_skipped,
        co_change=mined.co_change,
        file_commit_counts=mined.file_commit_counts,
        graphify=graphify,
    )

    output_path = write_store(repo_root, store)
    return BuildResult(store=store, output_path=output_path)
