"""
Path-safety-checked local storage for the GraphKeeper store.

Ported from src/store.ts. Every write and every directory GraphKeeper
creates is verified, after resolving symlinks, to be nested inside the
target repo's own `.graphkeeper/` directory -- so a maliciously crafted
repo (e.g. `.graphkeeper` itself replaced with a symlink to `/etc`, or a
target path containing `..`) can never redirect GraphKeeper's writes
somewhere unexpected.
"""
from __future__ import annotations

import json
import os
from typing import Optional

from .types import GraphKeeperStore

GRAPHKEEPER_DIR_NAME = ".graphkeeper"
GRAPH_FILE_NAME = "graph.json"
GRAPHIFY_RAW_DIR_NAME = "graphify-raw"


class PathSafetyError(Exception):
    pass


def resolve_repo_root(target_path: str) -> str:
    """Resolves `target_path` to a real, existing directory. Follows
    symlinks (`os.path.realpath`) so a malicious repo cannot point
    GraphKeeper's notion of "repo root" somewhere unexpected via a crafted
    symlink at the entry point."""
    resolved = os.path.abspath(target_path)
    if not os.path.exists(resolved):
        raise PathSafetyError(f'Path "{target_path}" does not exist.')
    real = os.path.realpath(resolved)
    if not os.path.isdir(real):
        raise PathSafetyError(f'Path "{target_path}" is not a directory.')
    return real


def assert_path_inside(child_path: str, parent_path: str) -> None:
    """Confirms that `child_path`, once symlinks are resolved, is the same
    as or nested inside `parent_path`. This is the core guard against a
    crafted repo causing GraphKeeper to read or write outside the intended
    output directory."""
    real_parent = os.path.realpath(parent_path)

    # child_path may not exist yet (e.g. before mkdir); resolve its nearest
    # existing ancestor and re-attach the remaining, not-yet-created
    # segments, mirroring src/store.ts's own walk-up loop.
    to_resolve = os.path.abspath(child_path)
    remainder = []
    while not os.path.exists(to_resolve):
        remainder.insert(0, os.path.basename(to_resolve))
        parent_of_to_resolve = os.path.dirname(to_resolve)
        if parent_of_to_resolve == to_resolve:
            # Reached filesystem root without finding an existing ancestor.
            break
        to_resolve = parent_of_to_resolve

    real_existing_ancestor = os.path.realpath(to_resolve) if os.path.exists(to_resolve) else to_resolve
    real_child = os.path.join(real_existing_ancestor, *remainder) if remainder else real_existing_ancestor

    is_inside = real_child == real_parent or real_child.startswith(real_parent + os.sep)
    if not is_inside:
        raise PathSafetyError(
            f"Refusing to write outside the target repo's {GRAPHKEEPER_DIR_NAME}/ directory "
            f'(resolved "{child_path}" -> "{real_child}", expected it under "{real_parent}").'
        )


def ensure_graphkeeper_subdir(repo_root: str, *subdir_segments: str) -> str:
    """Creates (or reuses) `.graphkeeper/<subdir...>` under `repo_root`,
    verifying containment at every step."""
    gk_dir = os.path.join(repo_root, GRAPHKEEPER_DIR_NAME)
    os.makedirs(gk_dir, exist_ok=True)
    assert_path_inside(gk_dir, repo_root)

    directory = gk_dir
    for segment in subdir_segments:
        directory = os.path.join(directory, segment)
    os.makedirs(directory, exist_ok=True)
    assert_path_inside(directory, repo_root)
    return directory


def graph_file_path(repo_root: str) -> str:
    """Path to the merged GraphKeeper store file, `.graphkeeper/graph.json`,
    under `repo_root`."""
    return os.path.join(repo_root, GRAPHKEEPER_DIR_NAME, GRAPH_FILE_NAME)


def write_store(repo_root: str, store: GraphKeeperStore) -> str:
    """Writes the store atomically (write to temp file, then rename) inside
    `.graphkeeper/`."""
    gk_dir = ensure_graphkeeper_subdir(repo_root)
    final_path = os.path.join(gk_dir, GRAPH_FILE_NAME)
    tmp_path = f"{final_path}.tmp-{os.getpid()}"
    assert_path_inside(tmp_path, repo_root)
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(store.to_dict(), fh, indent=2)
    os.replace(tmp_path, final_path)
    return final_path


def read_store(repo_root: str, override_path: Optional[str] = None) -> GraphKeeperStore:
    """Reads and parses `.graphkeeper/graph.json`, or a caller-supplied path
    override."""
    target = os.path.abspath(override_path) if override_path else graph_file_path(repo_root)
    if not os.path.exists(target):
        raise PathSafetyError(f'No graph found at "{target}". Run "graphkeeper build" first.')
    with open(target, "r", encoding="utf-8") as fh:
        raw = fh.read()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as err:
        raise PathSafetyError(f'"{target}" does not contain a valid GraphKeeper store.') from err
    if not isinstance(parsed, dict):
        raise PathSafetyError(f'"{target}" does not contain a valid GraphKeeper store.')
    return GraphKeeperStore.from_dict(parsed)
