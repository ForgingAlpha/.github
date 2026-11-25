# Automation Operator Checklist

Source publication does not configure GitHub. Verify the exact repository,
resolved action revision, callers, permissions and hosted state before enabling
an effect. Source on protected main is active at merge. Product deployment and hosted settings retain their own authority.

## Human Merge Boundary

- Require pull requests, designated human-team or applicable code-owner approval of
  the exact current revision, stale-approval dismissal, current-base checks and `CI`
  on protected branches. Keep scanning and merge-shape protections independent.
- Preserve personal human merges for all branch promotions, including separate security
  projections to main, exceptional CI overrides and changes to review or merge authority.
  This includes its protections, requester, proof producer, caller and enrollment.
  Keep merge queues disabled.
- Inventory consumer workflows before merging changed action interfaces.
  Reconcile callers, queued runs and credentials of removed merge automation.
  Remove unused merge credentials only after verifying their consumers; retain
  separately authorized proposal, tag and deployment identities.
- For a repository missing CODEOWNERS, the human reviews the bootstrap's exact
  head and performs the merge, then verifies the merged file and ruleset.
  GitHub reads CODEOWNERS from the base branch; a new file cannot enforce itself.
- Keep private keys in their scoped secret source and protected environment.
  Agents receive no operator SSH key, personal token or human credential.

### Team review for repository-owned CI

The shared policy action reads the [central enrollment](../actions/ci-alphaapps-policy/team-review-repositories.json)
from its own release. This list selects the ownership check in repository-owned CI.
The [organization baseline catalog](../actions/ci-org-baseline/enrollment.json)
separately selects centrally produced CI. Each ownership entry has a canonical
`repository`, its numeric `repository_id` and the destination `branches`
(`dev`, `staging` or `main`). Unlisted repositories and branches use the existing
CODEOWNERS check. Consider disclosure before adding a private repository to this public list.

1. Keep CODEOWNERS in place. The settings owner requires the independent
   [review workflow](../.github/workflows/verify-team-review.yml) from this
   repository's protected main on each selected destination. The verifier also
   supports existing reusable callers. Its PR branch filter suppresses ordinary
   source PR runs from a proposed ref. GitHub ignores that filter for ruleset runs.
   [GitHub ruleset workflow event handling](https://docs.github.com/en/enterprise-cloud@latest/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/troubleshooting-rules#supported-ruleset-workflow-events)
   Verify the effective organization workflow rule reports its exact repository ID, path and
   `refs/heads/main` with no fixed SHA. If GitHub returns another representation,
   retain the existing check until the binding is qualified.
2. Qualify a real PR with the product CI and the required workflow. Verify the
   intended human team, write access, all-file coverage and bypass settings. Prove
   an eligible approval allows the current head and an absent or ineligible approval
   blocks it. Repeat after a changed commit, an empty commit, a base merge and an
   identical-tree rebase. Each new head must require fresh approval. Hold enrollment
   if any case fails. Verify removing or replacing the product caller cannot satisfy
   the independently required workflow. Check the existing job token can read
   contents, PR metadata and effective branch rules. Retarget an open PR between
   protected branches and verify the newly targeted base requires current evidence.
3. Enroll only the qualified branches via a human-reviewed change here. Verify a
   current PR and protected-branch push, then remove the consumer file in its own PR.
   Inventory the consumer's workflow triggers. Only PRs targeting selected branches
   and pushes to those branches use team review. Feature pushes and PRs targeting
   unselected branches still need the file. Unsupported events on a selected branch
   refuse verification. If the head, base or push tip moves, qualify the new
   integration or current push. Replaying an obsolete event cannot refresh it.
   The product action verifies configuration in the caller's job. The separate
   required workflow binds its own source commit, and GitHub enforces human approval.
4. To reverse enrollment, restore and verify the canonical CODEOWNERS file and its
   enforcement first, remove the central entry second, and retire the required
   workflow rule last. Keep the published verifier available at its qualified path
   until every rule requiring it has been retired or migrated.

### Native auto-merge enrollment

The target repository’s owner selects its ordinary paths and security-source policy.
A human personally reviews and merges that enrollment into the protected target branch.
The two shared workflows read `.github/native-auto-merge.json` from the verified Git
tree at the exact current **base** commit. A proposed configuration cannot enroll its
own PR. No target is enrolled by the following illustration. The zero IDs deliberately
fail validation.

```json
{
  "repository_id": 0,
  "branch": "dev",
  "requester_id": 0,
  "proof_app_id": 0,
  "proof_context": "Exact human approval",
  "ruleset_qualification": {"sha256": "<owner-verified fingerprint>", "observed_at": "<UTC inspection time>"},
  "ordinary_paths": ["docs/guides/**"],
  "security_sources": false
}
```

Use the target’s numeric repository ID, the requester bot’s numeric **user ID**
and the independent proof producer’s numeric **App ID**. The branch is `dev` or `main`.
For ordinary task PRs every changed path, including both sides of a rename, must be an
admitted exact path or fall under an admitted `directory/**`. Hidden paths, workflow
and control directories, README and instruction files, and the other reserved names in
[the enrollment reader](../actions/native-auto-merge/enrollment.py) stay outside that
path selection. Enable `security_sources` only on a separately qualified protected
default branch where the existing trusted classifier and proof/observer can establish
all REQ-013 and REQ-014 obligations.

Use the protected default branch’s thin `.github/workflows/native-merge.yml` caller.
Grant only the reads required by the called jobs. The caller routes these events to
protected shared definitions and supplies no PR checkout, cache or artifacts.

| Consumer event | Shared workflow called by the fixed caller |
| --- | --- |
| `pull_request_target` on `opened` or `ready_for_review`; or a completed successful `AlphaApps Security Classification` check from App `4618077` | `ForgingAlpha/.github/.github/workflows/request-auto-merge.yml@main` |
| `workflow_run` on completion of the named unprivileged PR or PR-review signal workflows | `ForgingAlpha/.github/.github/workflows/verify-native-merge-approval.yml@main` |

Wake the proof on review submission or dismissal, head or base changes, draft/ready
transitions, and native enable or disable events even after CI finishes. A signal only
identifies the affected same-repository PRs and heads. An ambiguous shared head must
supersede an earlier green proof for every affected enrolled PR. Verify that invalidation
and restoration under concurrent hosted events before requiring the check. Keep product
CI independent so either approval or CI can finish first. When a check completes in the
merge second, the observer requires the GitHub rule evaluation for that actual merge
to name the successful check run and App. An unreadable or truncated evaluation leaves
the outcome unverified. [GitHub rule-suite metadata](https://docs.github.com/en/rest/repos/rule-suites#get-a-repository-rule-suite)

| Branch-restricted environment | Dedicated identity and inputs |
| --- | --- |
| `native-merge-request` | Requester App with variable `NATIVE_MERGE_REQUEST_CLIENT_ID` and secret `NATIVE_MERGE_REQUEST_PRIVATE_KEY` |
| `native-merge-proof` | Independent check producer with variable `NATIVE_MERGE_PROOF_CLIENT_ID` and secret `NATIVE_MERGE_PROOF_PRIVATE_KEY` |

Before separately authorizing activation, verify both installations, reachable workflow
sources and every credential access path. The requester needs GitHub write scopes that
can authorize operations beyond requesting auto-merge. The protected code, credential
isolation and actual rules must jointly prevent agent access, direct merges, protected-ref
writes, self-approval and bypass. Retain each identity’s actual grant and effective
organization, repository and inherited rules. Unavailable bypass or actor data leaves the
route unqualified.

The settings owner qualifies the branch under their own authority.

1. From the reviewed shared checkout, obtain the visible fingerprint and applicable
   ruleset IDs with `python3 -I -B actions/native-auto-merge/request.py ruleset-snapshot ForgingAlpha/REPO dev`
   (or `main`). The command uses the scoped read connection. It includes update
   restrictions, safety rules and inherited enterprise rules. It performs no mutation.
2. In the owning settings for **each** ID, inspect full actor lists, bypass modes,
   selectors, update admission and actual effective grants. Verify that exactly the
   authorized human exceptions survive, that neither App can bypass review, proof,
   CI or security, and that the requester can request native completion without
   permission to merge directly. Retain that inspection in the authorized settings
   record. GitHub omits bypass actors from a repository REST response when the
   reader lacks ruleset write access. A missing list supplies no evidence.
   [GitHub ruleset visibility](https://docs.github.com/en/rest/repos/rules#get-a-repository-ruleset)
3. Qualify a bypass-only change on a separately authorized representative ruleset
   for each applicable ownership layer. Verify that the read-only fingerprint changes
   when adding, changing or removing a bypass without changing visible rules. Verify
   both the prior and restored actor state with the authorized owner. If a layer or
   edit path cannot be observed or tested, keep the branch on the human procedure.
4. Fingerprint the target again after the complete owner inspection. Both reads
   must agree. Record the matching `sha256` and actual inspection time in
   `observed_at` (UTC with a trailing `Z`, after the latest update’s whole second).
   The enrollment PR binds them to the repository and branch. Changed or incomplete
   rules require fresh qualification. Before any ruleset, App grant or protection
   change, stop requests and have the owner disarm and reconcile outstanding requests
   while the existing protections still hold. Grant and classic branch-protection
   changes fall outside this ruleset fingerprint. For an armed PR the proof producer
   checks the fingerprint again. GitHub must still enforce protection when it merges.

Require strict current-base `CI` from the expected Actions producer and strict
`Exact human approval` from the enrolled proof App. Verify the designated human team,
scanning and all other required gates without a bypass for either identity. Exercise
same-diff pushes by a writer, a withdrawn review, retargeting, changed integration,
and two PRs sharing a head. Show that an already-green check or an externally armed
request cannot complete a manual-only PR. Exercise expired or lost responses, manual
disarm, and the real human path on excluded PRs. A skipped requester, a failed proof,
or a blocked native path does not establish that a human can merge. Record check
producer and subject, review, requester, actual merger and resulting content separately.
Keep failures and unqualified cases visible. Source preparation supplies no hosted settings,
App setup, consumer caller or activation.

After GitHub reports an ordinary native merge, use the protected shared source and the
target’s scoped read credential. Substitute the actual repository, PR number and merge
commit shown on that PR, then retain the verified JSON with the proposal record.

```bash
python3 -I -B actions/native-auto-merge/observe.py OWNER/REPO PR_NUMBER MERGE_COMMIT
```

A missing receipt or a disagreement between the PR, parent commits, reviewed tree
and recorded merger leaves delivery unverified. Use the security-source observer
for a Dependabot security PR.

## Shared Checks, Main Source And Recovery

- Require complete exact-head CI, coherent candidate and affected-consumer checks,
  and authorized human review before the protected source merge. Main membership
  makes the shared source active. Keep post-merge failures visible; there is no
  tag promotion, recurring source repin or post-merge source acceptance.
- Preserve all external Action SHA pins, license/vulnerability checks and exact
  runtime catalogs and locks. Internal callers use canonical
  `ForgingAlpha/.github` spelling with literal `@main`. Inventory and migrate thin
  consumer references through their own reviewed PRs; local inventory does not
  prove hosted organization coverage or completed migration.
- Retain defining workflow SHA or native per-job Action acquisition SHA, consumer
  revision, source fingerprints and outcome. A latest-main provenance lookup is
  dependency-source evidence, not an executed-source receipt. Qualify actual
  dependency-review main record shape and deployed runner/cache behavior before
  claiming universal composite coherence. Do not validate a local/SHA candidate
  parent against nested live-main helpers as if they were the same candidate.
- Confirm dependency graph, dependency review and the required Code Security
  entitlement in private consumers. Qualify actual PR dependency output before
  requiring the gate. Unknown records and API failures refuse without tag fallback.
- Recover shared source with a checked corrective or revert PR, exact-head human
  approval and protected merge into main under REQ-024. Retain before/after commits, affected runs
  and outcomes. A whole-policy revert can restore withdrawn catalog approvals;
  disclose that effect and choose a forward fix when withdrawal must persist.
- Retired v1 promotion/rollback workflows do not write tags or select fallback
  source. Preserve historical refs and evidence; source retirement grants no tag
  deletion/movement, credential change or protection write authority.
- Verify the repository ID and its adopted route under [REQ-027](../README.md#req-027---uniform-proposal-admission).
  Exercise task-to-dev and the exact website dev-to-main release. For a paid
  production app qualify the release claim, frozen dev snapshot, staging task,
  current staged candidate, isolated environment and staging-to-main release.
  Pending launch, keep ordinary development on dev. Shared tooling retains its
  main-only task path. Check refusal for an unknown identity, an undeclared
  target and an attempted paid-release shortcut. Preserve push/security/check
  consumers, exact human review and applicable protected merge controls when qualifying a route.

## Security Classification And Projection

- Resolve the protected security source target under REQ-013 and qualify its
  actual caller, proof and observation path before enrollment. The governing
  direct-main path does not establish an implemented or qualified direct-source
  wrapper/observer; unavailable prerequisites stop the affected security flow.
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
  Require classification before the protected source merge; an identical retry
  preserves its completion time and cannot manufacture pre-merge evidence.
- The source merge must have ordered parents `[classified base, head]`
  and the classified head tree. Record the actual merge actor and time. A native
  source merge additionally needs a qualified arming identity and the designated
  human’s effective review of that PR and exact head. Classification and required exact-head
  CI/CodeQL precede that merge. Later unrelated `dev` movement is allowed for a
  separate-dev source.

### Separate-dev source and production projection

These additional steps apply only when the classified source merges into dev.

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
  Where the product requires deployment, verify that the independently triggered
  deployment reports that same revision;
  post-merge observation is not a gate on a concurrently starting deployment.

### Direct-main source observation

- An eligible default-main security source is the production proposal; require
  its source classification, exact-patch proof, strict current-base CI/CodeQL,
  exact human approval and an attributed source merge under REQ-024. Do not create a second source merge,
  projection PR or projection attestation.
- Qualify a read-only observer that binds the actual main push, merged source PR
  and current main ref, then re-proves the source classification and its time,
  classified base/head, actual merge actor, ordered parents, source-head tree and official
  advisory association. Do not manufacture missing classification after merge or
  call the projection-only observer with invented attestation evidence.
- Where the product requires deployment, verify its exact main merge revision
  and tree. Deployment may start concurrently with observation; observation adds
  no shared-source activation gate.

### Failure handling for both paths

- On conflicting preimages, incomplete evidence, failed checks or deployment
  failure, stop the affected operation visibly. Do not promote unrelated `dev`
  work, regenerate locks in a privileged job, or silently roll back to a
  vulnerable revision.

## Dependency Proposal Enrollment

- Confirm the ordinary updater target against REQ-027, the current default/update
  coupling and the separate security target. Reconcile conflicts through the
  owning qualified transition; this checklist chooses no new default branch.
  Confirm required exact human review and protected merge gates. Verify that the
  organization's Mend Renovate App installation can access the repository.
- Review the Mend onboarding PR against the observed default branch. Check the
  root `renovate.json` against the [minimal consumer example](../README.md#dependency-and-security-flow).
  Confirm enrollment through the reviewed config and check which managers Mend
  discovers. An organization `renovate-config`
  repository with a `default.json` can take precedence during discovery. Verify
  which preset Mend actually selected. Existing consumers may retain the
  `renovate-weekly` alias, an explicit matching base, and reviewed package splits.
  Keep the local update-policy file for an assigned runtime profile. Reconcile
  existing updater PRs at cutover so each dependency has one ordinary updater.
- After the shared preset reaches protected `main`, inspect the effective config
  and run history in Mend. Verify both preset names resolve to the same weekly
  policy. Record the target, run times, pending-age decisions, batch branch and PRs
  across two separate weekly windows on the rollout pilot. Compare the observed
  behavior with [REQ-012](../README.md#req-012---normal-update-cooldown).
  Verify eligible updates join the open batch during Tuesday 00:00–06:00 in
  `America/New_York` and automatic batch updates wait outside that window.
  Review the batch after 06:00. Merging earlier can lead to a second batch PR.
  Check that majors and initial pins stay outside the group. Confirm proposal
  limits, runtime and first-party Action exclusions, and disabled Renovate
  `automerge` and `platformAutomerge`. Qualify a protected native merge request
  separately under REQ-024.
- For each new maintained repository at setup and each existing repository at
  cutover, verify in GitHub that the dependency graph, Dependabot alerts and
  security updates are enabled. Confirm required CI detects exactly one update
  owner for every dependency surface. An organization security
  configuration can apply these settings to selected existing repositories.
  Setting a default for newly created repositories is a separate administrator
  decision. Check supported manifests on the protected default branch, the
  security PR target and the production route. Each local Dependabot block
  must set `open-pull-requests-limit: 0` and omit `target-branch`. Verify
  coverage for each ecosystem and directory, including documented exceptions.
- When a new repository gains a package, image or externally versioned Action,
  use the [enrollment templates](../templates/dependabot/README.md) to configure its ecosystems and manifest paths.
- Runtime profile enrollment validates the exact central assignment and locked
  consumer projection. Do not claim automatic runtime projection writes until
  the constrained resolver, writer and rollout gates are qualified. Record
  temporary exceptions with scope, owner, approval revision and expiry.

Agents prepare reviewable source and commands. Humans retain exact PR approval, personal merges for the manual lanes,
credential and ruleset changes, and consumer settings transitions. Source recovery follows REQ-007.

## Organization-Required Documentation Pilot

The source implementation does not save settings. Use the authorized protected
operator path; an agent must not borrow a human browser session or credential to
perform reserved protection writes. Preserve the existing status, scanning, review,
update, deletion and non-fast-forward requirements throughout.

1. Verify the exact current protected `.github/main` source and pre-merge check/
   review evidence. For the one authorized selector transition, capture and compare
   the complete current rule against expected-old state. Replace only its shared
   workflow source selector with `main`, preserving workflow path, repository and
   branch selectors, CI App binding, strictness, bypasses, creation flags and all
   inherited controls. Stop on stale or unknown state; read back an outcome-unknown
   save before any retry. Verify the full saved rule and effective dev/main rules.
   Future protected main merges do not require selector repins or source activation.
2. Select only repositories and branches covered by both the approved source
   enrollment and the operator task’s authorized target scope.
   The current catalog selects repository ID `1420939261`
   (`ForgingAlpha/layaslearninglab-site`) on `dev` alone. Keep its qualified
   `dev` selector. Before selecting `main` for a first documentation-only promotion,
   verify the site's exact converted `dev`, empty sole-root `main`, approved
   dual-branch README scopes, direct route and reviewed dual-branch enrollment
   in protected shared source. Qualify the effective team review on target `main`,
   current-base CI, scanning and the required workflow producer. Qualify a personal
   merge method that preserves the reviewed tree and permits the next ordinary
   release. A merge with the empty `main` and reviewed `dev` as its two ordered
   parents preserves both tree and ancestry. Record the permitted method, and
   verify the actual parents and tree after the human merge. Other repositories
   and branches need their own approved enrollment and qualification. Exclude the
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
6. Qualify source recovery through a checked human-reviewed corrective or revert
   PR and protected merge into main, recording the new exact commit and affected valid
   pass and known-invalid block outcomes. Failed, cancelled, skipped or unexecuted
   runs are not recovery. Keep main as the active selector; do not repin a historical
   source or move a tag. If the initial consumer settings transition fails, restore
   its exact captured pre-transition configuration through the separately authorized
   human path. Compare expected-old state, reconcile an outcome-unknown save before
   retrying, and read back every original protection. Settings restoration is separate
   from shared source recovery and cannot waive existing required checks.
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
The legacy layout requires the standalone governing trio, tracked `PROJECT.md`
and the two root instruction links to `PROJECT.md`. Both links must point
literally to that tracked regular file. The converted layout requires the four-section root README, its
source manifest and both native instruction entries. The regular `AGENTS.md`
must contain the approved README pointer. `CLAUDE.md` may contain that same
pointer or link literally to `AGENTS.md`. Competing `PROJECT.md`, other links and
executable modes fail admission for the converted layout. Every input must match
the selected Git blob, and untracked inputs, including ignored files, fail.

## Full Application Profile Entry and Recovery

Use the [owner contract](../actions/ci-org-baseline/README.md) for exact schema and
interfaces. Source qualification alone does not authorize a hosted change.

1. Retain complete consumer tree/base, product-owned required static/test obligations
   (including an attributable explicit no-tests decision when applicable), actual
   runtime assignment and complete current release-route declaration.
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
   retirement, restoring the caller additionally requires its reviewed and merged
   source change and observed valid-pass/invalid-block behavior. A settings revert or
   failed/cancelled/skipped/missing restored run is not recovery. Reconcile unknown
   effects before retrying.

Runtime assignments retain their current catalog. Actual Rust backend/lock/tool selection,
consumer route/review scope and hosted results still need their own evidence.
The release-owner evidence needed for paid staging and the numeric-tool update-coverage gap remain explicit.

The historical retained Q6 source B was adopted `97a8a94c884f43c039278d117d0d9313d1465ec9`:
its baseline job produces bootstrap `CI`. This candidate moves `CI` to the final
result job and names the common job `Organization Baseline`. The one authorized consumer selector transition must reconcile
that topology with required checks and restoration expectations, then qualify both
check identities on the exact target. Source on main is already active after human
merge; consumer settings qualification is a separate obligation. Existing Q6 results cannot
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
