'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { modeFrom, lockedTool, siteSettings, builtSite } = require('../site.cjs');
const RequiredProjects = require('../required-projects.cjs');

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ci-site-browser-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return root;
}

test('public URLs include the base path, encode filenames and preserve distinct HTML pages', async (t) => {
  const root = fixture(t);
  const files = ['index.html', 'about/index.html', '404.html', 'a #.html', 'static/logo.svg'];
  for (const name of files) {
    const dest = path.join(root, 'dist', name);
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.writeFileSync(dest, name);
  }
  const { files: original, pages } = await builtSite(root, 'http://127.0.0.1:4041/prefix/');
  assert.deepEqual(Object.fromEntries(pages.map((page) => [page.relative, new URL(page.url).pathname])), {
    'index.html': '/prefix/', 'about/index.html': '/prefix/about/', '404.html': '/prefix/404.html', 'a #.html': '/prefix/a%20%23.html',
  });
  assert.deepEqual(original.map((file) => file.relative).sort(), [...files].sort());
  const asset = path.join(root, 'dist', 'static/logo.svg');
  fs.writeFileSync(asset, 'different SVG');
  const changed = await builtSite(root, 'http://127.0.0.1:4041/prefix/');
  assert.deepEqual(changed.pages, pages);
  assert.notDeepEqual(changed.files, original);
});

test('absent or empty builds and links in output fail closed', async (t) => {
  const root = fixture(t);
  await assert.rejects(() => builtSite(root, 'http://localhost/'), /ENOENT/);
  fs.mkdirSync(path.join(root, 'dist'));
  await assert.rejects(() => builtSite(root, 'http://localhost/'), /No public HTML/);
  fs.symlinkSync(root, path.join(root, 'dist', 'other'));
  await assert.rejects(() => builtSite(root, 'http://localhost/'), /Unexpected link/);
});

test('only explicit modes and existing inside-site journeys with a valid server are admitted', (t) => {
  assert.equal(modeFrom(['release']), 'release');
  for (const args of [[], ['production'], ['pr', '--pass-with-no-tests']]) assert.throws(() => modeFrom(args));
  const root = fixture(t);
  fs.mkdirSync(path.join(root, 'journeys'));
  fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ scripts: { 'serve:built': 'node serve.cjs' } }));
  const base = { baseURL: 'http://localhost:4100/review/', serve: 'serve:built', testDir: 'journeys' };
  const load = (fields) => {
    fs.writeFileSync(path.join(root, 'site-browser.json'), JSON.stringify({ ...base, ...fields }));
    return siteSettings(root);
  };
  assert.equal(load({}).testDir, path.join(root, 'journeys'));
  for (const fields of [{ baseURL: 'https://example.com/' }, { baseURL: 'http://localhost/base' }, { baseURL: 'http://user@localhost/' }, { serve: 'serve:built; true' }, { serve: 'absent' }, { testDir: '..' }]) {
    assert.throws(() => load(fields));
  }
});

test('missing or mismatched consumer tool installations cannot substitute an npm download', (t) => {
  const root = fixture(t);
  const name = '@playwright/test';
  const devDependencies = { [name]: '1.2.3' };
  fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ devDependencies }));
  const entry = `node_modules/${name}`;
  fs.writeFileSync(path.join(root, 'package-lock.json'), JSON.stringify({ packages: {
    '': { devDependencies }, [entry]: { version: '1.2.3', integrity: 'test-only' },
  } }));
  assert.throws(() => lockedTool(root, name), /ENOENT/);
  fs.mkdirSync(path.join(root, entry), { recursive: true });
  const install = (version) => fs.writeFileSync(path.join(root, entry, 'package.json'), JSON.stringify({ name, version }));
  install('1.2.4');
  assert.throws(() => lockedTool(root, name), /differs/);
  install('1.2.3');
  assert.doesNotThrow(() => lockedTool(root, name));
});

test('required projects cannot pass through empty, skipped or expected-to-fail journeys', (t) => {
  const completion = path.join(fixture(t), 'completed');
  const previous = process.env.SITE_BROWSER_COMPLETION;
  process.env.SITE_BROWSER_COMPLETION = completion;
  t.after(() => {
    if (previous === undefined) delete process.env.SITE_BROWSER_COMPLETION;
    else process.env.SITE_BROWSER_COMPLETION = previous;
  });
  const reporter = new RequiredProjects();
  const project = { name: 'smoke-webkit' };
  function disposition(tests) {
    reporter.onBegin({ projects: [project] }, { allTests: () => tests });
    return reporter.onEnd({ status: 'passed' });
  }
  const fact = (expectedStatus, status) => ({ expectedStatus, parent: { project: () => project }, results: [{ status }] });
  assert.deepEqual(disposition([]), { status: 'failed' });
  assert.deepEqual(disposition([fact('skipped', 'skipped'), fact('failed', 'failed')]), { status: 'failed' });
  assert.equal(fs.existsSync(completion), false);
  assert.equal(disposition([fact('passed', 'passed')]), undefined);
  assert.equal(fs.readFileSync(completion, 'utf8'), 'passed');
});

test('a successful CLI exit alone cannot certify the required browser projects', (t) => {
  const root = fixture(t);
  const deps = { '@playwright/test': '1.0.0', '@axe-core/playwright': '1.0.0' };
  const packages = { '': { devDependencies: deps } };
  for (const [name, version] of Object.entries(deps)) {
    const dir = path.join(root, 'node_modules', name);
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, 'package.json'), JSON.stringify({ name, version, exports: { './cli': './cli.cjs' } }));
    packages[`node_modules/${name}`] = { version, integrity: 'fixture' };
  }
  fs.writeFileSync(path.join(root, 'node_modules/@playwright/test/cli.cjs'), 'process.exit(0)');
  fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ devDependencies: deps, scripts: { preview: 'fixture' } }));
  fs.writeFileSync(path.join(root, 'package-lock.json'), JSON.stringify({ packages }));
  fs.writeFileSync(path.join(root, 'site-browser.json'), JSON.stringify({
    baseURL: 'http://127.0.0.1:4321/', serve: 'preview', testDir: 'journeys',
  }));
  fs.mkdirSync(path.join(root, 'journeys'));
  fs.mkdirSync(path.join(root, 'dist'));
  fs.writeFileSync(path.join(root, 'dist/index.html'), '<p>Fixture</p>');
  const run = require('node:child_process').spawnSync(process.execPath, [path.join(__dirname, '../run.cjs'), 'release'], {
    cwd: root, encoding: 'utf8',
  });
  assert.equal(run.status, 1);
  assert.match(run.stderr, /did not confirm a passing test in every required browser project/);
});
