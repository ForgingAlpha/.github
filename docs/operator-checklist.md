# Automation Operator Checklist

Complete these GitHub settings before merging the replacement workflows. Keep
the repository variable `V1_ROLLOUT_ENABLED` absent or `false` during initial
cutover, so the merge cannot move `v1` before the release controls are proven:

- Treat this pull request as the one-time CODEOWNERS bootstrap. GitHub evaluates
  CODEOWNERS from the pull request's base branch, so the new file cannot enforce
  itself before merge. The operator must manually review and approve the exact
  final head, perform the merge, and immediately verify the merged file and
  ruleset before any later control-plane change proceeds.

- Require pull requests, authorized-human code-owner approval of the exact
  current revision, dismissal of stale approvals, and `CI` on `.github/main`.
  The agent/authoring App may create and update the pull request but cannot
  satisfy the approval, bypass required CI, or merge `main`. Keep the scoped
  security and release Apps separate from that authoring identity.
- Create the `v1-rollback` environment, require operator approval, and verify
  the protection is active. GitHub otherwise auto-creates an unprotected
  environment on first use.
- Protect creation, update, and deletion of `v1`, `v1-rollout-*`,
  and `v1-rollback-*` from identities other than the repository GitHub Actions
  workflow identity, scoped release identity, and operator.
- Confirm the workflow token may write repository contents only for release and
  rollback jobs.
- For every private consumer repository, confirm the dependency graph and
  GitHub dependency review are enabled and that the organization has the GitHub
  Code Security/Advanced Security entitlement required by the official action.
  Do not merge the consumer rollout until a pull-request probe returns real
  dependency-change output.
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
- Protect creation, update, and deletion of `prod-*` promotion tags in every
  application repository. Confirm Turnkey's existing Integration bypass is the
  intended release App.
- Confirm the legacy release writer no longer exists on the merged branch.

Before enabling approved auto-activation, confirm `Allow auto-merge` is enabled
in each participating repository. Store `FORGINGALPHA_RELEASE_APP_CLIENT_ID` as an
organization Actions variable and `FORGINGALPHA_RELEASE_APP_PRIVATE_KEY` as an
organization Actions secret for only the enrolled repositories. The protected
release App must have only repository metadata read, contents write, and pull
request write permission. Token creation must remain scoped to the current
repository. The agent/authoring App must not receive the release credential or
a ruleset bypass.

For every enrolled persistent branch, require the authorized human's code-owner
review, dismiss stale approvals when the pull-request diff or merge base
changes, require the approved `CI` check, and require the branch to be current
with its target before merge. Restrict branch updates to the operator and
narrowly scoped protected automation. Give `forgingalpha-release`
pull-request-only bypass authority, never always-allow authority, and prohibit
admin-bypass merge commands in the protected workflow.

The auto-activation path intentionally follows GitHub's privilege-separation
pattern. `approval-signal.yml` runs in the pull-request context with no token
permissions, secrets, checkout, or executable pull-request content. Its
completion triggers `approved-auto-activation.yml` through `workflow_run`, so
the privileged caller and reusable workflow are loaded from the default branch.
The protected workflow treats the associated pull-request number as untrusted
passive data, re-queries GitHub, and requires the authorized human's latest
authoritative review to be `APPROVED` on the current full head SHA before it
invokes GitHub native auto-merge with `--match-head-commit`. GitHub rulesets,
not a parallel custom state machine, remain responsible for current approvals,
required checks, merge-base freshness, and branch-update restrictions.

Roll out `approval-signal.yml` and `approved-auto-activation.yml` to each
consumer with that repository's complete persistent-branch list. The first
workflow pull request is a manual bootstrap because its default branch does not
yet contain the privileged `workflow_run` caller. After it merges, use a
harmless same-repository probe to prove that an unchanged approved revision is
merged only by `forgingalpha-release`, while a draft, changed revision, stale or
dismissed approval, fork head, and undeclared target remain unmerged. Do not add
a merge queue until branch traffic justifies its additional `merge_group` CI
surface.

Approval is the routine activation decision, so exceptional operations must be
held before approval. Delay approval for coordinated launches, and use the
operation's separately governed environment or workflow approval for
destructive, non-repeatable, legal, or business-timed effects. Do not add a
generic post-approval merge click or a label-based revocation race.

Then merge `ForgingAlpha/.github` while rollout remains disabled. Confirm the
new workflows exist on `main` and `v1` did not move. Before moving `v1`, add the
canonical CODEOWNERS contract to every active consumer and control-plane
repository while those repositories still use the existing `v1`. Each initial
CODEOWNERS pull request is also a one-time bootstrap because GitHub reads the
file from that pull request's base branch: the operator manually reviews and
approves its exact final head, performs the merge, and then verifies GitHub's
CODEOWNERS error endpoint reports no errors. Verify each protected
persistent-branch ruleset requires code-owner review, dismisses stale
approvals, requires `CI`, gives the agent/authoring identity no bypass, and
allows only the intended scoped updater, security, or release operations.

After every consumer passes its existing CI with the ownership contract, set
`V1_ROLLOUT_ENABLED=true`, manually dispatch `Roll Out v1` for the exact current
green `main` SHA, and confirm the immutable record plus `v1` movement. Do not
roll back to the implementation that predates this contract. Once two
`v1-rollout-*` records exist, exercise the protected rollback between those
records and confirm that re-running an old CI run cannot re-advance the rolled
back SHA. Only then merge consumer branches that adopt new action inputs or
profiles. Turnkey and Outliers remain blocked until their surfaced strict
application findings are fixed; do not weaken CI to merge them.

- Treat a security promotion that reports an outdated `dev` SHA as a manual
  follow-up: another push won the race, so re-run the exact security change
  through current `dev` and promote only after its required CI succeeds.

Agents may prepare commands in `/tmp`; the operator performs ruleset changes,
destructive pushes, rollout activation, and rollback execution.

## Later Renovate Cutover

Do not begin this cutover until the initial `v1` rollout and consumer automation
rollout above are complete. Follow
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
