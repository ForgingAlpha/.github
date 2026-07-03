# Product Lifecycle Review - Probe Latest Platform

Status: pass

## Review Metadata

Base Ref: main
Base SHA: 0cdad6031334d05cf1058fdfcf68bc33b358ef44
Head SHA: 6329b9079ca7a46d884eb427f8b3c2eaff02510f
Reviewer: reviewer-product-development-lifecycle
Review Date: 2026-07-03

## Changed Lifecycle Files

Changed lifecycle files:

- docs/architecture.md
- docs/plans/shared-ci-policy-baseline.md
- docs/requirements.md

## Downstream Evidence Files Reviewed

- docs/evidence/product-evidence.json
- docs/evidence/product-evidence-view.md

## Reviewed Sources

- docs/intent.md
- docs/requirements.md
- docs/architecture.md
- docs/plans/shared-ci-policy-baseline.md
- docs/evidence/product-evidence.json
- docs/evidence/product-evidence-view.md
- README.md
- .github/workflows/ci-probe-docs.yml
- .github/workflows/ci-probe-elixir-postgres.yml
- .github/workflows/ci-probe-rust.yml
- workflow-templates/ci-probe.yml
- actions/ci-github-actions/scripts/check_workflows.py
- actions/ci-github-actions/tests/test_check_workflows.py
- actions/ci-remote-probe-guard/tests/test_validate_probe_inputs.py
- tests/test_shared_ci_contract.py
- tests/test_validate_github_actions.py

## Verification Evidence

- Confirmed `docs/intent.md`, `docs/requirements.md`, and
  `docs/architecture.md` are `status: approved`.
- Confirmed this PR changes lifecycle files only in `docs/requirements.md`,
  `docs/architecture.md`, and `docs/plans/shared-ci-policy-baseline.md`.
- Confirmed required CI remains on released shared-action refs such as `@v1`
  while manual diagnostic probes are documented as the latest-on-main
  exception.
- Confirmed `REQ-012A` defines latest-on-main diagnostics as manual,
  non-required, and not merge authority.
- Confirmed `REQ-012B` keeps probe command mapping and runtime-specific details
  in the consuming repository through an executable `bin/ci-probe` adapter.
- Confirmed architecture separates required-CI rollout through released tags
  from manual probe rollout through centralized reusable workflows at
  `ForgingAlpha/.github@main`.
- Confirmed Product Evidence remains downstream of source truth and records the
  new diagnostic requirements without inventing product scope.
- Confirmed `docs/plans/shared-ci-policy-baseline.md` remains execution
  authority and describes the approved implementation boundary: shared probe
  workflows and guard own safety scaffolding; consumer repos own runtime command
  adapters, lane allowlists, and repo-specific environment.
- Confirmed the initial reusable Elixir/Postgres probe draft embedded
  consumer-specific Turnkey and Outliers runtime environment names. That
  finding was fixed before closeout by replacing them with generic
  Postgres/Mix defaults and adding a regression contract test that rejects
  consumer-specific probe markers in shared reusable workflows.
- Confirmed the reviewer rerun found source-truth alignment holds after the
  boundary fix and identified only stale lifecycle review evidence as the
  remaining blocker; this audit file records the fresh review evidence for the
  current PR comparison.

## Deterministic Verification

- `python3 -m unittest discover -s tests`
- `python3 -m unittest discover -s actions/ci-github-actions/tests`
- `python3 -m unittest discover -s actions/ci-remote-probe-guard/tests`
- `python3 scripts/validate-github-actions.py`
- `python3 actions/ci-alphaapps-policy/scripts/validate_durable_evidence_references.py`
- `python3 actions/ci-alphaapps-policy/scripts/validate_product_evidence.py`
- `python3 /home/leosmigel/src/github.com/forgingalpha/alphaapps-docs/system/scripts/render-product-evidence.py --manifest docs/evidence/product-evidence.json --output docs/evidence/product-evidence-view.md --check`
- YAML parse for actions, `.github`, and `workflow-templates`
- `npx --yes markdownlint-cli2@0.22.1 --config .markdownlint-cli2.yaml README.md docs/requirements.md docs/architecture.md docs/evidence/product-evidence-view.md docs/plans/shared-ci-policy-baseline.md`
- actionlint `1.7.12` over `.github/workflows/*.yml` and
  `workflow-templates/*.yml`
- `git diff --check`

## Lifecycle Verdict

Pass. The latest-on-main diagnostic probe model is now represented as an
explicit manual, non-required exception to the required-CI `@v1` release-tag
rollout model. The approved intent, requirements, and architecture remain
source truth; Product Evidence remains downstream; and repo-specific probe
runtime behavior stays owned by consuming repositories.

## Residual Risk

- Consumer repositories still need their own thin manual wrappers and
  executable `bin/ci-probe` adapters before operators can run probes there.
