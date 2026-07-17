"""
GraphKeeper library API.

    from graphkeeper import build, query_co_change

    result = build(".")
    print(f"{result.store.commits_analyzed} commit(s) analyzed")

    co_change = query_co_change(result.store, "src/git.py")
    for row in co_change.results:
        print(row.count, row.file)

This is the Python port of the graphkeeper-cli npm package
(https://www.npmjs.com/package/graphkeeper-cli). Both distributions mine
`git log` for the same file-level co-change signal and, when graphify
(https://github.com/Graphify-Labs/graphify) is installed, enrich the same
store with its symbol/call-graph output; see
https://github.com/RudrenduPaul/GraphKeeper for the canonical
documentation and the original TypeScript source. `graphkeeper.cli` is a
thin argument-parsing wrapper over the same functions exported here, so
anything scriptable from the command line is also usable directly from
Python.
"""
from .build import build
from .git import GitError, mine_co_change, unquote_git_path
from .graphify import detect_graphify, run_graphify_enrichment
from .query import find_graphify_node, normalize_file_arg, query_calls, query_co_change
from .store import PathSafetyError, graph_file_path, read_store, resolve_repo_root, write_store
from .types import (
    BuildOptions,
    BuildResult,
    CallsQueryResult,
    CoChangeEdge,
    CoChangeQueryResult,
    CoChangeResultRow,
    GraphifyEnrichment,
    GraphifyEdge,
    GraphifyNode,
    GraphKeeperStore,
)

__version__ = "0.1.0"

__all__ = [
    "build",
    "query_co_change",
    "query_calls",
    "find_graphify_node",
    "normalize_file_arg",
    "detect_graphify",
    "run_graphify_enrichment",
    "mine_co_change",
    "unquote_git_path",
    "GitError",
    "resolve_repo_root",
    "read_store",
    "write_store",
    "graph_file_path",
    "PathSafetyError",
    "GraphKeeperStore",
    "CoChangeEdge",
    "GraphifyNode",
    "GraphifyEdge",
    "GraphifyEnrichment",
    "BuildOptions",
    "BuildResult",
    "CoChangeQueryResult",
    "CoChangeResultRow",
    "CallsQueryResult",
    "__version__",
]
