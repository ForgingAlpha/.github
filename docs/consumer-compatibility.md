# Consumer compatibility fixtures

Shared changes need evidence from affected consumers before merge. Shared checks
belong here; each consumer retains its product requirements, commands and tests.

`scripts/qualify_foundation.py` generates a disposable Foundation PR workflow from
an exact revision of Foundation's own CI workflow. It reads Git objects, preserves
the consumer's commands and final evaluator, and substitutes seven shared Action
references with one complete, verified candidate checkout. It adds source checks
and a distinct **Shared candidate compatibility** result. Foundation's normal
workflow remains unchanged.

The adapter supports Foundation's current single-job workflow contract. Changed
step order, conditions, inherited execution settings, extra stages, ambiguous YAML
or nested first-party Action references require a reviewed adapter update. It
refuses these inputs instead of guessing how to translate them. Public tests use
synthetic commands; actual consumer workflows and logs stay in their owning repo.

The generator uses Python and the existing shared CI PyYAML dependency. Supply
exact commit and tree identities from verified source bindings:

```bash
python3 -I -B scripts/qualify_foundation.py \
  --consumer-repo "$consumer_checkout" \
  --consumer-commit "$consumer_commit" --consumer-tree "$consumer_tree" \
  --candidate-repo "$shared_checkout" \
  --candidate-commit "$shared_commit" --candidate-tree "$shared_tree" \
  --branch "$fixture_branch" --output "$new_fixture_file"
```

The output path must not exist. The fixture branch must start with `test/`.
Publish the generated file as `.github/workflows/shared-candidate.yml` on a
disposable same-repository Foundation PR to `dev`. Never merge the fixture.
The tool itself performs no network operations, publication or credential setup.

Each acquisition verifies the shared commit, tree, actual files and repository.
The candidate is reacquired after the consumer's root checkout and removed before
product tests require a clean tree. After those tests, the same candidate is restored
and verified so GitHub can load composite Action files for its post-job hooks.
The overall native job must succeed, including those hooks; the final evaluator
alone is insufficient evidence. Empty read-only Python cache directories prevent
isolated Python imports from changing the candidate. This is source hygiene, not
an execution sandbox. Candidate jobs must remain read-only and receive no
orchestration credentials.

A successful fixture proves compatibility only for its exact recorded inputs and
observed run. Automatic triggering, stale-result reconciliation and aggregation into
shared CI require a separately qualified trusted integration. This generator alone
does not provide those effects or merge authority.

## Standards rejection and consumer remediation

A correct rule rejection can expose a consumer violation. Diagnose it against
the exact rule, consumer configuration and inputs. The responsible shared-CI or
consumer maintainer retains that evidence in the owning change record, with
private material kept in consumer custody. Fix the consumer when it violates
the selected contract; fix the checker when it misapplies that contract.
Unknown causes remain unresolved. Diagnosis never changes the required result.

The local composed Markdown cases bind synthetic consumer configuration that
enables MD001. The consumer owns this configuration; the shared wrapper owns
tool execution and outcome propagation. These cases do not establish universal
central Markdown rule ownership or resolve current policy about consumer opt-outs.

A passing negative assertion leaves the underlying consumer workflow failed.
The remediated example uses a different consumer revision conforming to the same
selected rule. Both adopted-source normal CI and candidate CI remain required.
This example does not resolve a rule replacement for which no consumer revision
can satisfy both. Such a case needs its owning resolution, not an exception that
makes failed evidence green.

The cases exercise actual wrapper, B1 evaluator and controller functions. Their
provider metadata is synthetic and public writes are captured. They establish
local composition and changed-plan behavior, not a native negative Markdown run
or automatic private execution.

## Trusted controller

`scripts/consumer_compatibility.py` and the reusable
`.github/workflows/consumer-compatibility-controller.yml` prepare the Foundation
connection. The workflow has only a reusable-call entrypoint. Its private caller,
standing authority, environment, two App installations and mandatory result must
be set up and qualified separately before use. This source does not activate a
schedule or enroll additional repositories.

The controller verifies existing exact-head human review, generates the original
adapter's fixture, and observes both native workflows. It publishes one distinct
`Consumer compatibility` result from the reporting App. It never replaces the
existing `CI` check. Current passing plans reuse their existing runs; unknown
publication outcomes are reconciled by exact native identities before another
write. Obsolete fixtures are closed only after full custody checks and are never
merged or force-pushed. Failed product tests are not automatically rerun.

The original consumer source, proposed Action source and adopted checking source
are different plan inputs. A rebase changes the plan even if file trees are equal.
The controller permits at most two new fixture PRs per invocation and per trailing
24 hours. Each starts normal CI plus compatibility CI: at most four automatic
product jobs from those new publications. It reads complete native PR inventories,
counts the configured fixture App and exact branch family, and reserves capacity
for refs whose PR creation outcome is unknown. Existing fixtures reuse their runs;
excess work remains queued. Rebases, shared `main` changes and private `dev` changes
create new plans, so a backlog can take multiple days. Human reruns or outside
pushes are outside this automatic-publication limit; this is not a dollar cap.

`scripts/consumer-compatibility-impact.json` owns the reviewed exemptions. A skip
requires matching inspected shared source fingerprints on both sides, only listed
unaffected paths changed, and the exact reviewed complete private source-tree
family. New directories, unknown paths/modes, changes to either side of a rename,
unavailable inventories or private configuration changes fall back to testing.
Private family values are equality hashes, not encryption or published private
source. Records change through ordinary source review and adoption, never because
CI happened to pass. A successful exemption explicitly says product tests were not
run and creates no fixture.

The initial family predates the private caller and documentation. Those additions
change the private tree, so initial rollout uses capped full tests until a new
family is independently reviewed and adopted. No savings from exemptions are
claimed for that rollout. The initial private caller uses manual dispatch only.
Hourly sweeps, `dev` pushes and owned completion notifications require a later,
separately authorized bounded qualification stage before standing recurring
operation. For completion events, a read-only job verifies exact fixture ownership
before the credentialed job can start; unrelated completions do not mint App
tokens. Controller and filter jobs consume runner time. They never fan out to
other repositories.

## One-time setup and qualification

The human operator must approve and retain the exact Resource Enrollment and
Cross-Domain Grant, separate App installations and immutable dependency selection.
The protected environment must exist and be restricted to adopted Foundation
`dev` before a caller can invoke this workflow. It has no recurring reviewer gate.
Both keys and the protected authorization projection belong only to that private
environment; never put them in fixture source or candidate jobs.

| Environment item | Meaning |
| --- | --- |
| `CC_REPORTING_APP_ID` | Public check writer installed only on `.github`. |
| `CC_REPORTING_APP_PRIVATE_KEY` | Private environment secret for that App. |
| `CC_FIXTURE_APP_ID` | Fixture writer installed only on Foundation. |
| `CC_FIXTURE_APP_PRIVATE_KEY` | Separate private environment secret. |
| `CC_AUTHORIZATION` | Protected, current projection of the human-owned records. |

The nonsecret repository variable `CC_FIXTURE_BOT_ID` is a wake-filter hint
published by the same protected setup owner. The credentialed job compares it to
`CC_AUTHORIZATION.fixture_bot_id` before minting tokens. It does not grant access.

`CC_AUTHORIZATION` has schema 1; exact resource IDs; `reporting_app_id`,
`fixture_app_id`, `fixture_bot_id`; grant/enrollment IDs and SHA256s; principal,
trust domain, purpose, allowed actions, conditions and decision evidence; and
UTC `not_before`/`expires_at`. The parser accepts only its fixed flow and closed
fields. It provides no default grant. The protected publisher owns currentness,
renewal and revocation; remove the projection and revoke the installation when
authority is withdrawn.

The proposed token Action is immutable-pinned with post-job revocation enabled.
The existing PyYAML parser is pinned by version and wheel SHA256 in
`scripts/requirements.txt`, with no dependency resolution or source builds. Its
controller environment is isolated from the runner's other Python packages.
Renovate owns normal updates and Dependabot retains security coverage. Runtime
and dependency selection must be qualified before this uninvoked proposal is used.

Before the first privileged manual dispatch, qualify its source, environment,
principals, recovery safety and finite operation/cost allowance. Inspect every
applicable protection layer and bypass actor; unavailable readback is not proof
of protection. Native connection qualification observes App-created PR execution,
reporting, stale-input invalidation, interrupted-write recovery, denied callers and
environment restrictions. Measure actual runner use during those bounded runs.

Required-check admission and actual failure/missing/pending/wrong-issuer blocking
verification retain REQ-028 and their owning qualification decision. The initial
manual connection does not authorize a bounded enforcement stage before complete
applicable native qualification. Its unresolved evidence order remains explicit;
a test label grants no protected settings authority. Existing checks and human-only
merge requirements remain mandatory. For any later authorized admission, bind the
exact reporting App as the required issuer while preserving every existing check
and human-only merge requirement. Agree the operating allowance before the first
privileged dispatch.

REQ-008 prohibits testing proposed controller code with write credentials before
source adoption. Local synthetic tests and separate provider probes do not prove
that privileged end-to-end path. The initial fixed Foundation workflow admission
may use only REQ-020's exact evidence order. Complete coherent source and maintained
affected-consumer acceptance, independent review and every existing required gate
precede the human checker merge. Record current consumer selectors and the actual
main-following exposure: the checker becomes active at that merge.

Before seeking or relying on Foundation CI after checker adoption, publish and
reconcile the exact manual-only caller revision. Do not rerun or cite the earlier
automatic caller revision as qualification. Verify the hosted head and manual-only
source before requesting a run or relying on an automatically started result.

Before seeking that CI, Foundation's owner qualifies its read-only capture and
private retention path for the actual raw dependency record, consumer head/tree,
run and attempt, native Action acquisition revision, and validator snapshot/blob
output. The existing consumer-subject artifact does not identify the acquired
Action revision; a later API snapshot cannot stand in for it. Do not assume job
logs retain the raw provider record or an acquisition field until that access
and extraction path is verified. Missing capture capability returns to the owning
source/evidence workflow; it grants no instrumentation or run authority.

Before the manual-only caller merges, retain the actual dependency record passing
the checker with the real consumer-job token. Separately bind the human-merged
initial checker commit, the runner-acquired Action revision and the API-resolved
main snapshot with its immutable source blob. Verify the acquired source contains
the adopted checker; unresolved source movement or identity keeps qualification
incomplete. Retain the exact consumer head/tree, run/attempt and complete ordinary
CI result, including applicable product steps and posthooks. A local fixture or
later different candidate is not that evidence. A failed or unavailable
observation keeps caller adoption blocked.
Distinguish a standards-correct refusal, which needs consumer remediation, from a
checker defect requiring its own reviewed human-merged repair. Preserve failures
and required checks; this order permits no silent consumer exception, automatic
source revert or settings change.

The separately qualified privileged manual connection follows caller adoption;
its native acceptance remains open until observed. The controller selects open
shared proposals. The initial checker proposal's own native qualification is
therefore foregone, not waiting for a later run. Foundation's ordinary CI and a
later privileged fixture record their actual candidate, consumer and defining
source; neither supplies the foregone qualification.
Neither a pilot label nor source adoption authorizes execution or silently waives
a required premerge obligation. Outside this exact initial order, resolve required
premerge-evidence conflicts through the governing owner; human review does not
waive them. Never merge source merely to obtain missing required premerge proof
outside the adopted exception.

Keep schedule, push and completion triggers absent during manual qualification.
Before dispatch, verify the adopted defining controller SHA, Foundation `dev`
caller and default-branch discoverability, qualified protected environment and
principals, exact eligible candidates and remaining operation/cost allowance.
Unknown setup or inventory blocks dispatch. A separate bounded automatic-trigger
qualification package must resolve its exact source, trigger window, stop mechanism
and allowance before those events are enabled. Manual results cannot supply this
proof. Standing recurring operation and new required-result enforcement remain off until
their complete applicable native qualification passes. The required-result
blocking evidence order remains unresolved and must be resolved by its owning
qualification package before dependent enforcement. Preserve every existing
mandatory check. Agents do not attempt a merge or bypass to probe blocking.

The shared-CI protocol owner coordinates native acceptance and the exact source
and evidence package with Foundation's source, CI and private-evidence owner.
The same joint owners assess a later automatic
package. Later controller changes return to the shared-CI protocol owner and
Foundation for affected evidence/order assessment and required independent review;
a changed governing or risk commitment retains its human decision path.

The first privileged manual dispatch is real operational activation within its
bounded scope. Its qualified executor binds the invoking principal and actual run
identity, verifies the existing protected environment before dispatch, and checks
all discoverable public candidates and private fixture/unknown-write inventory.
A missing environment must not be discovered by invoking the workflow. A dispatch
that creates a fixture normally needs a separately budgeted follow-up after both
whole workflows and posthooks finish; no completion wake is present.

Manual-stage public results are qualification observations of their exact plans,
not an admitted standing gate or proof of complete native qualification. They use
the same visible check name and issuer as ordinary results; the public result does
not identify a separate manual stage. Existing head, plan and outcome meanings remain.
Before the window, verify that no existing
rule already requires this result; a conflicting starting state returns to the
protected owner without disabling or reinterpreting that gate. Retain observation
times and source movement. Stop new dispatches on failed predicates, reconcile
in-flight/unknown effects, and retain stale-result exposure when authorized
invalidation cannot be verified. Window expiry, protected publication withdrawal
and any required settings cleanup remain with their actual authorized owner.

## Qualification status

Initial fixed-member checker and manual-caller source acceptance follow
REQ-020's exact evidence-order amendment; this document does not establish that
a proposal is merge-ready. Foundation's ordinary dependency and product CI
against the adopted checker must precede caller adoption. Native manual
connection proof remains unexecuted; automatic qualification and
required-result enforcement duties remain incomplete. The shared main-only
controller retains a migration obligation to qualify its result subject and stage
for the adopted dev/staging route under REQ-027. Initial source adoption does not
resolve the subsequent required-result enforcement evidence order.

Existing parent recovery work includes unknown check creation across invocations,
orphan reservations, incomplete or unseen inventory and bounded-sweep starvation.
Those deficiencies remain prerequisites for affected native use. The private
caller must pass dependency admission against adopted shared policy. Later
controller changes retain their own premerge proof and governing evidence-order
assessment. Markdown rule-selection alignment and incompatible-rule transitions
retain their owners. Local tests do not close native duties. Source preparation
or adoption grants no setup, dispatch or enforcement authority.
