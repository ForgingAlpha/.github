# Imported source verification

The [Foundation implementation transition](../../docs/requirements.md#foundation-implementation-transition)
preserves the specified existing import responsibilities until qualified source
replacement. The target duties below do not retire this verifier or its catalog.

The [owning Architecture](../../docs/architecture.md#imported-source-integrity)
defines admission, update ownership, withdrawal and rollback. This action checks
the actual checkout before any copied helper executes. It runs offline with
Python's standard library, using only its own resolved checking-source catalog and verifier.

This action serves existing imported source pairs. Container responsibilities
follow the [container procedure](https://github.com/ForgingAlpha/control-plane/blob/main/system/runbooks/operate-local-containers.md).
An application keeps required imported-source checks until qualified input removal
and reconciliation of its actual caller and any enrollment under the owning
Architecture. The existing change record carries that evidence, including an
unenrolled application's actual absence of enrollment. File absence alone is not
qualified removal. Synthetic fixture success grants no source eligibility.

## Consumer wiring

An existing imported pair contains one `tools/container-foundation/` directory
or `.foundation/` directory and a root `foundation.lock`. Exactly one of these two fixed payload locations must
exist; the verifier rejects dual, partial, linked or non-directory selections,
including a linked `tools/` ancestor. Unrelated content under `tools/` is allowed.
Component configuration stays application-owned; its adapter supplies the
platform build root explicitly.

Keep the existing required shared checks and run this gate before the
application-owned adapter. The following steps illustrate ordering inside the
consumer's required `CI` job after checkout; they are not a complete CI workflow
or an application scaffold:

```yaml
- name: Verify selected container core
  uses: ForgingAlpha/.github/actions/ci-foundation@main
- name: Qualify application containers
  run: python3 -I bin/container-ci.py
```

The adapter path is supplied by the application. The verification step must not
use `continue-on-error`; the adapter must not use `always()` or another condition
that runs after failure. Enrollment tests demonstrate the actual private
checkout, exact resolved shared revision and adapter ordering. The gate neither
executes the adapter nor deploys containers. An ordinary update-ownership check
also invokes this same checker if either supported payload leaf or the root lock
exists, including dangling links and partial selections. Absence of all three is
reported not applicable; unrelated `tools/` content does not enroll a repository.
The standalone gate always requires the complete pair.

The application integration owner retains the exact approved pair and its
provenance through human-reviewed app PRs. No new upstream acquisition route is
selected. Restore checkout drift only from an approved complete pair. A payload
defect requiring changed source returns to that owner's qualified migration;
rewritten payload or lock bytes cannot grant admission. The fixed first-party reviewed-import profile is the
pair's narrow management exception; ordinary Renovate/Dependabot ownership for
all other dependencies remains mandatory. A catalog record permits selection;
it does not establish application compatibility. Roll back only a complete
still-approved pair with compatible application configuration. Data migrations
and data are unaffected by source rollback.

Each application supplies its runnable target, images, health, migrations,
secrets and allocation. A disposable core fixture does not qualify a different
application storage profile.

## Catalog and source custody

Use the catalog in the exact resolved checking source. Records bind source
identity, human-delivered commit/tree, export format and the exact lock digest.
The owning Architecture preserves canonical hosted-identity, human-delivery,
required-check and independent private-derivation predicates. Retained evidence
must establish each predicate for the exact admitted subject; an origin name or
exporter assertion cannot replace it. Missing provenance or its accountable
custody prevents a dependent catalog change. Real locks, inventory, payload and
private receipts stay in their owning custody; public self-CI uses synthetic
fixtures. The admitted export definition remains authoritative; verifier
maintenance creates no new format owner or export producer.

Catalog schema 1 allows `payload_paths` only as a nonempty unique subset of
`.foundation` and `tools/container-foundation`. Without that field only
`.foundation` is permitted. A consumer cannot add eligibility to its lock or
obtain compatibility merely by moving an older helper. Catalog changes retain
the owning Architecture's affected-consumer and human source-adoption duties.
No new source acquisition or import procedure is selected by this action.

## Evidence and failures

Each decision emits available verifier/catalog and lock fingerprints, an action
reference and a result. A null fingerprint means this decision retained no digest
for that field; it does not prove the input was missing or a read was attempted.
Successful admission also reports the authenticated core commit/tree. Retain
these with the same job's native
`Set up job` action-acquisition log, which records the resolved `.github` commit.
The action ref `main` and the consumer workflow SHA are not that commit. A missing
or ambiguous native association leaves source-version evidence incomplete.
Local/candidate action tests do not establish human source adoption.

Errors report WHAT, WHY and HOW without exposing private paths or inventory.
Restore a complete approved pair for checkout drift. Return an unavailable source
revision or malformed shared policy to its owner; do not assume source acquisition
is available or substitute an unqualified revision.
Never regenerate expected policy from a changed application lock to pass CI.

Checkouts must preserve exported bytes and executable bits. Content filters,
line-ending conversion or restrictive execute-bit masks can require checkout
correction before the exact exported representation matches.

The first supported checker is Linux/Python 3 with regular files and Git modes
100644/100755. Limits are 1 MiB per metadata file, 256 catalog records, 4,096
payload files, 16 MiB per payload file, 64 MiB total payload and 8,192 discovered
file/directory entries. Unsupported sizes fail explicitly rather than silently
truncating. Directory iteration stops at the entry limit. Derivation caps Git
stdout to the relevant input limit and stderr to 1 MiB while reading, stops its
owned process group on refusal or timeout, and checks aggregate blob sizes before
reading the next blob. These limits cover the actual initial export; later source admission
must qualify changed representation or workload. This is a checkout integrity
check, not protection against a hostile concurrent runner process.

Run the canonical local checks from this repository root:

```sh
python3 -I actions/ci-foundation/scripts/foundation_source.py catalog
python3 -m unittest discover -s actions/ci-foundation/tests
python3 -m unittest discover -s actions/ci-update-ownership/tests
```

Source recovery uses a checked corrective or revert PR and human merge into main.
A whole-policy revert may restore a previously withdrawn approval; disclose the
exact restored records and use a forward fix when withdrawal must persist. Earlier
source and run records remain evidence, without an active historical-tag fallback.
