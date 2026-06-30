# Product Evidence View

Generated from `docs/evidence/product-evidence.json`.

This view is derived evidence. It does not create or change product source truth.

## Stale

No promises in this status.

## None

### REQ-009 - Do not require private alphaapps-docs checkout in consumer CI

- Source: `docs/requirements.md#REQ-009`
- Type: `security/safety`
- Status: `none`
- Planned context: `Phase 2 ci-alphaapps-policy implementation and public action review`
- Evidence: none

### REQ-018 - Require approved baseline source truth for policy-checked repos

- Source: `docs/requirements.md#REQ-018`
- Type: `technical/architecture`
- Status: `none`
- Planned context: `Phase 2 baseline lifecycle validator implementation`
- Evidence: none

### REQ-020 - Require Product Evidence for active policy-checked repos

- Source: `docs/requirements.md#REQ-020`
- Type: `technical/architecture`
- Status: `none`
- Planned context: `Phase 2 required Product Evidence validator implementation`
- Evidence: none

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

### REQ-015 - Self-validate workflow and action contracts before release

- Source: `docs/requirements.md#REQ-015`
- Type: `technical/architecture`
- Status: `covered`
- Evidence:
  - `auto` `path:tests/test_validate_github_actions.py` - Tests the deterministic GitHub Actions contract validator for action refs, permissions, pull_request_target, and nested action discovery.
