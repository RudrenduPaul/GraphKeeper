#!/usr/bin/env python3
"""
01 -- index and query.

The simplest possible use of the graphkeeper library: call build() against
a real repo, then query_co_change() to see which files historically changed
alongside a given one. This indexes the GraphKeeper repo checkout itself
(both its TypeScript and Python source share one git history), so it runs
standalone with no setup beyond `pip install -e .` (or `pip install
graphkeeper-cli`) from the python/ directory.

Run:
    python3 examples/01-index-and-query/build_and_query.py
"""
from pathlib import Path

from graphkeeper import BuildOptions, build, query_co_change

REPO_ROOT = Path(__file__).resolve().parents[3]


def main() -> None:
    result = build(str(REPO_ROOT), BuildOptions(skip_graphify=True))
    store = result.store

    print(f"Indexed: {store.repo_path}")
    print(f"Commits analyzed: {store.commits_analyzed}")
    print(f"Co-change pairs found: {len(store.co_change)}")
    print(f"Wrote: {result.output_path}")
    print()

    target = "src/git.ts"
    co_change = query_co_change(store, target, limit=5)
    print(f'Files that historically change alongside "{co_change.file}":')
    if not co_change.results:
        print("  (no co-change data found -- this checkout may be too shallow)")
    for row in co_change.results:
        print(f"  {row.count:>4}  {row.file}")


if __name__ == "__main__":
    main()
