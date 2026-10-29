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

## Organization-Required Documentation Pilot

The source implementation does not save settings. Use the authorized protected
operator path; an agent must not borrow a human browser session or credential to
perform reserved protection writes. Preserve the existing status, scanning, review,
update, deletion and non-fast-forward requirements throughout.

1. After the human source merge, verify the exact current `.github/main` commit and
   successful approved push `CI`. Bind the workflow selector to that eligible source
   and `.github/workflows/org-baseline.yml`; do not select an unmerged candidate or
   move `v1` to activate this pilot. Capture existing rules and expected-old state.
2. Select only repository and branch identities explicitly enrolled by the qualified
   central source and the task's authorized target scope recorded under this
   procedure. The source catalog
   selects repository ID `1420939261` (`ForgingAlpha/layas-learning-lab-site`) and
   branches `dev` and `main`. Preserve the existing qualified `dev` selector while
   completing the profile's required pilot cases. Select the additional `main`
   target only from a human-merged, green source, and qualify its actual target
   context before reliance. Other repositories or branches need separately approved
   source enrollment and qualification. Exclude the
   defining `.github` repository. Its skipped non-consumer
   job is not a pilot pass; all-skipped required-workflow semantics are unqualified.
   Distinguish workflow names from check-run names: the source workflow is named
   `Organization Baseline`, while its currently skipped check retains the
   unevaluated naming expression and supplies no `CI` result.
   Keep separate product `CI` requirements when an application profile is proposed.
3. Qualify the actual read-only Actions token's effective-rules read and the job
   identity fields. The defining source comes from `toJSON(job)` at step scope.
   Missing fields fail. The public context documentation contains inconsistent
   availability wording; local expression/parser tests are not runtime proof.
4. Read back actual selectors, expected CI producer bindings, strict current-base
   policy, team eligibility and bypass actors. The sampled team configuration
   matches Team `20299307`, one approval, stale dismissal and literal `*`; the
   string alone proves no complete-change coverage. Demonstrate review requirements
   on root and nested documentation paths. A coverage failure returns to preparation
   for a Material revision rather than silently changing the admitted pattern.
5. Observe an already-open PR and an App-created PR executing this exact source
   and consumer head. Newly adding a rule does not trigger an existing PR: use an
   authorized update/reopen. Record check identity and mergeability without an
   agent merge attempt. Confirm the enrolled target's executed job actually reports
   `CI` and satisfies the selected required workflow. The skipped source run does
   not establish target job-name evaluation. Exercise valid pass, deliberate invalid block and repair
   pass, including attempted consumer skip, executable config and application input.
6. Qualify controlled source A to human-reviewed/human-merged B and restoration to
   the previously qualified A. On restoration observe both valid pass and known
   invalid block. Failed, cancelled, skipped or unexecuted runs are not recovery.
   Serialize selector saves against captured expected-old settings and read back
   an outcome-unknown save before retrying. Preserve all preexisting protections.
   If the initial new rule cannot execute and no source A has qualified yet,
   restore the exact captured pre-pilot rule configuration through the authorized
   protected operator path. Verify that readback and every original protection;
   do not remove or waive an existing requirement to manufacture a pass. Reconcile
   an outcome-unknown restoration before retrying. This initial-failure recovery
   is separate from restoration between already qualified sources.
7. Retain exact saved configurations, source/consumer SHAs, API/check identities,
   findings and recovery records. Bind qualification to the profile and shared
   behavior exercised. Before additional enrollment, verify that profile's
   complete required pilot case set from steps 3–6 and its shared dependencies,
   including App-created/already-open triggers, attempted skip/configuration/
   application-input refusal and observed valid-pass/invalid-block source restoration;
   then qualify the new target's identity, current head/base, token access, result
   producers and protections. Do not treat a previous branch's content evidence as
   the new branch's required check result.
8. Review the impact of changes to shared checking sources, selection, permissions,
   runner assumptions and other common inputs; qualify all affected profiles. Retain
   the assessment in the existing task or proposal record, with independent verification
   of Material affected-scope, unrelatedness, no-change and scope-exclusion judgments.
   Bind complete consumer candidate/base inputs and checking-source before/after revisions.
   Unknown impact requires conservative validation or blocks the affected rollout.
   Retire consumer common calls only after independent verification that the central
   gate covers their complete obligations. The actual hosted Rust target remains
   required for Rust and shared behavior affecting it; documents cannot substitute
   for that evidence. One target does not complete the whole pilot, while missing
   unrelated-profile evidence does not block an otherwise qualified profile.
   Transitioning this documentation repository to application code still needs an
   explicit product profile and its meaningful checks; the documentation gate
   intentionally refuses that code until the transition.

The profile admits JSON only at `docs/governing-source-bindings.json`,
`docs/changes/site-foundation/production-preparation/governing-source.json`, and
`docs/changes/site-foundation/production-preparation/retained-inputs.json`. These
are parsed data, not grants or instructions to retrieve their referenced material.
Required inputs are `PROJECT.md`, `AGENTS.md`, `CLAUDE.md` and the governing trio.
The two root instruction links must point literally to the tracked regular
`PROJECT.md`; other links and executable modes are refused. Every input must match
the selected Git blob, and untracked inputs, including ignored files, fail.

## Full Application Profile Entry and Recovery

Use the [owner contract](../actions/ci-org-baseline/README.md) for exact schema and
interfaces. Source qualification alone does not authorize a hosted change.

1. Retain complete consumer tree/base, product-owned required static/test obligations
   (including an attributable explicit no-tests decision when applicable), actual
   runtime assignment, foundation scope and complete current release-route declaration.
   Confirm all tracked Markdown meets the central rules and byte limits; retain any
   additional product rules as selected static checks. Unsupported workspaces, missing
   inputs or unknown scope block that consumer rather than select bootstrap.
2. Inventory actual consumers of CI: security paths/wake events, push requirements,
   CodeQL, release controls, existing result producers and protection. Consumers whose
   local-CI security or required push contracts cannot be preserved retain their caller.
   Do not treat a fixture or a matching team ID as hosted qualification.
   Reusable-workflow jobs, unresolved dynamic names and any independent literal `CI`
   producer (including manual-only workflows) are admission exclusions. Organizational
   probe wrappers must be reconciled before activation rather than silently skipped.
3. Qualify the stable repository/branch and exact legacy workflow path/job/blob under
   the distinct qualification result. Observe valid, invalid and repaired revisions,
   App-created and already-open heads, moving current bases and controlled source
   restoration without weakening existing required CI or human review.
4. Before central-product cutover, capture the exact selectors, old/new producer,
   current retirement head/base and recoverable caller source. Preserve a separately
   required common baseline that refuses stale dual-producer heads, even if either CI
   passes. Keep strict current-base protection and required product CI throughout.
5. Before retirement, recovery restores the captured qualified configuration. After
   retirement, restoring the caller additionally requires its reviewed human-merged
   source change and observed valid-pass/invalid-block behavior. A settings revert or
   failed/cancelled/skipped/missing restored run is not recovery. Reconcile unknown
   effects before retrying.

The current source catalogs are unchanged. Actual Rust backend/lock/tool selection,
consumer route/foundation/review scope and hosted results still need their own evidence.
The existing legacy guard drift and numeric-tool update-coverage gap remain explicit.

The retained Q6 source B is adopted `97a8a94c884f43c039278d117d0d9313d1465ec9`:
its baseline job produces bootstrap `CI`. This candidate moves `CI` to the final
result job and names the common job `Organization Baseline`. Keep the current live
binding unchanged. A future human-merged source and new source activation must
explicitly reconcile that topology with required checks and restoration expectations,
then qualify both check identities on the exact target. Existing Q6 results cannot
prove the candidate topology.

Before any application enrollment, execute the actual pinned mise setup, owned locked
install, fresh clean-tree admission and full Astro static/test sequence on an eligible
locked fixture. Record installation side effects and repair any unsupported output;
mocked command success is insufficient. `MISE_TRUSTED_CONFIG_PATHS` is exported as the
workspace root, while setup executes in the trusted source directory. Runtime version
and projection validation are separate from runtime-owner binary/backend provenance.
Consumer actionlint ignore configuration remains inherited behavior; the independent
Python safety checker still applies in full.

The candidate's trusted baseline metadata job alone declares `checks: read` for the
existing canonical security verifier; product jobs retain their narrower read scope.
Source qualification does not activate a consumer security pipeline or change its
credentials, installation, protections or bindings. Required hosted source CI,
including `shellcheck -S style` for all extracted helpers, remains pending. Bash syntax
and actionlint with ShellCheck disabled do not waive that mandatory gate.
