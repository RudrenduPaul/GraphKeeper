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


def _capture_help() -> str:
    """Best-effort `--help` capture, used as the tool's dynamic description
    instead of a hardcoded string."""
    fallback = "Run the graphkeeper CLI (build/query co-change/query calls subcommands)."
    try:
        proc = subprocess.run(
            [*_base_command(), "--help"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return proc.stdout.strip() or fallback
    except Exception as exc:  # noqa: BLE001 - degrade to a generic description
        print(f"graphkeeper-mcp: could not capture --help: {exc}", file=sys.stderr)
        return fallback


mcp = MCPServer(name="graphkeeper")


@mcp.tool(description=_capture_help())
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
