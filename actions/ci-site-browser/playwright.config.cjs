'use strict';

const path = require('node:path');
const { modeFrom, siteSettings } = require('./site.cjs');

const root = process.cwd();
const site = siteSettings(root);
const mode = modeFrom([process.env.SITE_BROWSER_MODE]);
const desktop = { width: 1280, height: 900 };
const phone = { width: 390, height: 844 };

const projects = [];
for (const [size, viewport] of Object.entries({ desktop, phone })) {
  const use = { browserName: 'chromium', viewport, isMobile: size === 'phone', hasTouch: size === 'phone' };
  projects.push(
    { name: `pages-${size}`, testDir: __dirname, testMatch: 'pages.spec.cjs', use },
    { name: `journeys-${size}`, testDir: site.testDir, use },
  );
}
if (mode === 'release') {
  for (const [browserName, viewport] of [['firefox', desktop], ['webkit', phone]]) {
    projects.push({
      name: `smoke-${browserName}`,
      testDir: site.testDir,
      grep: /(?:^|\s)@smoke(?:\s|$)/,
      use: { browserName, viewport, isMobile: browserName === 'webkit', hasTouch: browserName === 'webkit' },
    });
  }
}

module.exports = {
  projects,
  forbidOnly: true,
  workers: 1,
  retries: 0,
  outputDir: path.join(root, 'test-results', 'site-browser'),
  reporter: [['list'], [require.resolve('./required-projects.cjs')]],
  use: { baseURL: site.baseURL, trace: 'retain-on-failure' },
  webServer: {
    cwd: root,
    command: `npm run ${site.serve}`,
    url: site.baseURL,
    reuseExistingServer: false,
  },
};
