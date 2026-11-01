// Central bootstrap only: admitted text in, diagnostics out. No consumer discovery.
import { spawnSync } from "node:child_process";
import { copyFile, mkdtemp, readFile, realpath, rm } from "node:fs/promises";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join, relative, isAbsolute } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const actionRoot = dirname(dirname(fileURLToPath(import.meta.url)));
// Admission bounds text to 8 MiB and Git metadata to 1 MiB. Even worst-case
// JSON escaping (six bytes per text byte) plus path/syntax overhead fits here.
const limit = 64 * 1024 * 1024;
const fail = (message) => { throw new Error(message); };
const contains = (root, path) => {
  const value = relative(root, path);
  return value !== ".." && !value.startsWith("../") && !isAbsolute(value);
};

async function run() {
  if (process.platform !== "linux") fail("Linux is required for the bootstrap Markdown runner.");
  const chunks = [];
  let size = 0;
  for await (const chunk of process.stdin) {
    size += chunk.length;
    if (size > limit) fail("Admitted Markdown input exceeds the 64 MiB transport limit.");
    chunks.push(chunk);
  }
  const strings = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks)));
  if (!strings || Array.isArray(strings) || typeof strings !== "object" ||
      !Object.keys(strings).length || Object.values(strings).some(value => typeof value !== "string")) {
    fail("Expected a nonempty mapping of admitted Markdown paths to text.");
  }
  const config = JSON.parse(await readFile(join(actionRoot, "bootstrap-config.json"), "utf8"));
  const prefix = await mkdtemp(join(process.env.RUNNER_TEMP || tmpdir(), "bootstrap-markdown-"));
  try {
    for (const name of ["package.json", "package-lock.json"]) {
      await copyFile(join(actionRoot, name), join(prefix, name));
    }
    const manifest = JSON.parse(await readFile(join(prefix, "package.json"), "utf8"));
    // cwd is outside the consumer; its .npmrc and package scripts are never used.
    const install = spawnSync("npm", ["ci", "--prefix", prefix, "--ignore-scripts", "--no-audit", "--no-fund"], {
      cwd: prefix, stdio: "inherit", timeout: 120000,
    });
    if (install.error || install.status !== 0) fail("The Action-owned locked Markdown tool could not install.");
    const toolRequire = createRequire(join(prefix, "package.json"));
    const cliEntry = await realpath(toolRequire.resolve("markdownlint-cli2"));
    const installed = JSON.parse(await readFile(join(prefix, "node_modules/markdownlint-cli2/package.json"), "utf8"));
    if (!contains(await realpath(prefix), cliEntry) || installed.name !== "markdownlint-cli2" ||
        installed.version !== manifest.dependencies["markdownlint-cli2"]) fail("Locked tool identity mismatch.");
    const cliRequire = createRequire(cliEntry);
    const library = await realpath(cliRequire.resolve("markdownlint/sync"));
    if (!contains(await realpath(prefix), library)) fail("Markdown library escaped the isolated install.");
    const { lint } = await import(pathToFileURL(library).href);
    const results = lint({ strings, config, noInlineConfig: true });
    let count = 0;
    for (const [path, errors] of Object.entries(results)) {
      for (const error of errors) {
        if (count++ < 200) console.error(`${JSON.stringify(path)}:${error.lineNumber} ${error.ruleNames[0]}`);
      }
    }
    if (count) fail(`${count} Markdown violations; diagnostics show at most the first 200.`);
    console.log(`Validated ${Object.keys(strings).length} canonical Markdown inputs under central rules.`);
  } finally {
    await rm(prefix, { recursive: true, force: true });
  }
}

run().catch(error => {
  console.error(`WHAT: ${error.message}\nWHY: The complete bootstrap profile requires data-only central Markdown validation.\nHOW: Repair the document or locked tool prerequisite; executable config and inline rule suppression are unsupported.`);
  process.exitCode = 1;
});
