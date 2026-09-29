import { spawnSync } from "node:child_process";
import { constants } from "node:fs";
import { access, copyFile, mkdtemp, readFile, realpath, rm, stat } from "node:fs/promises";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { dirname, isAbsolute, join, relative, sep } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const actionRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const discoveryLimit = 64 * 1024 * 1024;

function failure(what, why, how) {
  return new Error(`WHAT: ${what}\nWHY: ${why}\nHOW: ${how}`);
}

function unsupported(name) {
  return failure(
    `Unsupported tracked Markdown path ${JSON.stringify(name)}.`,
    "The locked linter cannot reliably discover this filename through its glob adapter.",
    "Rename paths containing CR/LF, backslashes, incompatible glob escapes, or '+(' in a directory name."
  );
}

async function discover() {
  const result = spawnSync("git", ["ls-files", "-z", "--", "*.md", "*.markdown"], {
    maxBuffer: discoveryLimit,
    // Discovery owns its case-sensitive recursive suffix pathspecs.
    env: { ...process.env, GIT_LITERAL_PATHSPECS: "0", GIT_GLOB_PATHSPECS: "0",
      GIT_NOGLOB_PATHSPECS: "0", GIT_ICASE_PATHSPECS: "0" },
  });
  if (result.error || result.status !== 0) {
    throw failure(
      "Git Markdown discovery failed.",
      "The tracked inventory could not be read completely within the 64 MiB capture limit.",
      "Run from the checked-out repository root; verify git ls-files succeeds and the inventory fits the limit."
    );
  }
  let text;
  try {
    text = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(result.stdout);
  } catch {
    throw failure("Git returned a non-UTF-8 Markdown path.", "Indexed paths must decode without loss.", "Rename the path to valid UTF-8 and update the index.");
  }
  if (!text) return [];
  if (!text.endsWith("\0")) {
    throw failure("Git returned an incomplete path inventory.", "NUL-delimited discovery must end at a path boundary.", "Verify git ls-files -z completes successfully.");
  }
  const names = text.slice(0, -1).split("\0");
  for (const name of names) {
    if (!name || /[\r\n\\]/u.test(name) || dirname(name).includes("+(")) throw unsupported(name);
    try {
      if (!(await stat(name)).isFile()) throw new Error("not a regular file");
      await access(name, constants.R_OK);
    } catch {
      throw failure(
        `Tracked Markdown path ${JSON.stringify(name)} is missing, unreadable, or not a file.`,
        "Every indexed input must be readable before consumer lint policy can filter it.",
        "Restore the file and its read permission or remove its stale index entry; use a complete checkout."
      );
    }
  }
  return names;
}

function contains(root, file) {
  const path = relative(root, file);
  return path !== ".." && !path.startsWith(`..${sep}`) && !isAbsolute(path);
}

async function run() {
  if (process.platform !== "linux") {
    throw failure("Unsupported runner platform.", "This adapter is qualified for Linux paths.", "Run ci-markdown on a Linux runner.");
  }
  const config = process.env.MARKDOWN_CONFIG_PATH;
  if (!config) throw failure("config-path is empty.", "A repo-owned Markdown policy is required.", "Set config-path to the checked-in configuration.");
  try {
    if (!(await stat(config)).isFile()) throw new Error("not a file");
    await access(config, constants.R_OK);
  } catch {
    throw failure(`Markdown config ${JSON.stringify(config)} is not readable.`, "The repository must supply its lint policy.", "Add the config file or correct config-path and read permissions.");
  }
  const names = await discover();
  if (!names.length) {
    console.log("No tracked Markdown files found.");
    return 0;
  }
  const prefix = await mkdtemp(join(process.env.RUNNER_TEMP || tmpdir(), "ci-markdown-"));
  try {
    for (const file of ["package.json", "package-lock.json"]) {
      await copyFile(join(actionRoot, file), join(prefix, file));
    }
    const manifest = JSON.parse(await readFile(join(prefix, "package.json"), "utf8"));
    const expectedVersion = manifest.dependencies?.["markdownlint-cli2"];
    if (typeof expectedVersion !== "string" || !expectedVersion) throw new Error("Missing Action-owned tool version");
    const install = spawnSync("npm", ["ci", "--prefix", prefix, "--ignore-scripts", "--no-audit", "--no-fund"], {
      cwd: prefix,
      stdio: "inherit",
    });
    if (install.error || install.status !== 0) {
      throw failure("Locked Markdown tool installation failed.", "The Action-owned dependency lock must install successfully before linting.", "Check npm availability, cache/registry access and the Action lock. User/environment npm settings apply; consumer project .npmrc is intentionally not loaded.");
    }
    const require = createRequire(join(prefix, "package.json"));
    const packageRoot = await realpath(join(prefix, "node_modules", "markdownlint-cli2"));
    const entry = await realpath(require.resolve("markdownlint-cli2"));
    const installed = JSON.parse(await readFile(join(packageRoot, "package.json"), "utf8"));
    if (!contains(await realpath(prefix), packageRoot) || !contains(packageRoot, entry) ||
        installed.name !== "markdownlint-cli2" || installed.version !== expectedVersion) {
      throw new Error("Installed Markdown tool does not match the Action-owned package identity");
    }
    const linterRequire = createRequire(entry);
    const { convertPathToPattern } = await import(pathToFileURL(linterRequire.resolve("globby")).href);
    const patterns = names.map((name) => {
      const pattern = convertPathToPattern(`./${name}`);
      // Version-bound adapter: the pinned CLI otherwise rewrites some literal escapes.
      if (pattern.replace(/\\(?![$()*+?[\]^])/gu, "/") !== pattern) throw unsupported(name);
      return pattern;
    });
    const { main } = await import(pathToFileURL(entry).href);
    const code = await main({
      argv: ["--config", config, "--", ...patterns],
      logMessage: (message) => console.log(message),
      logError: (message) => console.error(message),
    });
    if (!Number.isInteger(code) || code < 0 || code > 255) throw new Error("Markdown linter returned an invalid exit status");
    if (code !== 0) {
      console.error(failure("Markdown validation failed.", "The linter reported a rule, configuration, or input error above.", "Correct the reported error using the existing repository Markdown policy.").message);
    }
    return code;
  } finally {
    await rm(prefix, { recursive: true, force: true });
  }
}

try {
  process.exitCode = await run();
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  console.error(message.startsWith("WHAT:") ? message : failure(
    "Markdown validation could not complete.", message,
    "Check the Action package/lock, runner prerequisites, and repository configuration; do not treat this as a successful lint."
  ).message);
  process.exitCode = 1;
}
