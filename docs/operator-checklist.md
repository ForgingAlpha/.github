# Automation Operator Checklist

Complete these GitHub settings before merging the replacement workflows. Keep
the repository variable `V1_ROLLOUT_ENABLED` absent or `false` during bootstrap,
so the merge cannot move `v1` before the rollback path is proven:

- Require pull requests, approval, and `CI` on `.github/main`. Allow the
  automation App's exact-revision approval to satisfy the review requirement;
  do not bypass required CI.
- Create the `v1-rollback` environment, require operator approval, and verify
  the protection is active. GitHub otherwise auto-creates an unprotected
  environment on first use.
- Protect creation, update, and deletion of `v1`, `v1-rollout-*`,
  `v1-rollback-*`, and `v1-bootstrap-*` from identities other
  than the repository GitHub Actions workflow identity, scoped release identity,
  and operator.
- Confirm the workflow token may write repository contents only for release and
  rollback jobs.
- Install the automation GitHub App with repository contents and pull-request
  write, issues write, checks write, and read-only Dependabot-alert permissions.
  Store its ID
  and private key as organization Dependabot secrets named
  `ALPHAAPPS_AUTOMATION_APP_ID` and `ALPHAAPPS_AUTOMATION_PRIVATE_KEY`.
  Also store the ID as the organization Actions variable
  `ALPHAAPPS_AUTOMATION_APP_ID` and the private key as the organization Actions
  secret `ALPHAAPPS_AUTOMATION_PRIVATE_KEY`; post-merge promotion workflows run
  in the Actions context and require those stores.
- Create the `security-autopromote` label in every participating repository,
  including `ForgingAlpha/.github` and each application repository.
- Record the peeled current `v1` commit as both repository variable
  `V1_BOOTSTRAP_SHA` and lightweight tag `v1-bootstrap-<first 12 SHA>`. Confirm
  it is an ancestor of `main`; this explicit bootstrap exception exists because
  legacy `v1` predates the new `CI` contract.
- Protect creation, update, and deletion of `prod-*` promotion tags in every
  application repository. Confirm Turnkey's existing Integration bypass is the
  intended release App.
- Confirm the legacy release writer no longer exists on the merged branch.

Then merge `ForgingAlpha/.github` while rollout remains disabled. Confirm the
new workflows exist on `main` and `v1` did not move. Run the protected rollback
once against the bootstrap tag. Set `V1_ROLLOUT_ENABLED=true`, manually dispatch
`Roll Out v1` for the exact current green `main` SHA, and confirm the immutable
record plus `v1` movement. Re-running the old CI run must not re-advance a
rolled-back SHA.

Only then merge the four consumer branches, so their new inputs and action calls
resolve against the matching shared contract. The Turnkey and Outliers branches
remain intentionally blocked until their surfaced strict application findings
are fixed; do not weaken CI to merge them. Merge each green consumer promptly
after its prerequisite refactor.

- Treat a security promotion that reports an outdated `dev` SHA as a manual
  follow-up: another push won the race, so re-run the exact security change
  through current `dev` and promote only after its required CI succeeds.

Agents may prepare commands in `/tmp`; the operator performs ruleset changes,
destructive pushes, rollout activation, and rollback execution.

## Later Renovate Cutover

Do not begin this cutover until the `v1` bootstrap, rollback proof, and consumer
automation rollout above are complete. Follow
[`plans/renovate-normal-dependency-automation.md`](plans/renovate-normal-dependency-automation.md)
in order.

- Confirm `dev` is the default branch in every participating application
  repository and that protected `dev` requires pull requests and `CI` without
  automation bypass.
- After the transition-capable updater-neutral coverage gate and central preset
  are green, install the free hosted Renovate GitHub App on the site canary in
  silent lookup mode. Review its hosted dry-run logs before allowing it to
  create branches or pull requests.
- Keep Renovate vulnerability remediation disabled and retain GitHub Dependabot
  alerts and security updates.
- For each repository, convert Dependabot to security-only in the same protected
  change that flips its declared normal-update owner to active Renovate. The
  coverage gate must prove the complete destination mode on that exact head.
- Enable patch auto-merge on one site canary first. Expand to minor, major,
  runtime, and control-plane automation only after the plan's corresponding
  go/no-go evidence passes.
- Do not enroll obsolete deployment integrations in Renovate; remove them.
