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
  The released control-plane policy pins its public App ID; do not duplicate or
  override that identity in a consumer secret, variable, or workflow input.
  Store only its private key as the organization Dependabot secret and the
  organization Actions secret `ALPHAAPPS_AUTOMATION_PRIVATE_KEY`; post-merge
  projection workflows run in the Actions context and require that second store.
- Create the `security-autopromote` label in every participating repository,
  including `ForgingAlpha/.github` and each application repository.
- Treat the existing whole-branch promotion workflow and `prod-*` tags as a
  legacy caller contract only. Do not enroll a new security flow in that
  workflow. Retain its protection until any verified live callers are migrated,
  then remove the workflow, tags, and instructions through a separate reviewed
  retirement.
- Confirm the legacy release writer no longer exists on the merged branch.

Approved auto-activation does not depend on the repository's `Allow auto-merge`
setting. In every enrolled repository, create a
`release-automation` environment, restrict its deployment branches to that
repository's exact default branch, add no required reviewer, and store
`FORGINGALPHA_RELEASE_APP_CLIENT_ID` as an environment variable and
`FORGINGALPHA_RELEASE_APP_PRIVATE_KEY` as an environment secret. A pull-request
merge ref must not satisfy that deployment-branch rule.
The protected release App must have only repository metadata read, contents
write, and pull-request write permission. Token creation must remain scoped to
the current repository. The agent/authoring App must not receive the release
credential or a ruleset bypass.

For every enrolled persistent branch, require the authorized human's code-owner
review, dismiss stale approvals when the pull-request diff or merge base
changes, require the approved `CI` check, and require the branch to be current
with its target before merge. Put review, code-owner, latest-push, thread,
status-check, scanning, deletion, and non-fast-forward protections in rulesets
where `forgingalpha-release` has no bypass. Put `Restrict updates` alone in a
separate updater-authority ruleset where the operator retains emergency
authority and `forgingalpha-release` has pull-request-only bypass. Ruleset-local
bypass keeps the App able to update the protected ref only through GitHub's
pull-request merge endpoint without letting it bypass any quality or
human-authority rule. Prohibit direct pushes and administrative merge bypasses
in the protected workflow.

The auto-activation path intentionally follows GitHub's privilege-separation
pattern. `approval-signal.yml` runs in the pull-request context with no token
permissions, secrets, checkout, or executable pull-request content. Its
completion triggers `approved-auto-activation.yml` through `workflow_run`, so
the repository-owned privileged caller is loaded from the default branch. That
normal job statically owns the default-branch-only `release-automation`
environment and passes its protected release credential directly to the
centrally versioned `approved-automerge` composite action. This keeps the
environment boundary in the caller repository, blocks a pull-request workflow
from requesting the key even for a same-repository task branch, and preserves
one shared activation implementation without copying it into consumers.
The protected workflow treats the approval run's head SHA as GitHub-authentic
event data, not as authorization. Before minting a write-capable token, it uses
GitHub's workflow-run pull-request pointer first, validates that pointer against
the live open same-repository pull request and exact signal head, and fails
closed on malformed or multiple pointers. When GitHub supplies no pointer, it
falls back to requiring one unique live commit association. Neither resolution
path is authorization. It then re-queries GitHub and requires the authorized
human's latest authoritative review to be `APPROVED` on the current full head
SHA before it calls GitHub's synchronous REST pull-request merge endpoint as the release App.
The request supplies that exact SHA and the governed merge method; it uses
neither deferred auto-merge nor an administrative bypass. GitHub atomically
rejects it if an independent review, check, scanning, merge-base, or ref rule
is no longer satisfied. GitHub rulesets, not a parallel custom state machine,
remain responsible for those protections.
The environment grants secret access without recording a deployment because
activation is a merge-control operation, not an environment deployment.

Roll out `approval-signal.yml` and a repository-owned
`approved-auto-activation.yml` caller to each consumer with that repository's
complete persistent-branch list. Each caller must be a normal job with exact
read-only pull-request permission, a static `release-automation` environment,
and one invocation of
`ForgingAlpha/.github/actions/approved-automerge@v1`. Do not copy the composite
implementation into consumers or pass its credential through a reusable
workflow. The first
workflow pull request is a manual bootstrap because its default branch does not
yet contain the privileged `workflow_run` caller. After it merges, use a
harmless same-repository probe to prove that an unchanged approved revision is
merged only by `forgingalpha-release`, while a draft, changed revision, stale or
dismissed approval, fork head, and undeclared target remain unmerged. Do not add
a merge queue until branch traffic justifies its additional `merge_group` CI
surface.

For the `.github` control-plane bootstrap, manually merge the reviewed repair,
wait for exact-main `CI`, and advance `v1` to that exact green revision before
retesting activation. The caller deliberately references the governed `@v1`
action rather than executing an unreleased implementation from a task branch.

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

- For exact security projection, confirm the writer App can create only a task
  branch and pull request and has no persistent-branch bypass. Store no
  activation credential in the writer workflow. Confirm its public App ID is
  the exact source-classifier and writer identity pinned by the released
  control-plane policy; do not add a consumer variable or workflow input that
  can select a different automation App.
- Before the first projection, upgrade source classification so its trusted
  exact-head check also binds the source base and complete associated GHSA set;
  the current head-only classification is not production-projection authority.
- Create a `security-activation` environment restricted to the repository's
  exact default branch. Store only the dedicated security activator's client ID
  variable and private-key secret there; the activator has metadata read,
  contents write, and pull-request write, but no vulnerability-alert, workflow,
  check, status, deployment, or direct-push authority. The pre-token
  proof uses a separately minted no-bypass automation App token narrowed to
  metadata, pull-request, check, content, Actions, and vulnerability-alert read
  access so the exact CI workflow path and run—not only a check name—are proven;
  the merge-capable token is unavailable until that proof passes.
- Split rulesets before unattended activation: keep strict pinned CI, CodeQL,
  current-base, merge shape, deletion, and non-fast-forward rules in a no-bypass
  requirements set; put human review in its own set with only the security
  activator's pull-request bypass; put UPDATE alone in an authority set with the
  same pull-request-only bypass. Give neither the projector nor Dependabot any
  bypass.
- Verify the production projection records and then independently re-proves the
  exact source PR, base/head blobs and modes, App-owned classification, App
  merge, complete GHSA set, production base, projected head, and result tree.
  Labels and pull-request prose are never authority.
- Keep the first `alphaapps-site` projection in observation mode. Require Leo's
  existing exact-head approval for that projected `main` pull request, observe
  the normal production deployment, and verify the resulting `main` and
  deployed revision before installing unattended review bypass.
- For an outdated source or production base, divergent manifest or lock,
  conflict, concurrent lock update, unsupported path, incomplete API response,
  failed trusted check, or deployment failure, stop visibly. Rebuild only from
  the new production base after the exact preimages still match. Never promote
  the whole `dev` range, regenerate a lock in the privileged workflow, or
  automatically roll back to a vulnerable revision.

Agents may prepare commands in `/tmp`; the operator performs ruleset changes,
destructive pushes, rollout activation, and rollback execution.

## Renovate Canary Activation

Follow
[`plans/renovate-normal-dependency-automation.md`](plans/renovate-normal-dependency-automation.md)
in order.

- Confirm `dev` is the default branch in every participating application
  repository and that protected `dev` requires pull requests and `CI` without
  automation bypass.
- After the updater-ownership gate, central preset, runtime catalog, and
  `alphaapps-site` consumer projection PR are green but still unmerged, install
  the free hosted Renovate GitHub App on only that site canary. App installation
  is a separate sensitive operator action. Inspect Renovate's generated
  onboarding PR and job log only for App access, intended manager discovery,
  and the default `dev` branch. Close that generated onboarding PR without
  merging its competing config; then merge the already-reviewed canonical
  consumer PR to perform the manual onboarding. Inspect the first hosted job
  after that merge for the resolved central preset, cooldowns, disabled
  vulnerability/mise lanes, and the exact `ForgingAlpha/.github` package
  identity excluded from GitHub Actions updates.
- Keep Renovate vulnerability remediation disabled and retain GitHub Dependabot
  alerts and security updates.
- For each repository, convert Dependabot to security-only in the same protected
  change that flips its declared normal-update owner to active Renovate. The
  coverage gate must prove the complete destination mode on that exact head.
- Keep the Renovate App out of every ruleset bypass list during proposal-only
  canarying. Before unattended merges, create the separately scoped updater
  identity and decompose review authority from required CI and CodeQL so the
  updater can bypass only the review rule for an already classified normal
  update. Never grant it a bypass on quality rules.
- Prove patch auto-merge on one site canary first. Expand to minor, major,
  runtime, and control-plane automation only after the plan's corresponding
  go/no-go evidence passes.
- Do not enroll obsolete deployment integrations in Renovate; remove them.

### Runtime Profile Cutover

- The initial Node canary may activate the catalog and projection validator in
  read-only mode while direct Renovate mise updates and generic lock maintenance
  remain disabled. The consumer's exact `mise.toml`/`mise.lock` remains the
  executable source, but required CI proves it is the assigned central tuple.
- Do not claim automated runtime updates until the constrained projection
  writer is active. Do not hand-edit a consumer version as an independent
  authority.
- Require every impacted consumer to validate the same exact candidate profile
  and its locked projection before declaring the runtime rollout complete.
- Record any temporary deviation centrally with exact scope, accountable owner,
  approval revision, and expiration.
