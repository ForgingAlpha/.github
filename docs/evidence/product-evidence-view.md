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
  - `manual` `manual:phase-1-public-disclosure-sweep` - Phase 1 closeout runs a public-disclosure sweep over changed public files before commit.

### REQ-009 - Do not require private alphaapps-docs checkout in consumer CI

- Source: `docs/requirements.md#REQ-009`
- Type: `security/safety`
- Status: `manual-only`
- Evidence:
  - `manual` `path:docs/architecture.md` - Defines the public/private boundary and self-contained shared policy action model.

### REQ-018 - Require approved baseline source truth for policy-checked repos

- Source: `docs/requirements.md#REQ-018`
- Type: `technical/architecture`
- Status: `manual-only`
- Evidence:
  - `manual` `path:docs/requirements.md` - Defines approved intent, requirements, and architecture enforcement for active ForgingAlpha repositories that run the policy check.

### REQ-020 - Require Product Evidence for active policy-checked repos

- Source: `docs/requirements.md#REQ-020`
- Type: `technical/architecture`
- Status: `manual-only`
- Evidence:
  - `manual` `path:docs/requirements.md` - Defines the required Product Evidence behavior and the source-truth/evidence-backfill-only path while a manifest is missing.

## Covered

### REQ-015 - Self-validate workflow and action contracts before release

- Source: `docs/requirements.md#REQ-015`
- Type: `technical/architecture`
- Status: `covered`
- Evidence:
  - `auto` `path:tests/test_validate_github_actions.py` - Tests the deterministic GitHub Actions contract validator for action refs, permissions, pull_request_target, and nested action discovery.
