# Product Evidence View

Generated from `docs/evidence/product-evidence.json`.

This view is derived evidence. It does not create or change product source truth.

## Stale

No promises in this status.

## None

No promises in this status.

## Manual-only

### REQ-007 - Roll required CI automation out through released tags

- Source: `docs/requirements.md#REQ-007`
- Type: `operational/quality`
- Status: `manual-only`
- Evidence:
  - `manual` `path:README.md` - Documents that required CI uses released refs such as v1, while manual probes are the latest-on-main exception.

### REQ-008 - Keep public repository content safe to expose

- Source: `docs/requirements.md#REQ-008`
- Type: `security/safety`
- Status: `manual-only`
- Evidence:
  - `manual` `manual:public-disclosure-sweep` - A public-disclosure sweep checks changed public files for local paths, private-key markers, and credential-like strings.

## Covered

### REQ-001 - Preserve one required CI status

- Source: `docs/requirements.md#REQ-001`
- Type: `integration/contract`
- Status: `covered`
- Evidence:
  - `auto` `path:tests/test_shared_ci_contract.py` - Tests that parent CI dogfoods bootstrap-safe local shared actions, preserves direct shell validation, and language composites preserve the shared CI contract inside one caller job.
  - `manual` `path:README.md` - Documents the uppercase CI job contract and composite-action usage that preserves the required status.

### REQ-003 - Run strict reproducible shared checks

- Source: `docs/requirements.md#REQ-003`
- Type: `operational/quality`
- Status: `covered`
- Evidence:
  - `auto` `path:actions/ci-markdown/tests/test_ci_markdown.py` - Tests the pinned Markdown lint version, changed-file helper behavior, ignore-prefix handling, and missing-base diagnostics.
  - `auto` `path:actions/ci-github-actions/tests/test_check_workflows.py` - Tests reusable GitHub Actions safety policy for composite action refs, allowlist reasons, privileged triggers, root permissions, and data-driven first-party pinning.
  - `auto` `path:actions/ci-dependency-review/tests/test_ci_dependency_review.py` - Tests the dependency-review wrapper defaults, pull-request scope, official action wrapper, and license-policy validation.
  - `auto` `path:actions/ci-dependabot-coverage/tests/test_check_dependabot_coverage.py` - Tests deterministic Dependabot coverage validation for detected dependency surfaces and documented unmanaged exceptions.
  - `auto` `path:tests/test_shared_ci_contract.py` - Tests that published language composites run shared policy, Markdown, conditional GitHub Actions safety, and Dependabot coverage before language-specific checks.

### REQ-009 - Do not require private alphaapps-docs checkout in consumer CI

- Source: `docs/requirements.md#REQ-009`
- Type: `security/safety`
- Status: `covered`
- Evidence:
  - `auto` `path:actions/ci-alphaapps-policy/tests/test_validate_product_evidence.py` - Tests that ci-alphaapps-policy has no private docs checkout dependency and no Product Evidence opt-out input.

### REQ-011 - Keep diagnostic workflows out of merge authority

- Source: `docs/requirements.md#REQ-011`
- Type: `integration/contract`
- Status: `covered`
- Evidence:
  - `auto` `path:actions/ci-remote-probe-guard/tests/test_validate_probe_inputs.py` - Tests the probe template is a manual read-only wrapper and reusable probe workflows stay workflow_call-only, read-only, and diagnostic-only.
  - `manual` `path:README.md` - Documents that manual remote diagnostic probes are non-required evidence collectors and that required CI remains merge authority.

### REQ-012 - Constrain diagnostic execution inputs

- Source: `docs/requirements.md#REQ-012`
- Type: `security/safety`
- Status: `covered`
- Evidence:
  - `auto` `path:actions/ci-remote-probe-guard/tests/test_validate_probe_inputs.py` - Tests valid exact/file/lane selectors, rejects invalid mode/lane/path/ref/line/label and command-like input, and proves the guard emits selectors instead of shell commands.
  - `manual` `path:actions/ci-remote-probe-guard/action.yml` - Defines the shared guard action inputs and selector outputs, including normalized checkout refs, without command-like inputs or outputs.

### REQ-012A - Use the latest approved diagnostic workflow on main

- Source: `docs/requirements.md#REQ-012A`
- Type: `integration/contract`
- Status: `covered`
- Evidence:
  - `auto` `path:tests/test_shared_ci_contract.py` - Tests the reusable probe workflows use ci-remote-probe-guard at @main and the public template calls a centralized @main reusable workflow.
  - `auto` `path:actions/ci-github-actions/tests/test_check_workflows.py` - Tests the GitHub Actions safety checker allows ForgingAlpha shared diagnostic actions and reusable workflows on @main while preserving ref validation.
  - `manual` `path:README.md` - Documents that manual probes intentionally use ForgingAlpha/.github@main so all repos run the latest approved diagnostic platform.

### REQ-012B - Keep probe command mapping repo-owned

- Source: `docs/requirements.md#REQ-012B`
- Type: `security/safety`
- Status: `covered`
- Evidence:
  - `auto` `path:tests/test_shared_ci_contract.py` - Tests reusable probe workflows invoke executable ./bin/ci-probe adapters and do not use eval for shared command execution.
  - `auto` `path:actions/ci-remote-probe-guard/tests/test_validate_probe_inputs.py` - Tests the wrapper stays thin while reusable workflows delegate repo-specific command mapping to ./bin/ci-probe.
  - `manual` `path:README.md` - Documents that consumer repositories own executable bin/ci-probe adapters that map validated selectors to reviewed local commands.

### REQ-014 - Emit actionable failure output

- Source: `docs/requirements.md#REQ-014`
- Type: `operational/quality`
- Status: `covered`
- Evidence:
  - `auto` `path:actions/ci-markdown/tests/test_ci_markdown.py` - Tests that missing changed-mode base refs fail with remediation guidance in the diagnostic output.
  - `auto` `path:actions/ci-github-actions/tests/test_check_workflows.py` - Tests that empty allowlist reasons fail and identify the exact exception entry to repair.
  - `auto` `path:actions/ci-dependabot-coverage/tests/test_check_dependabot_coverage.py` - Tests that missing Dependabot coverage and malformed unmanaged-surface comments emit actionable findings.
  - `auto` `path:actions/ci-remote-probe-guard/tests/test_validate_probe_inputs.py` - Tests that invalid remote probe selectors return WHAT/WHY/HOW diagnostics before command construction.

### REQ-015 - Self-validate workflow and action contracts before release

- Source: `docs/requirements.md#REQ-015`
- Type: `technical/architecture`
- Status: `covered`
- Evidence:
  - `auto` `path:tests/test_validate_github_actions.py` - Tests the deterministic GitHub Actions contract validator for action refs, permissions, pull_request_target, and nested action discovery.
  - `auto` `path:actions/ci-github-actions/tests/test_check_workflows.py` - Tests the reusable safety checker that scans workflow files and composite action.yml dependencies through the same policy.
  - `auto` `path:tests/test_shared_ci_contract.py` - Tests parent self-CI dogfood/bootstrap wiring, direct shell validation, and parseable public workflow examples before release.
  - `auto` `path:actions/ci-remote-probe-guard/tests/test_validate_probe_inputs.py` - Tests remote probe action metadata, the thin public wrapper template, and reusable probe workflows preserve the manual diagnostic contract before release.

### REQ-016 - Define a Dependabot coverage standard

- Source: `docs/requirements.md#REQ-016`
- Type: `operational/quality`
- Status: `covered`
- Evidence:
  - `auto` `path:actions/ci-dependabot-coverage/tests/test_check_dependabot_coverage.py` - Tests that public Dependabot templates are valid v2 configs and include GitHub Actions coverage.
  - `manual` `path:templates/dependabot/README.md` - Documents template selection, unmanaged-surface comments, and the boundary between Dependabot manifest updates and hardcoded version review.
  - `manual` `path:templates/dependabot/github-actions-only.yml` - Provides the GitHub Actions-only Dependabot template for workflows and shared composite action manifests.
  - `manual` `path:templates/dependabot/rust-cargo.yml` - Provides the Rust/Cargo plus GitHub Actions Dependabot template.
  - `manual` `path:templates/dependabot/npm.yml` - Provides the npm/Astro/TypeScript plus GitHub Actions Dependabot template.
  - `manual` `path:templates/dependabot/elixir-mix.yml` - Provides the Elixir/Mix plus GitHub Actions Dependabot template.
  - `manual` `path:templates/dependabot/mixed-app.yml` - Provides the mixed app template for repeated nested npm manifest directories.
  - `manual` `path:templates/dependabot/python.yml` - Provides the Python plus GitHub Actions Dependabot template.

### REQ-017 - Validate missing Dependabot coverage

- Source: `docs/requirements.md#REQ-017`
- Type: `technical/architecture`
- Status: `covered`
- Evidence:
  - `auto` `path:actions/ci-dependabot-coverage/tests/test_check_dependabot_coverage.py` - Tests missing config failures, nested action-manifest coverage, directory globs, report mode, and documented unmanaged-surface behavior.

### REQ-018 - Require approved baseline source truth for policy-checked repos

- Source: `docs/requirements.md#REQ-018`
- Type: `technical/architecture`
- Status: `covered`
- Evidence:
  - `auto` `path:actions/ci-alphaapps-policy/tests/test_validate_product_lifecycle_baseline.py` - Tests approved, missing, definition-only, and provisional baseline source-truth behavior for policy-checked repositories.

### REQ-020 - Require Product Evidence for active policy-checked repos

- Source: `docs/requirements.md#REQ-020`
- Type: `technical/architecture`
- Status: `covered`
- Evidence:
  - `auto` `path:actions/ci-alphaapps-policy/tests/test_validate_product_evidence.py` - Tests required manifest behavior, source-truth/evidence backfill allowance, malformed manifests, orphaned views, and stale generated views.
