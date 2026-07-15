import * as fs from "node:fs";
import * as path from "node:path";
import type { GraphKeeperStore } from "./types.js";

export const GRAPHKEEPER_DIR_NAME = ".graphkeeper";
export const GRAPH_FILE_NAME = "graph.json";
export const GRAPHIFY_RAW_DIR_NAME = "graphify-raw";

export class PathSafetyError extends Error {}

/**
 * Resolves `targetPath` to a real, existing directory. Follows symlinks via
 * `fs.realpathSync` so a malicious repo cannot point GraphKeeper's notion of
 * "repo root" somewhere unexpected via a crafted symlink at the entry point.
 */
export function resolveRepoRoot(targetPath: string): string {
  const resolved = path.resolve(targetPath);
  let real: string;
  try {
    real = fs.realpathSync(resolved);
  } catch {
    throw new PathSafetyError(`Path "${targetPath}" does not exist.`);
  }
  const stat = fs.statSync(real);
  if (!stat.isDirectory()) {
    throw new PathSafetyError(`Path "${targetPath}" is not a directory.`);
  }
  return real;
}

/**
 * Confirms that `childPath`, once symlinks are resolved, is the same as or
 * nested inside `parentPath`. This is the core guard against a crafted repo
 * (e.g. a `.graphkeeper` entry that is actually a symlink to `/etc` or `..`)
 * causing GraphKeeper to read or write outside the intended output directory.
 */
export function assertPathInside(childPath: string, parentPath: string): void {
  const realParent = fs.realpathSync(parentPath);
  // childPath may not exist yet (e.g. before mkdir); resolve its nearest
  // existing ancestor and re-attach the remaining, not-yet-created segments.
  let toResolve = path.resolve(childPath);
  const remainder: string[] = [];
  while (!fs.existsSync(toResolve)) {
    remainder.unshift(path.basename(toResolve));
    const parentOfToResolve = path.dirname(toResolve);
    if (parentOfToResolve === toResolve) {
      // Reached filesystem root without finding an existing ancestor.
      break;
    }
    toResolve = parentOfToResolve;
  }
  const realExistingAncestor = fs.existsSync(toResolve) ? fs.realpathSync(toResolve) : toResolve;
  const realChild = remainder.length > 0 ? path.join(realExistingAncestor, ...remainder) : realExistingAncestor;

  const isInside = realChild === realParent || realChild.startsWith(realParent + path.sep);
  if (!isInside) {
    throw new PathSafetyError(
      `Refusing to write outside the target repo's ${GRAPHKEEPER_DIR_NAME}/ directory ` +
        `(resolved "${childPath}" -> "${realChild}", expected it under "${realParent}").`,
    );
  }
}

/** Creates (or reuses) `.graphkeeper/<subdir...>` under `repoRoot`, verifying containment at every step. */
export function ensureGraphKeeperSubdir(repoRoot: string, ...subdirSegments: string[]): string {
  const gkDir = path.join(repoRoot, GRAPHKEEPER_DIR_NAME);
  fs.mkdirSync(gkDir, { recursive: true });
  assertPathInside(gkDir, repoRoot);

  let dir = gkDir;
  for (const segment of subdirSegments) {
    dir = path.join(dir, segment);
  }
  fs.mkdirSync(dir, { recursive: true });
  assertPathInside(dir, repoRoot);
  return dir;
}

/** Path to the merged GraphKeeper store file, `.graphkeeper/graph.json`, under `repoRoot`. */
export function graphFilePath(repoRoot: string): string {
  return path.join(repoRoot, GRAPHKEEPER_DIR_NAME, GRAPH_FILE_NAME);
}

/** Writes the store atomically (write to temp file, then rename) inside `.graphkeeper/`. */
export function writeStore(repoRoot: string, store: GraphKeeperStore): string {
  const gkDir = ensureGraphKeeperSubdir(repoRoot);
  const finalPath = path.join(gkDir, GRAPH_FILE_NAME);
  const tmpPath = `${finalPath}.tmp-${process.pid}`;
  assertPathInside(tmpPath, repoRoot);
  fs.writeFileSync(tmpPath, JSON.stringify(store, null, 2), "utf-8");
  fs.renameSync(tmpPath, finalPath);
  return finalPath;
}

/** Reads and parses `.graphkeeper/graph.json`, or a caller-supplied path override. */
export function readStore(repoRoot: string, overridePath?: string): GraphKeeperStore {
  const target = overridePath ? path.resolve(overridePath) : graphFilePath(repoRoot);
  if (!fs.existsSync(target)) {
    throw new PathSafetyError(
      `No graph found at "${target}". Run "graphkeeper build" first.`,
    );
  }
  const raw = fs.readFileSync(target, "utf-8");
  const parsed: unknown = JSON.parse(raw);
  if (typeof parsed !== "object" || parsed === null) {
    throw new PathSafetyError(`"${target}" does not contain a valid GraphKeeper store.`);
  }
  return parsed as GraphKeeperStore;
}
