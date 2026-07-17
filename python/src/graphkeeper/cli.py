#!/usr/bin/env python3
"""
Argument-parsing wrapper over graphkeeper's build/query library functions.
Console entry point: `graphkeeper <command> [options]`, installed via the
`graphkeeper` console-script defined in python/pyproject.toml.

Ported from src/cli.ts (which uses `commander`); this port uses the stdlib
`argparse` to avoid a CLI-framework dependency. Subcommands, flags,
defaults, and exit codes are kept identical to the npm CLI's `--help`
output and behavior: `build [path]`, `query co-change <file>`, and
`query calls <symbol>`.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, NoReturn, Optional

from .build import build
from .formatters import (
    format_build_json,
    format_build_text,
    format_calls_json,
    format_calls_text,
    format_co_change_json,
    format_co_change_text,
    parse_positive_int,
)
from .query import query_calls, query_co_change
from .store import read_store, resolve_repo_root
from .types import BuildOptions

VERSION = "0.1.0"


def _report_error(err: Exception, as_json: bool) -> NoReturn:
    message = str(err)
    if as_json:
        sys.stderr.write(json.dumps({"error": message}, indent=2) + "\n")
    else:
        sys.stderr.write(f"Error: {message}\n")
    sys.exit(2)


def build_parser() -> "tuple[argparse.ArgumentParser, argparse.ArgumentParser]":
    parser = argparse.ArgumentParser(
        prog="graphkeeper",
        description=(
            "Local-only CLI that mines git history for file-level co-change patterns and builds a "
            "queryable knowledge graph for AI coding agents, with optional enrichment from graphify's "
            "symbol/call-graph output when it is installed."
        ),
    )
    parser.add_argument("-V", "--version", action="version", version=VERSION)

    subparsers = parser.add_subparsers(dest="command")

    build_cmd = subparsers.add_parser(
        "build",
        description="Mine git history for co-change and (if available) merge in graphify's symbol/call graph",
    )
    build_cmd.add_argument("path", nargs="?", default=".", help="path to the target repo")
    build_cmd.add_argument("--json", action="store_true", help="emit machine-readable JSON instead of human-readable text")
    build_cmd.add_argument(
        "--max-files-per-commit",
        default=None,
        help="skip commits touching more than this many files (default: 100)",
    )
    build_cmd.add_argument(
        "--no-graphify",
        dest="graphify",
        action="store_false",
        default=True,
        help="skip graphify enrichment even if graphify is installed",
    )

    query_cmd = subparsers.add_parser("query", description="Query the GraphKeeper store built by `graphkeeper build`")
    query_subparsers = query_cmd.add_subparsers(dest="query_command")

    co_change_cmd = query_subparsers.add_parser(
        "co-change",
        description="List files that historically change alongside <file>, ranked by co-change frequency",
    )
    co_change_cmd.add_argument("file", help="repo-relative file path, e.g. src/git.py")
    co_change_cmd.add_argument("--json", action="store_true", help="emit machine-readable JSON instead of human-readable text")
    co_change_cmd.add_argument("--limit", default=None, help="cap the number of results")
    co_change_cmd.add_argument(
        "--graph", default=None, help="path to a specific graph.json (default: <cwd>/.graphkeeper/graph.json)"
    )

    calls_cmd = query_subparsers.add_parser(
        "calls",
        description="Show callers/callees of <symbol> (requires graphify enrichment from `graphkeeper build`)",
    )
    calls_cmd.add_argument("symbol", help="symbol name, e.g. parse_config")
    calls_cmd.add_argument("--json", action="store_true", help="emit machine-readable JSON instead of human-readable text")
    calls_cmd.add_argument(
        "--graph", default=None, help="path to a specific graph.json (default: <cwd>/.graphkeeper/graph.json)"
    )

    return parser, query_cmd


def _run_build(args: argparse.Namespace) -> int:
    try:
        max_files_per_commit = (
            parse_positive_int(args.max_files_per_commit, "--max-files-per-commit")
            if args.max_files_per_commit
            else None
        )
        result = build(
            args.path,
            BuildOptions(max_files_per_commit=max_files_per_commit, skip_graphify=not args.graphify),
        )
        print(format_build_json(result) if args.json else format_build_text(result))
        return 0
    except Exception as err:  # noqa: BLE001 -- mirrors src/cli.ts's catch-all reportError()
        _report_error(err, bool(args.json))


def _run_query_co_change(args: argparse.Namespace) -> int:
    try:
        limit = parse_positive_int(args.limit, "--limit") if args.limit else None
        repo_root = resolve_repo_root(".")
        store = read_store(repo_root, args.graph)
        result = query_co_change(store, args.file, limit)
        print(format_co_change_json(result) if args.json else format_co_change_text(result))
        return 0 if result.results else 1
    except Exception as err:  # noqa: BLE001
        _report_error(err, bool(args.json))


def _run_query_calls(args: argparse.Namespace) -> int:
    try:
        repo_root = resolve_repo_root(".")
        store = read_store(repo_root, args.graph)
        result = query_calls(store, args.symbol)
        print(format_calls_json(result) if args.json else format_calls_text(result))
        return 0 if (result.available and result.node) else 1
    except Exception as err:  # noqa: BLE001
        _report_error(err, bool(args.json))


def run_cli(argv: Optional[List[str]] = None) -> int:
    parser, query_cmd = build_parser()
    args = parser.parse_args(argv)

    if args.command == "build":
        return _run_build(args)
    if args.command == "query":
        if args.query_command == "co-change":
            return _run_query_co_change(args)
        if args.query_command == "calls":
            return _run_query_calls(args)
        query_cmd.print_help()
        return 0
    parser.print_help()
    return 0


def main() -> None:
    sys.exit(run_cli(sys.argv[1:]))


if __name__ == "__main__":
    main()
