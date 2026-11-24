'use strict';

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
    if (missing.length) {
      console.error(`Missing passing website tests for: ${missing.join(', ')}. Release smoke tests must carry @smoke.`);
      return { status: 'failed' };
    }
  }
};
