#!/usr/bin/env python3
"""
02 -- agent-native JSON report.

Demonstrates the use case GraphKeeper is actually designed for: an agent
framework calling the library in-process (no CLI subprocess, no shelling
out) and consuming a structured co-change report it can reason over
programmatically -- e.g. "which other files should I look at before editing
this one?" Builds against this repo checkout, then emits a JSON report for
a handful of source files, capped with `limit`.

Run:
    python3 examples/02-agent-json/report.py
"""
import json
from pathlib import Path

from graphkeeper import BuildOptions, build, query_co_change

REPO_ROOT = Path(__file__).resolve().parents[3]
FILES_OF_INTEREST = ["src/git.ts", "src/store.ts", "src/cli.ts"]


def main() -> None:
    result = build(str(REPO_ROOT), BuildOptions(skip_graphify=True))
    store = result.store

    report = {
        "repo": store.repo_path,
        "commits_analyzed": store.commits_analyzed,
        "co_change_pairs": len(store.co_change),
        "queries": [],
    }

    for file in FILES_OF_INTEREST:
        co_change = query_co_change(store, file, limit=3)
        report["queries"].append(
            {
                "file": co_change.file,
                "top_co_change_partners": [{"file": r.file, "count": r.count} for r in co_change.results],
            }
        )

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
