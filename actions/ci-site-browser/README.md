# Website browser checks

Run this product check immediately after the website's normal build, while its
`dist` still contains that build. The website supplies the test server and
product journeys. The shared runner supplies the browser projects, emitted-page
checks and axe configuration.

## Website setup

Commit `@playwright/test` and `@axe-core/playwright` as development dependencies
with matching npm lockfile entries. Use a runner with the OS libraries required by
the selected Playwright browsers. The installation command downloads the matching
browser binaries without installing system packages. CI and developers run the
same commands from the website package root, after `npm ci` and the production build:

```sh
node "$SHARED_CHECKOUT/actions/ci-site-browser/install.cjs" pr
node "$SHARED_CHECKOUT/actions/ci-site-browser/run.cjs" pr
```

`SHARED_CHECKOUT` is the verified checkout of the shared CI revision. Use
`release` in both commands for the release matrix. The composite action takes
the same required `mode` and an optional `working-directory` (default `.`).

Commit a `site-browser.json` file:

```json
{
  "baseURL": "http://127.0.0.1:4321/",
  "serve": "preview:built",
  "testDir": "tests/e2e"
}
```

Set `baseURL` to the loopback HTTP address, including the website's base path and
trailing slash. The `serve` field names an npm script which serves the completed
release build at that address. Use the actual local Worker when redirects,
security headers or Worker behavior belong to the website's contract. The runner
starts a fresh server. The script must serve the built files without rebuilding
or publishing them.

## Required coverage

Both modes run the site's Playwright tests in desktop and phone-width Chromium.
At each width, the shared suite enumerates every HTML file in `dist`, follows the
site base path, checks that the response contains that file's bytes, and runs
axe. Directory indexes use their public directory URL. A built `404.html` or
`404/index.html` may return HTTP 404 with its own body. Symbolic links and empty
HTML inventories fail. The runner snapshots the HTML before starting the server
and verifies it again after the tests. The shared page scan blocks cross-origin requests.

Keep navigation, keyboard/focus and interactive-state assertions in the
site's regular Playwright specs under `testDir`. Mark at least one essential
journey with the Playwright tag or title token `@smoke`. Release mode also runs
these journeys in desktop Firefox and phone-width WebKit. Each required project
must execute a passing test. Tests use a single worker, fresh browser contexts,
and retain a Playwright trace on failure under `test-results/site-browser`.

For an open menu or another interactive state, a site-owned spec can invoke
the same axe check:

```js
const { auditPage } = require(process.env.SITE_BROWSER_AXE_HELPER);
await auditPage(page);
```

The rule set includes available WCAG 2.0, 2.1 and 2.2 A/AA rules, with installed
2.2 A/AA rules explicitly enabled. Every reported violation fails the test.
Keep manual keyboard, visual and assistive-technology acceptance checks where
the product requires them. Automated scans examine the page state at the time
of execution. Each site still owns its content, release obligations and manual
accessibility review.
