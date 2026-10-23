# Automation Operator Checklist

Source publication does not configure GitHub. Verify the exact repository,
released action revision, callers, permissions and hosted state before enabling
an effect. Keep deployment and tag-rollout authority separate from PR merges.

## Human Merge Boundary

- Require pull requests, applicable authorized-human code-owner approval of the
  exact current revision, stale-approval dismissal, current-base checks and `CI`
  on protected branches. Keep scanning and merge-shape protections independent.
- An applicable authorized human executes every PR merge. Disable repository
  auto-merge and merge queues; cancel previously queued merges. No bot, App or
  workflow receives a persistent-branch update or merge bypass.
- Inventory consumer workflows before releasing changed action interfaces.
  Reconcile callers, queued runs and credentials of removed merge automation.
  Remove unused merge credentials only after verifying their consumers; retain
  separately authorized proposal, tag and deployment identities.
- For a repository missing CODEOWNERS, the human reviews the bootstrap's exact
  head and performs the merge, then verifies the merged file and ruleset.
  GitHub reads CODEOWNERS from the base branch; a new file cannot enforce itself.
- Keep private keys in their scoped secret source and protected environment.
  Agents receive no operator SSH key, personal token or human credential.
- For the main-only shared repositories, inspect the complete main protection and
  inherited rules with the human settings owner. Allow only authorized human push
  actors; enforce required PRs, exact human approval, trusted CI and applicable
  scanning without a quality bypass. Verify that Agent and release/updater identities
  cannot update main through an ordinary merge after approval. Omitted actor lists
  and HTTP 403 are unknown, not empty. Replace a routine-bypass update restriction
  only after equivalent actor denial and every existing quality requirement are verified.
- Reconcile Container Foundation's main/dev commits, pending proposals, default branch,
  CI and updater targets before retiring dev. Preserve approved export commits and
  consumer locks. Its main-only selection does not add a numbered-release process
  or silently update an application's imported payload.

Read-only inspection helper: the human settings owner runs
`python3 -I tools/main-protection-read.py` without sudo using their existing `gh`
session. It checks the fixed three repository IDs and writes a private report under
`/tmp/alphaapps-shared-main-read-*/REPORT.json`. It applies no settings and never
certifies Agent exclusion; unavailable reads and omitted bypass actors remain unknown.

## Shared Checks And Rollout

- Confirm dependency graph, dependency review and the required Code Security
  entitlement in private consumers. Qualify the gate with actual PR dependency
  output before requiring it.
- Keep `V1_ROLLOUT_ENABLED` absent or false until the exact candidate and release
  controls are qualified. Verify merged-commit `CI`, current `main`, and the
  applicable version-coherent consumer gate before enabling `v1` movement.
- Protect `v1`, `v1-rollout-*` and `v1-rollback-*` against unauthorized creation,
  update and deletion. Grant tag writes only to the scoped rollout identity
  and operator; this grants no persistent-branch update authority.
- Create and verify the protected `v1-rollback` environment before use. GitHub
  must not auto-create an unprotected environment on first execution.
- Observe atomic leased `v1` movement with its immutable rollout record. Exercise
  rollback only between eligible recorded rollouts; verify stale CI reruns
  cannot re-advance a superseded commit. Retain the prior qualified deployment
  until the candidate's consumer checks pass.

## Security Classification And Projection

- Install the security App whose public ID is pinned by the released policy.
  Consumers cannot select a different trust identity. Give it no branch merge
  bypass. Keep its key out of general agent launchers and unrelated workflows.
- Install the default-branch caller for `security-patch-classification`. Its
  unprivileged preflight binds the exact trusted CI workflow/run/repository and
  Dependabot PR/base/head. It receives read access only, with no environment,
  secret, checkout, cache or PR artifact. Preflight is not full GHSA classification.
- In the separate branch-restricted security environment, grant classification
  only the required metadata, Actions, content, PR and alert reads plus check
  writes. Re-prove the complete official GHSA set and exact allowed patch before
  writing. Serialize by repository and source head without cancellation.
  Require classification before the human source merge; an identical retry
  preserves its completion time and cannot manufacture pre-merge evidence.
- The human source merge must have ordered parents `[classified base, head]`
  and the classified head tree. Record its observed actor and time; those fields
  alone do not prove authorization. Later unrelated `dev` movement is allowed.
- Enroll `security-patch-projection` with only the nonpersistent-branch, check and
  draft-PR writes it needs. Serialize by repository, target and lock path.
  Verify exact source preimages, approved manifest/lock paths, complete file
  enumeration, fixed-App attestation and sole-lock ownership.
- Exercise lost-response retries for ref, check and draft-PR creation. Only
  exact existing state may be adopted. Wrong or missing objects, moved bases,
  duplicate/conflicting checks, tombstoned PRs and competing lock proposals
  must fail without update, deletion or duplicate creation.
- Run `security-patch-verification` with a read-only security token. Require
  fresh strict target CI, trusted CodeQL, complete provenance, the expected
  tree and exact synthetic merge parents. Reject armed native auto-merge.
  Draft creation precedes these review gates; it does not need approval or
  checks that exist only after creation.
- An applicable authorized human approves and merges the exact production
  proposal. A read-only push observer calls `verify-post-merge` with its PR and
  actual merge SHA, deriving expected parents/tree from the trusted attestation.
  Verify the independently triggered deployment reports that same revision;
  post-merge observation is not a gate on a concurrently starting deployment.
- On conflicting preimages, incomplete evidence, failed checks or deployment
  failure, stop the affected operation visibly. Do not promote unrelated `dev`
  work, regenerate locks in a privileged job, or silently roll back to a
  vulnerable revision.

## Dependency Proposal Enrollment

- Confirm the intended default/update branch and required human merge gates.
  Install the hosted Renovate App only in explicitly enrolled repositories.
- Inspect onboarding for App access and manager discovery. Use the reviewed
  canonical consumer config, extending only the central preset with its exact
  base branch; avoid a competing generated config. Change sole update ownership
  with no overlap or unmanaged interval.
- Inspect a hosted job for the resolved preset, disabled bot/platform auto-merge,
  exact 3/7/30-day cooldowns, proposal limits, disabled vulnerability/mise/Node
  engine lanes and first-party Action exclusion. An unrestricted run window
  does not prove daily execution; verify actual hosted runs.
- Keep Dependabot security remediation enabled with normal-update capacity zero
  after Renovate enrollment. Verify every dependency surface has one owner.
- Runtime profile enrollment validates the exact central assignment and locked
  consumer projection. Do not claim automatic runtime projection writes until
  the constrained resolver, writer and rollout gates are qualified. Record
  temporary exceptions with scope, owner, approval revision and expiry.

Agents prepare reviewable source and commands. Humans perform PR merges,
credential and ruleset changes, rollout enablement and protected rollback.
