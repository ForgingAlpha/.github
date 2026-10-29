# Organization baseline Fact Contract

Status: PROPOSED derived contract, authored for applicable-profiles-completion-20261029.
This text is not an independently validated Fact Gate, governing amendment, runtime
assignment, consumer enrollment or activation. Its governing source is `.github`
commit `97a8a94c884f43c039278d117d0d9313d1465ec9`: REQ-001–004, REQ-008–011,
REQ-024–026 and Architecture's Organization-required baseline pilot, Full application
profiles and producer transitions, language profiles, and Selected Container
Foundation Source sections. Conflicts return to those owners; this contract cannot
change their scope. No PROJECT.md exists at that baseline; no local override is inferred.

## Ownership and source precedence

The shared-CI owner owns this contract, enrollment representation, admitted producer,
component composition and result aggregation. Product owners own component purpose,
product behavior, npm script meaning and completeness of product tests. The shared-CI
owner coordinates component introductions and producer cutovers with product owners;
the protection operator owns actual protection, source selector and recovery effects.
Human source integration and hosted effects retain their existing authorization.

`enrollment.json` is accepted configuration only from the admitted checking-source
revision. It cannot assign runtime versions, admit foundation revisions, prove hosted
rights, or grant itself operational eligibility. `runtime-profiles/catalog.json` and
its existing validator own repository runtime assignments and exact tuples.
`ci-foundation/approved.json` and its existing verifier own admitted foundation
fingerprints. GitHub supplies observations of current PR/base, effective rules and
actual run results. Receipts and job outputs are derived evidence, never new policy.
A consumer manifest proves observed shape, not entitlement to select a smaller profile.

## Markdown policy rights and entry feasibility

| Assertion | Meaning owner and admitted writer | Consumer prerequisite and reconciliation |
| --- | --- | --- |
| Controlled common Markdown rules and byte limits | Shared-CI owns the fixed data-only common baseline; product owners retain any additional repository rule meaning. Central source admits the composition after owner review. | Every tracked Markdown file must pass central rules within 512 KiB/file and 8 MiB total; actual site inventory/format compatibility is an activation feasibility check. Consumer custom rules cannot weaken this baseline. Required additional product rules must be selected static_scripts or the consumer stays ineligible; no silent loss of custom policy. |

This is a Class-3 acceptance-right effect in the composed change, not merely a linter
implementation detail. Rule/limit changes need shared-CI review and affected product
reconciliation. Current legacy wrappers retain their existing repository-config behavior.

## Enrollment successor and totality

Schema 1 remains readable with exactly its existing keys and constraints; its only
profile remains `documentation-bootstrap`. Normalization explicitly derives bootstrap
producer, qualified-team policy, empty component list and non-applicable foundation
from that historical schema contract. Schema-1 application records are refused. Its historic release-route non-applicability
and result behavior stay unchanged; schema-2 route decisions cannot be backfilled into it.
The live catalog remains byte-identical in this change; schema 2 is exercised by
synthetic source fixtures. No public fixture ID represents an admitted real consumer.

Schema 2 has exactly `schema_version: 2` and `repositories` (1–32 records). Each
record has exactly these required fields, with no nulls, implicit defaults or unknown
keys:

| Field | Meaning and domain |
| --- | --- |
| `repository`, `repository_id` | Exact ForgingAlpha full name and positive integer ID; neither repeated; `.github` self-enrollment refused. Booleans are not integers. |
| `branches` | Bootstrap/direct route: explicit `['dev']` or `['dev','main']`. Staged application route: exactly `['dev','staging','main']`. No glob, omission, duplicates or branch-presence inference. Source support changes no live selectors. |
| `profile` | `documentation-bootstrap`, `rust`, `astro`, or `mixed`; actual component kinds must agree exactly. |
| `producer` | Closed enum: `bootstrap` for docs; `central-product` or `qualification` for applications. Qualification is the bounded carrier below, never accepted product CI. No consumer override or inherited producer. |
| `qualification_subject` | Exactly `{kind:'none'}` except for `qualification`, which requires the exact subject and legacy workflow binding below. No null or default. |
| `release_route` | Docs: exactly `{kind:'not-applicable'}`. Applications: explicit direct/staged projection with exact adopted product-source binding below. No unknown route admitted. |
| `review_policy` | Exactly `{kind:'qualified-team',team_id:positive-int,minimum_approvals:positive-int}` or `{kind:'codeowners'}`. Docs uses qualified-team. Team replacement for application CODEOWNERS needs separately retained actual protection qualification. |
| `foundation` | `not-applicable` for docs; application `required` or `not-applicable` only from an explicit owner-established scope disposition described below. |
| `components` | Docs: empty array. Application: 1–16 unique component records, sorted by root and kind; exact schema below. |

A Rust component has exactly `{kind:'rust',root:PATH,tests:['cargo-all']}`. An Astro
component has exactly `{kind:'astro',root:PATH,tests:TEST_SELECTION,static_scripts:[SCRIPT_ID,...]}`. `PATH` is `.` or
a normalized relative POSIX path: no absolute path, empty segment, `.`/`..` segment,
backslash, control character, leading option or linked ancestor. SCRIPT_ID matches
`[A-Za-z0-9][A-Za-z0-9:_-]{0,63}`; the list is nonempty, unique, ordered and at most
16 entries. IDs name npm scripts, never shell fragments, command lines or consumer
JSON overrides. The trusted enrollment fixes IDs after product-owner acceptance of
the actual commands. TEST_SELECTION is exactly `{kind:'required',scripts:[SCRIPT_ID,...]}`
with a nonempty list, or `{kind:'owner-declared-none',evidence_sha256:SHA256}`. The latter
requires a retained attributable product-owner decision that no extra product tests
are required for this component; it does not waive fixed meaningful common/static
checks. Missing/null selection, an empty required list or missing selected command
fails. A consumer cannot select none by deleting tests. Source fixtures illustrate
both states without asserting an actual owner decision.
`static_scripts` is required and may be explicitly empty when the fixed static core
is complete. Otherwise it selects unique bounded npm script IDs under the same syntax
and owner-selection rule, executed only in the static job, never repeated in tests.
Repo-owned architecture/custom Markdown/publication validation belongs here when the
product owner requires it. A missing selected script fails. Additional publication
checks, if required by the owner, are selected validation-only script IDs;
this does not permit publication or deploy effects during CI.

No schema-2 field can select a catalog, checkout, script path, shell command, runtime
version, exclusion glob, CI job name, token or opt-out. Unknown is an error;
`not-applicable` is an explicit decision with its own predicate, never missing evidence.

## Complete manifest classification

Inventory comes from the exact committed tree, including all tracked `Cargo.toml`,
`Cargo.lock`, `package.json`, `package-lock.json` and runtime files at every depth.
No changed-file selector, extension-only shortcut, vendor ignore or .gitignore exclusion
can narrow it. Validate clean tracked checkout, physical containment, modes and bytes
before parsing; reject gitlinks, unsafe paths and linked manifests/locks/configs.
Do not traverse an untrusted link. Bound counts and parsing bytes, refusing overflow
rather than truncating inventory. Application baseline bounds are 100,000 tracked
entries, 256 manifests, 1 MiB per manifest and 8 MiB combined manifest bytes; lock
reading uses the canonical validator's existing limits or an explicit 64 MiB bound.
Bootstrap retains its existing 512 inputs/512 KiB per file/8 MiB total limits unchanged.

Every package.json must be exactly one declared Astro root and contain an Astro
package dependency plus required local prettier, eslint and Astro commands available
from its locked dependencies. Every root has its own tracked package-lock.json.
Nested independent Astro components are supported by explicit declarations; npm
workspaces, local file/link/workspace dependencies between roots, yarn/pnpm locks,
vendored npm manifests and non-Astro packages are unsupported and fail. They are
not silently excluded or relabeled Astro. Unsupported ecosystem manifests detected
by existing update/dependency surface discovery also refuse application enrollment.

Each declared Rust root owns its tracked Cargo.lock and either a package or workspace
Cargo.toml. Admission records the full tracked manifest set without executing Cargo.
The required static job, after integrity and approved runtime admission, runs `cargo metadata
--locked --format-version 1 --no-deps` at that root, without compiling or running build scripts.
Compare canonical workspace root, workspace_members and each member manifest with
the complete tracked inventory. Every tracked Cargo.toml must be the declared root
manifest or an actual member covered by exactly one declared root. Workspace default
members cannot narrow coverage: commands use `--workspace`. Independent nested Rust
roots are supported only when metadata proves non-overlapping ownership. External
workspace members, linked/untracked members, vendored manifests, path dependencies
outside the admitted member set and Cargo workspace exclusions leaving tracked crates
uncovered fail. Metadata failure, incomplete output or unknown workspace identity is
an error, never permission for a lighter manifest heuristic. Cargo metadata uses --no-deps to avoid dependency enumeration/fetch; it still runs
without credentials after foundation/runtime admission and is not privileged evidence.

Each lock belongs to one declared root; undeclared/orphan/nested extra locks fail.
Mixed means at least one component of each kind, not an inferred runtime tuple.
Any unsupported tree can be proposed to the owning contract in later work; this
bounded implementation must not claim support or drop an input to pass.

## Runtime and foundation boundaries

All central application profiles require an active repository assignment in the
existing runtime catalog and pass its `validate_catalog`, `validate_policy_assignment`
and `validate_projection` contracts. Use the repository-root tracked mise.toml and
mise.lock and root update-policy projection. Each component consumes that same tuple;
it must contain the tools required by every component. Do not invent component-level
runtime assignments. Refuse nested mise files, alternative runtime selectors and any
rust-toolchain or rust-toolchain.toml that could override the approved runtime. Use
existing pinned mise setup with locked installation at repository root and verify
actual selected tools before commands. A different supported layout needs prior
contract preparation; it cannot silently bypass exact projection validation.

The existing catalog has only Node and no Rust assignment. Rust and mixed execution
remain SOURCE-FIXTURE-ONLY until the runtime owner supplies an approved real assignment,
valid lock/platform integrity shape, actual Rust toolchain selection and tool provenance.
Synthetic catalogs are injected only by tests; the production CLI always uses the
fixed trusted catalog. Do not relax its active-assignment requirement or add an unused
Rust tuple. This limitation does not block independent docs/Astro source qualification.
The Markdown tool's Node and actionlint/cargo-audit tooling are shared checking tools,
not consumer product runtime assertions. Keep their existing owned pins/update coverage;
do not copy application versions into workflow inputs or call tool Node a runtime tuple.

For an explicitly foundation-backed application, `foundation:'required'` always calls
the canonical verifier with its fixed checking-source catalog before any copied helper,
consumer formatter/configuration, package install, metadata, build or test. Deleting
both foundation.lock and payload fails; update-owner's absent-pair behavior cannot
replace this unconditional admission. Partial/dual imports and modified bytes fail.
`not-applicable` requires an explicit existing owning-scope determination retained by
the shared-CI/product owners before activation, and refuses either pair member if
present. Absence of files, an Astro label or static-site output alone establishes
neither exemption nor container obligation. The broad application wording in Selected
Container Foundation Source must be reconciled against the actual consumer's scope;
unresolved applicability blocks that consumer, not independent source preparation.
No new foundation exemption is adopted by this proposed contract. Existing catalog
admission/release and pinned-source withdrawal/rollback obligations remain unchanged.

## Fixed checking composition

Use fixed Python/shell entrypoints owned by existing actions, reached from the same
resolved repository archive through `GITHUB_ACTION_PATH` in legacy wrappers and from
the separately verified trusted checkout in the central workflow. A missing sibling
helper fails. Keep pinned external setup/cache Actions in wrappers, their current
inputs/defaults/conditions, full common steps, command order, flags and failure
semantics. This preserves observed legacy behavior for unknown/unmigrated callers,
not a claim that its existing merge-route defect satisfies governing policy. The
legacy guard permits dev-to-main for staged products and rejects staging-to-main;
that drift remains explicitly unresolved until authoritative affected route bindings
exist. Central schema-2 admission must not inherit that wrong behavior. Wrappers keep their existing changed/all Actions-safety choice and `@v1`
common calls. There is no omit-common input, new `$/` syntax, nested-local-action
workaround, YAML execution engine or new parser dependency.

Central composition is fixed source code with explicit consumer root/cwd. Reuse
canonical validators, current PyYAML and existing language commands. Where a command
block currently exists only in YAML (merge-flow/actionlint install), extract that
block to its existing owner's shell helper and preserve wrapper invocation semantics;
any such extra file scope must be bound in the implementation Brief before Build.
Do not copy a second policy implementation into baseline.py. External Actions retain
full SHA pins and reviewed comments. Central transitive local helpers must never
resolve a moving sibling @v1, including hidden nested `uses` or script downloads.

The common job runs the following once, before product jobs, with exact head/base:

1. Identity, enrollment, complete tracked inventory, producer-conflict and applicable
   foundation/runtime data validation. Rust workspace metadata verification is a
   mandatory static-job obligation after admitted setup; no Cargo runs in admission.
2. Schema-2 declared release-route admission below, with its separate exact security
   projection carveout; no changed event is passed to that guard. Bootstrap remains
   unchanged. Do not use the legacy dev-only guard as central application admission.
3. Full source-truth policy script; full CODEOWNERS script for `codeowners`, or fresh
   complete effective-team rules for a qualified-team record. Team membership/bypass
   qualification remains external; a matching ID does not prove it.
4. All tracked Markdown through existing controlled data-only lint_bootstrap checking,
   with action-owned configuration and no consumer custom rules/config execution.
   Bootstrap retains its exact current limits and behavior. Application Markdown is
   checked as admitted UTF-8 text with the same per-file/total text limits; overflow
   refuses explicitly. Required extra repo policy is selected in static_scripts and
   runs later in the product static job. Unsupported/custom requirements without an
   owner-selected complete static obligation block enrollment, never silently vanish.
5. Full workflow/composite inventory: actionlint and check_workflows.py always run for
   application profiles, including Markdown-only changes. Existing reviewed exceptions
   retain their owned validation; they cannot skip this complete check.
6. Existing Dependabot coverage, complete update-ownership validator and canonical
   foundation update-owner check. Missing required update policy or owner fails.
7. Pinned dependency-review Action with low severity and existing license policy and
   exact-artifact evidence validation. Add the scoped `workspace` input at
   ci-dependency-review/action.yml, defaulting to the existing github.workspace.
   Its license-evidence step sets DEPENDENCY_WORKSPACE from that input. The trusted
   central caller supplies its verified absolute consumer root; external dependency
   review Action/pin, policy, conditions and legacy default remain unchanged. The
   owner tests cover default and secondary checkout; credentials exist only in
   trusted metadata steps, never npm/lint/build/test.

The policy API is the full existing `validate_product_lifecycle_baseline.py` process
with cwd=consumer, explicit `ALPHAAPPS_POLICY_BASE_REF=<verified base SHA>`,
`ALPHAAPPS_POLICY_REPO_KIND=code` and only that process's event set to
`org_baseline_exact_head` to disable HEAD^2 inference. Central profiles additionally
require complete approved structural metadata via `baseline_statuses` and
`incomplete_baseline`; the definition-only fallback is not application admission.
No shortened status-only clone replaces the full process. CODEOWNERS uses its full
`validate_codeowners_contract.py` from trusted source, cwd=consumer. Preserve sanitized
Git environment, no hooks, no lazy fetch/replacements and no credential persistence.

Static job: for each admitted component run its static commands once. Rust runs
`cargo fmt --all -- --check`, `cargo clippy --locked --workspace --all-targets
--all-features -- -D warnings`, `RUSTFLAGS='-D dead_code' cargo check --locked
--workspace --all-targets`, existing exact cargo-audit installation and `cargo audit`
at its lock root, after mandatory exact workspace metadata coverage validation. Astro runs `npm ci`, `./node_modules/.bin/prettier --check .`,
`./node_modules/.bin/eslint --max-warnings 0 .`, `./node_modules/.bin/astro check`, then
`npm run build`, followed by every selected static_scripts ID via `npm run ID`.
Local executable presence is checked; no npx download can repair a
missing tool. Flags strengthening the central path do not silently change legacy
wrapper commands. A fixed internal execution mode differentiates central locked
commands from preserved wrapper commands; it is not an exposed consumer opt-out.

Test job: one logical lane per declared component, executed in one bounded job after
common/static success. Repeat
only locked tool/dependency setup and the assigned tests. An Astro component with
explicit owner-declared-none performs no test install/command; the fixed test job
still completes and emits that exact explicit disposition. No missing output or
skipped job can substitute for it; all required common/static jobs still must pass. Rust runs `cargo test
--locked --workspace --all-targets --all-features`. Astro runs `npm ci` and each fixed
`npm run SCRIPT_ID` in enrollment order, never `--if-present`. No static checks in
these lanes. Missing executable/script/lock, failure or timeout fails. A product owner
whose meaningful tests need services, secrets, arbitrary setup or additional Rust
commands is unsupported until that requirement is explicitly prepared, not declared
covered by cargo-all. Setup installs may run consumer lifecycle scripts only after
admission and without secrets. They are not trusted policy assertions.

## Existing tool literal custody

The current renovate.json only extends renovate-config.json. Neither has a custom
manager, and validate_central_preset rejects unknown manager configuration. There are
no literal-manager file patterns to relocate. Keep existing actionlint version/checksum,
mise setup version and cargo-audit version values at their current action-owner YAML
paths, without creating new version selections or changing update policy. Extracted
helpers accept those trusted values as fixed parameters. Central code may read only
exact explicitly named keys at those fixed source paths using existing PyYAML; validate
types/expected shape and never evaluate run text or a generic YAML command definition.
The fixed reads are ci-github-actions/action.yml Install actionlint step env keys
ACTIONLINT_VERSION/ACTIONLINT_SHA256, ci-astro/action.yml Install exact locked runtime
step with.version, and ci-rust/action.yml Install cargo-audit step
env.CARGO_AUDIT_VERSION. Missing/duplicate named steps or keys fail.
Where an existing version is in a command, expose the unchanged value as an owner YAML
env key for the same step and use the fixed canonical helper argv. The legacy command
journal must remain identical. This is source custody, not proven updater coverage:
configured Renovate ownership does not establish automation for those numeric tool
literals. The pre-existing coverage gap stays explicit; this change adds no manager,
policy exception, downloaded tool or version and does not claim to repair that gap.

## Declared release-route projection

The product owner owns its Current declared route. Current control-plane ASR-AUTH-005
and Architecture §5.9 require staging where declared and prohibit inferring a route
from branch existence. The attributable original human decision is
`msg_01a17993-0ab8-7230-a762-0d1068725c7d` (2026-10-26), retained in the task evidence;
it requires staging where configured. `.github` source admission projects an existing
product decision; it does not choose or redefine that decision.

An application `release_route` has exactly `declarations`, `transition` and
`reconciliation_sha256`. The digest identifies the retained attributable product-owner
reconciliation receipt, including Current source revisions, the declared route meaning,
permitted update and any exact authorized successor. It is provenance, not a claim that
a digest grants authority. No new product-side file, JSON schema or globally fixed
Architecture location is required.

`declarations` contains one entry normally, or two during an explicitly owner-authorized
route change. Each entry is exactly `{kind:'direct'|'staged',path,start,end,text}`.
Path is the owner-selected existing regular Markdown source path, subject to the same
safe relative-path rules; start/end are distinct complete existing delimiter lines,
unique in that file, and text is the exact UTF-8 declaration region between them.
Use at most 8 KiB for the region and 256 bytes per delimiter. This source-owned bounded
selector projects an existing owner declaration; it does not require a new consumer
representation. Unsupported/ambiguous source shapes require an owner reconciliation
before enrollment rather than inventing a file or parsing arbitrary prose as authority.
The owner receipt verifies that this region expresses the complete relevant route.
Runtime matches the region, not the whole file: unrelated Architecture edits pass.
Missing/duplicate delimiters or declaration mismatch fail. The exact original whole
source commit/blob stays in retained provenance, not an immutable runtime head/base pin.

`transition` is `none` for one declaration and `owner-authorized` for two, ordered
predecessor then successor. Stable same-entry matches and the forward predecessor-base
to successor-head pair are allowed; reverse pairs require separately reconciled recovery. Admission
matches base and head regions against this finite source-owned set. Stable runs require
the same declaration; an authorized transition also permits the exact declared old/new
pair. No unmerged commit must be an ancestor of the base. The shared-CI/product owners
first authorize and retain the exact successor meaning, admit a source successor that
recognizes both declaration regions, and qualify that source before the consumer
route-change proposal. During the interval use the stricter staged promotion rule if
either matched declaration requires staging; this cannot open a staged shortcut.
Then human-merge the consumer declaration change through its permitted route, reconcile
other affected branches and outstanding heads, and retire the predecessor declaration
from a subsequent central source. Retain strict current-base/CI and old/new observations
throughout; unknown outcome pauses the transition for reconciliation. Rollback uses
that captured pair/producer state and cannot silently restore a forbidden shortcut.
This bounded source/consumer ordering supports actual route changes without a whole-file
edit deadlock. It authorizes no live change and adds no general route registry.

Currentness, complete declaration meaning and the authority for an actual successor
remain owner-qualified activation prerequisites. The source fixtures exercise matching
and ordering only. An unresolved/superseded owner reconciliation blocks affected
activation; branch presence or a matching declaration alone is not owner authority.

The common owner's fixed helper has two explicit internal interfaces:
`legacy-observed` retains existing wrapper behavior and known drift;
`declared-route` receives only the trusted decoded enrollment declaration set, validated exact
consumer root and fresh PR event. Legacy wrappers expose no new route or bypass input.
The central runner always chooses declared-route for schema-2 applications, including
qualification; it cannot select legacy behavior because evidence is unavailable.
Use the existing common-owner helper path and canonical security verifier, not a
consumer JSON file, branch-existence API inference or a second route registry.
The central helper validates the source binding above, same-repository PR identities,
exact head/base and permitted pair before returning admission; no arbitrary branch
or shell expression is accepted as a route. Extend this bounded helper's owned tests.

For a matched direct route, ordinary promotion to main requires same-repository dev; staging is not
an admitted target. For staged, ordinary promotion to staging requires same-repository
dev and ordinary promotion to main requires same-repository staging. Staged dev-to-main
is refused even if staging is absent, unused or has a failing check. Neither path
creates or updates a branch. Normal authored PRs into dev remain under the existing
nonpersistent-source/human proposal process. This helper retains the existing absence
of a promotion-source restriction for targets named dev, including main/staging-to-dev;
it does not invent a new prohibition. Passing the guard does not authorize such a
proposal, and branch-name shape alone is not proof of nonpersistent authority.
Source identity, exact revision, approved scope and human execution remain separate.

The existing `security_patch.py verify-ci-admission` remains a separate exact
machine-attested security-projection exception for main. It is not evidence of an
ordinary staged promotion. For a same-repository non-ordinary main head, acceptance
requires the unchanged verifier's complete proof; an unavailable verifier, permission
or mismatched attestation fails. A staged dev-to-main ordinary shortcut does not fall
through to an exemption based on branch name or CI success. No broadened security
policy, new credentials, security enrollment or migration is introduced. Consumers
whose security pipeline is bound to local CI remain excluded from central-product
activation even though this admission carveout is preserved in source.

## Plan, result identities and exact aggregation

A trusted admission job derives a bounded JSON plan from validated enrollment and
complete tree: schema, repository name/ID, PR number, base ref/SHA, head/tree SHA,
checking-source SHA, enrollment digest, profile/producer, qualification subject, declared route/source binding,
review/foundation dispositions,
canonical ordered components and required lane IDs. Lane IDs are bounded source-generated
indices tied to that ordered inventory, not consumer job-name expressions. Output
only these allowlisted values to GITHUB_OUTPUT using bounded validated serialization;
never emit commands, API responses, credentials, arbitrary log text or unchecked paths.
The admission/common job is data-only: no consumer JS, Markdown configuration, npm,
Cargo or custom helper executes in any job that emits authoritative plan/source/lane
outputs. Its trusted checkers parse consumer input only as data. Product static/test
jobs receive read-only plan expectations but cannot publish replacement plan or source
authority. They can affect only their required job success/failure; consumer-written
GITHUB_OUTPUT/GITHUB_ENV or altered trusted files cannot change required lane membership
or the finalizer checkout. The final freshness job independently checks out trusted
source and consumer, recomputes the data-only plan and performs trusted data processing
only. Environment stripping alone is not this isolation boundary.
The plan is a projection: every executing job revalidates source SHA, its clean source
checkout and consumer head/tree/base plus catalog digest before consuming it. Checkouts
are separate fixed paths; trusted jobs never load consumer build artifacts. Product
jobs share a runner with consumer code and do not claim filesystem isolation after it
executes; the independent finalizer has fresh checkouts.

Use a named common result `Organization Baseline`. Bootstrap's final complete-profile
result is `CI` and requires its unchanged common bootstrap checks. Application central-product
fan-in is `CI`; qualification fan-in is fixed `Organization Profile Qualification`; source/self runs and unknown/unadmitted targets must never produce a
successful CI. Every job excluded for the defining `.github` repository must also
have a distinct non-CI name when skipped: its independent required CI must never
collide with an excluded central job. Qualification-only result names stay distinct.
Job names may use the admitted plan's closed enum output with a fixed
non-CI fallback when admission fails; never use a repository-name shortcut. Job-name
needs expressions are documented platform capability, but actual required-workflow
result binding remains a hosted qualification obligation.

Avoid matrix-result information loss: the minimal source uses a bounded test job
that executes the complete ordered component list and records one result per component,
while exposing one fixed direct `needs` result; no individual test failure may be
swallowed to finish green. This supports all components without arbitrary dynamic
jobs and supplies exact aggregation evidence. Static work remains in its own job.
The implementation may not replace this with a matrix aggregate without independent
preparation of per-component completion conservation.

Fan-in uses `always()` only to run its checks. It requires admission, common, static
and test direct-needs results for applications; bootstrap explicitly has only admission
and its bootstrap common result. Only `success` satisfies an applicable obligation.
`failure`, `cancelled`, `skipped`, missing, null, unknown and duplicate/mismatched lane
receipts all refuse success. A bootstrap-inapplicable static/test job may be skipped
only when the authenticated complete plan explicitly declares no such obligations.
Non-applicability cannot arise from a missing output or a failed job.

Before final success a trusted step freshly re-reads PR head/base, current branch,
applicable team rules and source/consumer bindings, and validates the complete required direct-needs results. Per-component logs/receipts
are diagnostic evidence only and cannot change the trusted complete component list
or override job failure. Recheck against the same event base/head; movement refuses. No global
atomicity with later GitHub changes is claimed; strict current-base protection and
actual required-check binding remain hosted prerequisites. Receipt transport is bounded JSON job outputs only: at most 16 component entries and
64 KiB per static/test output, with duplicate/unknown fields rejected. No upload/download
Actions, artifact dependency or new permission is introduced. The finalizer treats
outputs as deny-only: missing/malformed/mismatched/failed component output refuses;
matching success never grants authority or replaces a required direct-needs success.
It independently derives membership/identity from trusted source. Consumer outputs
are never executed or imported as files/code in trusted jobs.
Consumer code may forge its own test output: script meaning still requires product
ownership; a receipt is not a hostile-code sandbox or an independent assertion of
business correctness. Before consumer execution, source/checkouts/helpers are verified. After npm lifecycle
or other consumer code runs on the same runner, helpers and process results are not
protected against that code rewriting files or job output. This equals the legacy
execution exposure and is explicitly not a hostile-code sandbox guarantee. Static/test
job success and matching outputs are necessary execution signals, not independent
proof against malicious consumer code; they are deny-only inputs to the finalizer.
Separate data-only jobs preserve plan and policy authority, not isolation of every
helper inside a consumer-executing job. No token is passed in environment to consumer processes, including
GITHUB_TOKEN, GH_TOKEN and GITHUB_LICENSE_TOKEN; persist-credentials stays false.

Bootstrap retains the exact existing public receipt field set and meanings; topology
or internal plan metadata does not silently change that public contract. Application
receipts use a distinct versioned shape containing approved plan identities,
catalog/verifier fingerprints, required lane IDs and exact conclusions. These new
application fields are never inferred for a bootstrap receipt.
Freeze public subject metadata before authenticated operations, emit only after
validation, and discard authenticated return payloads. Never log private foundation
locks/inventory, rule bodies, membership, secret-bearing exceptions or tokens. Failed
runs retain actionable sanitized refusal and exact public subject where validated;
missing evidence remains missing. Store exact source qualification and private admission
material through the existing retained task/artifact custody. Source receipts do not
prove real consumer protection, product quality, source adoption or deployment.

## Introduction, cutover and recovery protocol

The shared-CI owner coordinates the product owner and protection operator. For a new
component, bind the proposed complete consumer head and source enrollment successor,
owner-selected tests, runtime/foundation compatibility and source/base predecessors.
Qualify the exact pair before activating the selector or accepting that consumer head.
Existing pins reject undeclared new components; successor pins reject old heads missing
the newly required component. That fail-closed interval is permissible; a green gap or
lighter fallback is not. Serialize overlapping introductions for the same consumer,
re-read current source/consumer predecessor and inventory, reconcile concurrent proposals
and repeat affected qualification. Do not extend a component list solely to unblock CI.

Inventory all consumers of the CI result, including security classifier/verifier path,
workflow_run wake, push-event requirement, CodeQL and release controls. Unknown evidence
blocks activation. Consumers bound to repository-local security CI or required push CI
retain their full caller in this revision. No source fixture substitutes for that
inventory, and no org-required PR workflow proves those event contracts.

At admission parse every tracked workflow with existing PyYAML under bounded strict
mapping validation (reject ambiguous keys/tags/unsupported shape). For central-product,
refuse any local job whose effective literal name or default job ID is CI, dynamic
name/reusable-workflow result whose CI identity cannot be proven absent, or a push CI
producer. Parse string/list/mapping event forms. Treat ambiguous producer evidence as
failure; do not pick whichever CI passes. Relevant called workflow uncertainty blocks
admission rather than following consumer-controlled network references. This conservative
boundary does not prohibit unrelated literal-name workflows whose results are proven
distinct. No consumer allowlist can waive a dual producer; only the exact centrally bound
qualification carrier below permits its existing sole legacy CI to coexist with a
distinct qualification result.

The supported qualification carrier is the same schema-2 source-owned record with
`producer:'qualification'`. `qualification_subject` has exactly
`{kind:'legacy-ci',branch,legacy_workflow:{path,blob,job_id}}`. Repository identity comes
from the enclosing record and branch must be explicitly enrolled. Path is a normalized
tracked `.github/workflows/*.yml` or `.yaml` file; blob is its exact SHA40 Git blob and
job_id is a literal YAML job ID whose effective literal name is CI. No dynamic/matrix
name, reusable producer or additional indistinguishable CI is supported. There is no
workflow_id lookup or new Actions permission. Hosted operator evidence separately
binds actual result producers/protections; source validation does not pretend to prove
that solely from a filename.

Only this exact legacy workflow/job is exempt from central-product dual-producer refusal
during qualification. Its blob must match at each observed head; all other CI/dynamic
unresolved producers refuse. Existing push triggers in that bound workflow remain;
legacy CI retains every obligation and central qualification does not satisfy its
push/security wake contracts. A workflow-definition change needs new source admission,
but ordinary head/base movement, valid/invalid/repair and already-open PR sequences do
not. Every run independently verifies and records its actual current head/base/tree;
none is pinned in the catalog or accepted from a consumer receipt.

The complete central common/static/tests run on each observed exact revision, with
Organization Baseline and fixed Organization Profile Qualification results. They never
emit CI or replace existing required legacy CI. Preserve legacy CI, human review and
all other protection. Qualification evidence records each observed subject and outcome;
equivalence/activation eligibility still requires retained owner review and actual
protection observations. No qualification target is enrolled by this source change.

The finalizer freshly derives producer, route, complete component set, qualification
subject and fixed result identity from its own trusted source and exact consumer
checkout. It verifies exact required direct-needs conclusions. It never derives plan
membership, producer or result name from consumer receipts. A missing admission
output cannot select qualification, CI, an empty plan or a successful fallback.
Qualification source-self skips still have distinct non-CI names. Transition from
qualification to central-product requires a separately authorized reviewed source
successor and actual protected selector/cutover qualification; changing this enum is
not a consumer opt-in or self-executing migration.

Before retirement qualify equivalent complete coverage under a distinct provisional
result on a separately authorized target; source support does not enroll that target.
Capture old/new workflow IDs, source pin, selectors, full controls, exact retirement
head/base and recovery source. Select the central producer before merging retirement;
the separately required Organization Baseline refuses every pre-retirement head still
carrying local CI even if either CI is green. Required CI and strict current-base
controls remain. The retirement head removes the caller and receives CI only centrally.
Already-open heads must update to post-retirement base and pass uniquely. End the
window only after observed retirement/current-base success or captured recovery.

Before retirement recovery restores the captured qualified producer/configuration.
After retirement a settings revert alone is insufficient: restoring the caller needs
its separately reviewed human-merged consumer source change and observed valid-pass /
invalid-block enforcement. Failed, cancelled, skipped or absent restored CI is not
recovery. Unknown mutation outcomes require reconciliation before retry. This source
change performs none of those effects and keeps all actual catalog assignments intact.
