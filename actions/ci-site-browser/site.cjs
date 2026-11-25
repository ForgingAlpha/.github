'use strict';

const fs = require('node:fs');
const os = require('node:os');
const { createHash } = require('node:crypto');
const path = require('node:path');
const { createRequire } = require('node:module');
const { spawnSync } = require('node:child_process');
const { pipeline } = require('node:stream/promises');

const readJSON = (file) => JSON.parse(fs.readFileSync(file, 'utf8'));

function modeFrom(args) {
  if (args.length !== 1 || !['pr', 'release'].includes(args[0])) {
    throw Error('Expected a single mode argument: pr or release.');
  }
  return args[0];
}

function lockedTool(root, name) {
  const manifest = readJSON(path.join(root, 'package.json'));
  const lock = readJSON(path.join(root, 'package-lock.json'));
  const declaration = manifest.devDependencies?.[name];
  const locked = lock.packages?.[`node_modules/${name}`];
  if (!declaration || lock.packages?.['']?.devDependencies?.[name] !== declaration ||
      !locked?.integrity || !locked.version) {
    throw Error(`Commit ${name} as a locked devDependency of this website.`);
  }
  const installed = readJSON(path.join(root, 'node_modules', name, 'package.json'));
  if (installed.name !== name || installed.version !== locked.version) {
    throw Error(`Installed ${name} differs from package-lock.json. Run npm ci.`);
  }
}

function siteSettings(root) {
  const { baseURL, serve, testDir } = readJSON(path.join(root, 'site-browser.json'));
  const url = new URL(baseURL);
  if (url.protocol !== 'http:' || !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname) ||
      url.username || url.password || url.search || url.hash || !url.pathname.endsWith('/')) {
    throw Error('baseURL must be a loopback HTTP URL ending with the site base path and a slash.');
  }
  const scripts = readJSON(path.join(root, 'package.json')).scripts ?? {};
  if (typeof serve !== 'string' || !/^[a-z\d][a-z\d:._-]*$/i.test(serve) ||
      !Object.hasOwn(scripts, serve) || typeof scripts[serve] !== 'string' || !scripts[serve].trim()) {
    throw Error('serve must name the npm script that serves the already-built site.');
  }
  if (typeof testDir !== 'string' || !testDir || path.isAbsolute(testDir)) {
    throw Error('testDir must name a directory of site-owned Playwright tests.');
  }
  const testRoot = fs.realpathSync(path.join(root, testDir));
  if (!testRoot.startsWith(fs.realpathSync(root) + path.sep) || !fs.statSync(testRoot).isDirectory()) {
    throw Error('testDir must be a directory inside the website.');
  }
  return { baseURL: url.href, serve, testDir: testRoot };
}

function digest(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

async function builtSite(root, baseURL) {
  const artifact = path.join(root, 'dist');
  if (!fs.lstatSync(artifact).isDirectory()) throw Error('dist must be a built directory.');
  const files = [];
  const pages = [];
  async function walk(dir, prefix) {
    const entries = fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name, 'en'));
    for (const entry of entries) {
      const file = path.join(dir, entry.name);
      const relative = prefix + entry.name;
      if (entry.isDirectory()) {
        await walk(file, relative + '/');
        continue;
      }
      if (!entry.isFile()) throw Error(`Unexpected link or special file in built output: ${relative}`);
      const hash = createHash('sha256');
      await pipeline(fs.createReadStream(file), hash);
      const sha256 = hash.digest('hex');
      files.push({ relative, sha256 });
      if (/\.html$/i.test(entry.name)) {
        const route = relative.split('/').map(encodeURIComponent).join('/').replace(/(^|\/)index\.html$/, '$1');
        pages.push({ relative, url: new URL(route, baseURL).href, sha256 });
      }
    }
  }
  await walk(artifact, '');
  if (!pages.length) throw Error('No public HTML found in dist. Run the production build first.');
  return { files, pages };
}

async function invoke(kind, args) {
  let temporary;
  try {
    const mode = modeFrom(args);
    const root = process.cwd();
    lockedTool(root, '@playwright/test');
    const fromSite = createRequire(path.join(root, 'package.json'));
    const cli = fromSite.resolve('@playwright/test/cli');
    let command;
    let inventory;
    let baseURL;
    const env = { ...process.env, SITE_BROWSER_MODE: mode, SITE_BROWSER_AXE_HELPER: path.join(__dirname, 'accessibility.cjs') };
    if (kind === 'install') {
      const browsers = mode === 'release' ? ['chromium', 'firefox', 'webkit'] : ['chromium'];
      command = ['install', ...browsers];
    } else {
      lockedTool(root, '@axe-core/playwright');
      ({ baseURL } = siteSettings(root));
      inventory = await builtSite(root, baseURL);
      temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'website-browser-'));
      env.SITE_BROWSER_INVENTORY = path.join(temporary, 'pages.json');
      env.SITE_BROWSER_COMPLETION = path.join(temporary, 'completed');
      fs.writeFileSync(env.SITE_BROWSER_INVENTORY, JSON.stringify(inventory.pages), { mode: 0o400 });
      command = ['test', '--config', path.join(__dirname, 'playwright.config.cjs')];
    }
    const child = spawnSync(process.execPath, [cli, ...command], {
      cwd: root,
      stdio: 'inherit',
      env,
    });
    if (child.error) throw child.error;
    if (child.status === 0 && inventory) {
      if (!fs.existsSync(env.SITE_BROWSER_COMPLETION)) {
        throw Error('Playwright did not confirm a passing test in every required browser project.');
      }
      if (JSON.stringify(inventory.files) !== JSON.stringify((await builtSite(root, baseURL)).files)) {
        throw Error('The built site changed during browser testing. Serve the original build and keep its output intact.');
      }
    }
    process.exitCode = child.status ?? 1;
  } catch (error) {
    console.error(`Website browser ${kind} failed: ${error.message}`);
    process.exitCode = 1;
  } finally {
    if (temporary) fs.rmSync(temporary, { recursive: true, force: true });
  }
}

module.exports = { readJSON, digest, modeFrom, lockedTool, siteSettings, builtSite, invoke };
