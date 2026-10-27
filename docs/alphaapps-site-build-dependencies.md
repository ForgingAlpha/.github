---
status: approved
tags:
  - org/alpha-apps
  - topic/github
---
# Alpha Apps Static-Build Dependency Admission

This policy derives from [REQ-023](requirements.md#req-023---commercial-dependency-license-gate)
and the [dependency-review architecture](architecture.md). It defines a limited
admission for the fourteen immutable artifacts in the
[preparation receipt](audits/2026-10-26-alphaapps-site-sharp-artifacts.json).
The default SPDX allowlist and the existing Mapbox admission are unchanged.

## Scope and ownership

The only consumer is `ForgingAlpha/alphaapps-site`, root `package.json` and
`package-lock.json` in npm lock format 3. The receipt binds ten
`@img/sharp-libvips-*` packages at `1.3.4`, `@img/sharp-wasm32` at `0.35.5`, and
three `@img/sharp-win32-*` packages at `0.35.5`. Their complete identities,
declared LGPL-containing expressions, canonical registry artifacts, SHA512
integrities, archive digests and packaged notice digests are fixed by that receipt.
There is no wildcard artifact or future-version approval.

The shared-CI owner owns central identity policy and enforcement. The website
release owner owns the actual build and deployment contents. Leo Smigel, subject
to Applicable governing authority, owns the decision to permit this use under the applicable terms and the resulting
notice, source and distribution obligations. An agent's artifact verification or
policy proposal does not supply that decision.

## Permitted use and prerequisites

The use covered by this admission is the website's Astro static build, with the receipt's exact
Astro version and build/deploy input digests. These packages are optional resolved
toolchain dependencies. Their npm classification alone does not establish the
permitted use. This admission does not permit shipping their native libraries,
Wasm, package code or a dependency installation to browsers or the deployed Worker.

Before operational admission, the human use-basis decision must identify the
applicable terms, required notices, corresponding-source duties if applicable,
permitted internal build use, and any distribution restrictions. Missing required
evidence or unresolved obligations stop operational admission. The present receipt
establishes artifact and packaged-notice identity; it is not a complete legal or
distribution assessment. All fourteen archives contain a Licensing table in
`package/README.md`; absence of a separately named LICENSE file does not establish
absence of notices.

The decision belongs in this existing shared-policy request's retained evidence,
with the direct original human message or authenticated provider decision event,
actor, timestamp, exact artifact-set and build-envelope digests, applicable terms
and evidence references, permitted effects, obligations, and validity/revocation
conditions. Its stable artifact identity, exact revision and member digest must
be bound by the central admission record. An agent-authored status or copied
quotation is not the decision. Before releasing an enforcing successor, its
REQ-024 human reviewer must verify this binding against the original human source
and record that verification with the exact implementation revision. An exact
human PR approval can also supply the use decision only if its reviewed proposal
explicitly covers all these terms and effects; an implementation merge alone
cannot do so. A missing, stale or conflicting binding refuses operational
admission. Applicable product dependency-selection authorization under shared
ASR-AUTH-014 must be resolved and reused within its existing scope. This license
decision does not supply that authorization or require renewed approval of an
already covered selection/update. An uncovered choice remains with its product
owner; neither kind of decision implicitly supplies the other.

Each release relying on this admission must bind its exact source and generated
asset inventory, retain the actual emitted Worker bundle and its digest, and
establish that the deployment contains only the approved static output and
dispatcher. An import-free Worker source and a successful dry run without retained
bundle bytes do not complete that evidence. Unknown or changed output composition
stops delivery under this admission; it cannot be inferred from filenames alone.
Changed bound build/deploy inputs or runtime/redistribution use require a new
central policy review rather than a consumer waiver.

The website release owner retains this evidence in the existing website release
task, bound to the exact candidate head/tree, complete deployed-file inventory
and digests, emitted Worker digest, method and result of composition inspection,
and the applicable use-decision binding. A mandatory composition check in the
existing required `CI` result must verify the actual emitted files against that
declared static-assets/dispatcher boundary. The human release reviewer verifies
the retained record and exact CI result before delivery; the qualified deployment
executor binds the package actually uploaded to the same verified contents.
Missing, mismatched or inconclusive composition evidence, or any inclusion of the
admitted package code/native/Wasm content, refuses release. This is a future
enforcement obligation; the current dry run does not satisfy it.

## Required enforcement and acceptance

A subsequent enforcing implementation must preserve the official vulnerability
review at its current severity and scope thresholds. It may supply package-license
exclusions only for the exact consumer, with no consumer-selected exception input.
Whenever the consumer lock contains this admission's artifacts, the guard must
validate its fixed root manifest, Astro version and build/deploy input digests
on every pull request, even with an empty dependency diff. Missing dependency-change
output on a dependency-changing PR is a failure, not proof of an empty diff.
Because upstream exclusions may ignore versions and normalize names, an
independent mandatory guard must inspect every added or updated record matching
`@img/sharp-libvips-*`, `@img/sharp-wasm32` or `@img/sharp-win32-*` before the
ordinary nonempty-license shortcut. Normalized matching selects scrutiny, never
admission: a passing record must have the exact canonical policy identity.

For each added record representing an introduction or update, the guard must
require ecosystem `npm`, manifest `package-lock.json`, `change_type=added`, a
vulnerability array and a scope of `runtime`, `development` or `unknown`, all
subject to the unchanged vulnerability review. Scope is not build-use evidence.
It must require exactly one approved artifact,
the root manifest/lock binding, exact name, version, install path, registry URL,
SHA512 integrity, declared license expression, optional lock state, and the fixed
build/deploy inputs. It must reject unlisted family members, wrong versions,
nested or additional installations of an admitted artifact, duplicate records,
PURLs differing from the exact recorded canonical representation, license drift,
conflicts, missing evidence, symlinked manifest/lock
paths or ancestors, link descriptors, non-regular files and
malformed or oversized inputs. No SPDX-only shortcut or use of another approved
artifact may cover a mismatch. Routine CI compares the reviewed immutable evidence;
it does not download or execute these archives.
The recorded `%40img` namespace encoding is valid. Extra escaping, double encoding
such as `%2540img`, or any other representation differing from that exact approved
PURL is rejected; normalization never creates an additional accepted form.
Pre-existing unchanged nested versions receive no admission from this policy;
their normal dependency and vulnerability obligations remain. Their presence
must not be misrepresented as an additional installation of an admitted version,
or used to exempt a new or updated nested record.

Acceptance must distinguish the exact permitted records from each failure above,
prove unchanged handling for other repositories and Mapbox, and preserve refusal
when the upstream review or evidence guard fails. It must exercise the real
composite-action input/output path as well as the guard. Output-composition and
human use-basis prerequisites remain independently required before delivery; a
green source test cannot substitute for either.
Cases must also cover envelope-only and no-dependency-change PRs, each accepted
scope value without a vulnerability bypass, malformed or absent decision bindings,
and matching versus missing, mismatched or nonconforming emitted-package evidence.
Security updates of an admitted artifact deliberately stop until its new exact
artifact and affected envelope receive a new reviewed central policy; urgency
does not bypass this obligation or the REQ-013/014 security lane.

## Delivery state

This policy defines a conditional admission. Policy source alone changes no executable Action, validator,
allowlist, consumer dependency, hosted setting, permission or deployment. The
existing gate continues to block the website dependencies. Operational admission
requires the human use-basis decision, the reviewed enforcing implementation and
its human merge/current-channel release, followed by fresh exact-head website CI
and the normal human release process. This source proposal does not establish
Google app configuration, OAuth authorization or YouTube publishing readiness.
