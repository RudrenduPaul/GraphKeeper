"""Regression tests guarding against the dependency-confusion bug where the
MCP wrapper shelled out to `npx graphkeeper` (no `-cli` suffix) instead of
the actually-published `npx graphkeeper-cli`. `graphkeeper` (bare name) is
an unrelated third-party npm package from a different publisher; running it
instead of this project's CLI would silently execute unaudited code.

These tests only exercise this module's own `_base_command()` logic, not
the MCP SDK itself, so they stub `mcp.server.MCPServer` when it isn't
importable rather than skipping outright -- this project's pyproject.toml
requires `mcp[cli]>=2.0.0`, and some local/shared environments may still
have an older `mcp` pinned for unrelated projects that predates that name,
which shouldn't stop this dependency-confusion regression test from running.
"""
from __future__ import annotations

import importlib

import pytest

pytest.importorskip("mcp", reason="optional `mcp` extra not installed")


def _ensure_mcpserver_importable() -> None:
    try:
        from mcp.server import MCPServer  # noqa: F401

        return
    except ImportError:
        pass

    import mcp.server as real_server_module

    class _StubMCPServer:
        """Minimal stand-in with just enough surface for mcp_server.py's
        module-level `mcp = MCPServer(name=...)` and `@mcp.tool(...)` to
        execute without error."""

        def __init__(self, name: str) -> None:
            self.name = name

        def tool(self, description: str = ""):
            def decorator(func):
                return func

            return decorator

    real_server_module.MCPServer = _StubMCPServer


_ensure_mcpserver_importable()


@pytest.fixture()
def mcp_server_module(monkeypatch):
    monkeypatch.delenv("GRAPHKEEPER_CLI_JS", raising=False)
    import graphkeeper.mcp_server as module

    return importlib.reload(module)


class TestBaseCommand:
    def test_default_command_uses_published_cli_package_name(self, mcp_server_module):
        # The published npm package is `graphkeeper-cli`, not `graphkeeper`.
        # `npx graphkeeper` (missing the `-cli` suffix) resolves to a
        # completely different, unrelated npm package -- this must never
        # be the default.
        assert mcp_server_module._base_command() == ["npx", "graphkeeper-cli"]

    def test_default_command_never_omits_cli_suffix(self, mcp_server_module):
        command = mcp_server_module._base_command()
        assert "graphkeeper" not in command, (
            "the bare `graphkeeper` npm package is an unrelated third-party "
            "package; the CLI must always be invoked as `graphkeeper-cli`"
        )

    def test_local_override_still_takes_precedence(self, mcp_server_module, monkeypatch, tmp_path):
        cli_js = tmp_path / "cli.js"
        monkeypatch.setenv("GRAPHKEEPER_CLI_JS", str(cli_js))
        module = importlib.reload(mcp_server_module)
        try:
            assert module._base_command() == ["node", str(cli_js)]
        finally:
            monkeypatch.delenv("GRAPHKEEPER_CLI_JS", raising=False)
            importlib.reload(module)
