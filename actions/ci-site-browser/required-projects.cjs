'use strict';

const fs = require('node:fs');

module.exports = class RequiredProjects {
  onBegin(config, suite) {
    this.projects = config.projects.map((project) => project.name);
    this.suite = suite;
  }

  onEnd(result) {
    if (result.status !== 'passed') return;
    const ran = new Set(this.suite.allTests()
      .filter((test) => test.expectedStatus === 'passed' && test.results.some((attempt) => attempt.status === 'passed'))
      .map((test) => test.parent.project().name));
    const missing = this.projects.filter((name) => !ran.has(name));
    if (!this.projects.length || missing.length) {
      console.error(`Missing passing website tests for: ${missing.join(', ')}. Release smoke tests must carry @smoke.`);
      return { status: 'failed' };
    }
    fs.writeFileSync(process.env.SITE_BROWSER_COMPLETION, 'passed', { flag: 'wx', mode: 0o600 });
  }
};
