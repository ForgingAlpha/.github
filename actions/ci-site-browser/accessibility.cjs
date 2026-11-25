'use strict';

const path = require('node:path');
const { createRequire } = require('node:module');
const fromSite = createRequire(path.join(process.cwd(), 'package.json'));
const { AxeBuilder } = fromSite('@axe-core/playwright');
const fromAdapter = createRequire(fromSite.resolve('@axe-core/playwright'));
const axe = fromAdapter('axe-core');
const tags = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22a', 'wcag22aa'];
// axe disables some 2.2 rules by default. Explicitly enable those supplied by the installed engine.
const wcag22Rules = axe.getRules(['wcag22a', 'wcag22aa']);
if (!wcag22Rules.length) throw Error('Installed axe-core provides no WCAG 2.2 A/AA rules.');
const rules = Object.fromEntries(wcag22Rules.map(({ ruleId }) => [ruleId, { enabled: true }]));

exports.auditPage = async function auditPage(page) {
  const result = await new AxeBuilder({ page }).options({ runOnly: { type: 'tag', values: tags }, rules }).analyze();
  if (result.violations.length) {
    const details = result.violations.map(({ id, nodes, helpUrl }) => `${id} (${nodes.length} nodes): ${helpUrl}`);
    throw Error(`Accessibility violations on ${new URL(page.url()).pathname}:\n${details.join('\n')}`);
  }
};
