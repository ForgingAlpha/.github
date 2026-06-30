# Product Evidence View

Generated from `docs/evidence/product-evidence.json`.

This view is derived evidence. It does not create or change product source truth.

## Stale

No promises in this status.

## None

No promises in this status.

## Manual-only

### REQ-001 - Preserve one required CI status

- Source: `docs/requirements.md#REQ-001`
- Type: `integration/contract`
- Status: `manual-only`
- Evidence:
  - `manual` `path:README.md` - Documents the uppercase CI job contract and composite-action usage that preserves the required status.

### REQ-007 - Roll shared automation out through released tags

- Source: `docs/requirements.md#REQ-007`
- Type: `operational/quality`
- Status: `manual-only`
- Evidence:
  - `manual` `path:README.md` - Documents that merging to main does not roll out shared action changes until a released major tag such as v1 moves.

### REQ-008 - Keep public repository content safe to expose

- Source: `docs/requirements.md#REQ-008`
- Type: `security/safety`
- Status: `manual-only`
- Evidence:
  - `manual` `manual:public-disclosure-sweep` - A public-disclosure sweep checks changed public files for local paths, private-key markers, and credential-like strings.

## Covered

### REQ-003 - Run strict reproducible shared checks

- Source: `docs/requirements.md#REQ-003`
- Type: `operational/quality`
- Status: `covered`
- Evidence:
  - `auto` `path:actions/ci-markdown/tests/test_ci_markdown.py` - Tests the pinned Markdown lint version, changed-file helper behavior, ignore-prefix handling, and missing-base diagnostics.
  - `auto` `path:actions/ci-github-actions/tests/test_check_workflows.py` - Tests reusable GitHub Actions safety policy for composite action refs, allowlist reasons, privileged triggers, root permissions, and data-driven first-party pinning.

### REQ-009 - Do not require private alphaapps-docs checkout in consumer CI

- Source: `docs/requirements.md#REQ-009`
- Type: `security/safety`
- Status: `covered`
- Evidence:
  - `auto` `path:actions/ci-alphaapps-policy/tests/test_validate_product_evidence.py` - Tests that ci-alphaapps-policy has no private docs checkout dependency and no Product Evidence opt-out input.

### REQ-014 - Emit actionable failure output

- Source: `docs/requirements.md#REQ-014`
- Type: `operational/quality`
- Status: `covered`
- Evidence:
  - `auto` `path:actions/ci-markdown/tests/test_ci_markdown.py` - Tests that missing changed-mode base refs fail with remediation guidance in the diagnostic output.
  - `auto` `path:actions/ci-github-actions/tests/test_check_workflows.py` - Tests that empty allowlist reasons fail and identify the exact exception entry to repair.

### REQ-015 - Self-validate workflow and action contracts before release

- Source: `docs/requirements.md#REQ-015`
- Type: `technical/architecture`
- Status: `covered`
- Evidence:
  - `auto` `path:tests/test_validate_github_actions.py` - Tests the deterministic GitHub Actions contract validator for action refs, permissions, pull_request_target, and nested action discovery.
  - `auto` `path:actions/ci-github-actions/tests/test_check_workflows.py` - Tests the reusable safety checker that scans workflow files and composite action.yml dependencies through the same policy.

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
