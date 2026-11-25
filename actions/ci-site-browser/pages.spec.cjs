'use strict';

const path = require('node:path');
const { createRequire } = require('node:module');
const { readJSON, digest, siteSettings } = require('./site.cjs');
const { auditPage } = require('./accessibility.cjs');

const root = process.cwd();
const { test, expect } = createRequire(path.join(root, 'package.json'))('@playwright/test');
const { baseURL } = siteSettings(root);
for (const built of readJSON(process.env.SITE_BROWSER_INVENTORY)) {
  test(`accessibility of ${built.relative}`, async ({ page, context }) => {
    const origin = new URL(baseURL).origin;
    await context.route('**/*', (route) =>
      new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
    const response = await page.goto(built.url);
    expect(response).toBeTruthy();
    expect(new URL(page.url()).origin).toBe(origin);
    const expectedStatuses = ['404.html', '404/index.html'].includes(built.relative) ? [200, 404] : [200];
    expect(expectedStatuses).toContain(response.status());
    expect(response.headers()['content-type']).toMatch(/^text\/html\b/i);
    const served = await response.body();
    expect(digest(served), `Server must serve the original dist/${built.relative}`).toBe(built.sha256);
    await page.evaluate(() => document.fonts.ready);
    await auditPage(page);
  });
}
