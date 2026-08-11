"""
MCP (Model Context Protocol) stdio server wrapping the graphkeeper CLI.

Generic MCP server template described in strategy-b2a-ideas/gtm/mcp-plugins.md
("Generic MCP Server Template"): one exposed tool that shells out to the
underlying CLI with --json appended, parses the JSON stdout, and returns it
as the tool result.

Deliberately shells out to the Node/TypeScript CLI (`npx graphkeeper`)
rather than calling into this same Python package's own native
`graphkeeper.cli` module. Per the template, the MCP wrapper's implementation
language is independent of the CLI's: this keeps one wrapper shape reusable
across the whole portfolio regardless of whether a given repo's CLI is Node
or Python, and it exercises the actual published `graphkeeper` npm binary
end to end rather than a parallel code path.

stdout is reserved for MCP's JSON-RPC framing, so anything this module
logs goes to stderr.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

from mcp.server import MCPServer

# Local-test override: point at a built dist/cli.js instead of `npx graphkeeper`.
# The npm package may not be globally linked on a dev machine, so testing
# this wrapper against a repo checkout needs a direct `node <path>` command.
# Production default (no env var set) is `npx graphkeeper`.
_LOCAL_CLI_JS = os.environ.get("GRAPHKEEPER_CLI_JS")


def _base_command() -> list[str]:
    if _LOCAL_CLI_JS:
        return ["node", _LOCAL_CLI_JS]
    return ["npx", "graphkeeper"]


_TOOL_DESCRIPTION = """Run the GraphKeeper CLI to mine a local git repo's commit history for file-level co-change patterns and query the resulting knowledge graph. Call this when an agent needs to know which files tend to change together in a codebase (e.g. before editing a file, to see what else usually needs to change alongside it) or which functions call/are called by a given symbol.

WHEN TO USE: call `build` once per repo (or after significant new commits) to (re)generate the graph, then call `query co-change` or `query calls` as often as needed against that graph. Do not call `build` on every query; the graph persists on disk at `.graphkeeper/graph.json` under the target repo and only needs rebuilding when history has moved on meaningfully. Requires `git` on PATH and a real git repository at the target path; `query calls` additionally requires the repo to have been built with graphify enrichment available (co-change queries work without it).

BEHAVIOR: `build` is read-only with respect to the target repo (it only reads `git log`) but WRITES a `.graphkeeper/graph.json` file to disk, overwriting any existing graph at that path -- this is the tool's only side effect, there is no network access. `query` subcommands are fully read-only, reading the existing graph.json without modifying it. All calls are synchronous and idempotent: rerunning `build` on the same commit range reproduces the same graph; rerunning a `query` is a no-op read. On CLI failure (bad path, missing graph, non-git directory) the tool returns a JSON object with an `error` key and, where available, `stderr`/`command` -- it never raises.

PARAMETERS: `args` is a list[str] of the CLI's own argv, i.e. everything after `graphkeeper` -- the subcommand plus its flags/positional args, exactly as you would type them on a command line. `--json` is appended automatically; never pass it yourself. Real examples for this CLI:
  - `["build", "."]` -- build/rebuild the graph for the repo at the given path (use "." for the current repo)
  - `["build", ".", "--no-graphify", "--max-files-per-commit", "50"]` -- build while skipping graphify symbol enrichment and ignoring commits touching more than 50 files
  - `["query", "co-change", "src/index.ts", "--limit", "10"]` -- list files that historically change alongside src/index.ts, most frequent first
  - `["query", "calls", "parseConfig"]` -- show callers/callees of a symbol (requires graphify enrichment from a prior `build`)
  - `["--help"]` or `["query", "--help"]` -- discover the full flag/subcommand set directly from the CLI rather than guessing

RETURN SHAPE: the parsed JSON stdout of the underlying command. `build` returns an object with keys like `repoPath`, `outputPath`, `commitsAnalyzed`, `commitsSkipped`, `coChangePairs`, and a `graphify` sub-object (`enriched`, `version`, `nodes`, `edges`). `query co-change` returns `{"file": <path>, "results": [{"file": <path>, "count": <int>}, ...]}` ranked by co-change frequency. `query calls` returns caller/callee edges for the requested symbol. On error, expect `{"error": <str>, "stderr"?: <str>, "command"?: [...]}` instead."""


mcp = MCPServer(name="graphkeeper")


@mcp.tool(description=_TOOL_DESCRIPTION)
def run(args: list[str]) -> dict[str, Any]:
    """Run the graphkeeper CLI with `args` (subcommand + its own arguments,
    e.g. ["build", "."] or ["query", "co-change", "src/index.ts"]) and
    return its parsed `--json` output. `--json` is appended automatically,
    callers should not pass it themselves."""
    command = [*_base_command(), *args, "--json"]
    print(f"graphkeeper-mcp: running {command!r}", file=sys.stderr)
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=120)
    except OSError as exc:
        return {"error": f"failed to exec {command!r}: {exc}"}
    if proc.stderr:
        print(f"graphkeeper-mcp: stderr: {proc.stderr}", file=sys.stderr)
    if proc.returncode != 0:
        return {
            "error": f"graphkeeper exited with code {proc.returncode}",
            "stderr": proc.stderr.strip(),
            "command": command,
        }
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return {
            "error": f"could not parse JSON output: {exc}",
            "stdout": proc.stdout,
            "command": command,
        }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
