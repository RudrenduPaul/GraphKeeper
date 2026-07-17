#!/usr/bin/env python3
"""
03 -- graceful degradation without graphify.

GraphKeeper's call-graph queries (query_calls()) only work when a build
included graphify (https://github.com/Graphify-Labs/graphify) enrichment.
This example shows the documented graceful-degradation path: querying
calls without graphify installed returns a structured, explanatory result
-- never a crash, never a silently empty answer. It also calls
detect_graphify() directly, so you can see exactly what GraphKeeper checks
for before attempting enrichment.

Run:
    python3 examples/03-graceful-degradation/calls_without_graphify.py
"""
from pathlib import Path

from graphkeeper import BuildOptions, build, detect_graphify, query_calls

REPO_ROOT = Path(__file__).resolve().parents[3]


def main() -> None:
    detected = detect_graphify()
    print(f"graphify on PATH: {detected['installed']} (version: {detected['version']})")
    print()

    # skip_graphify=True forces the same "not enriched" state this example
    # is demonstrating, regardless of whether graphify happens to be
    # installed on the machine running this script.
    result = build(str(REPO_ROOT), BuildOptions(skip_graphify=True))

    calls_result = query_calls(result.store, "mineCoChange")
    print(f"query_calls('mineCoChange') available: {calls_result.available}")
    print(f"reason: {calls_result.unavailable_reason}")


if __name__ == "__main__":
    main()
