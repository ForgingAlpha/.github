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
claimed for that rollout. The private caller proposes an hourly safety sweep,
`dev` pushes and owned completion notifications. A read-only job verifies exact
fixture ownership before the credentialed job can start; unrelated completions do
not mint App tokens. These lightweight controller/filter jobs also consume runner
time. They never fan out to other repositories.

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

Before enforcement, observe actual App-created PR execution, successful reporting,
failure/missing/pending/wrong-issuer blocking, stale-input invalidation, interrupted
write recovery, denied callers and environment restrictions. Inspect every
applicable protection layer and bypass actor; unavailable readback is not proof
of protection. Add the exact reporting App as the required issuer while preserving
all existing checks and human-only merges. Measure native runner usage and agree
the operating allowance before activation.

REQ-008 prohibits testing proposed controller code with write credentials before
source adoption. Local synthetic tests and separate provider probes do not prove
that privileged end-to-end path. Resolve any required premerge-evidence conflict
through its governing owner; neither a pilot label nor a human review silently
waives that requirement. Never merge source merely to obtain missing proof.
