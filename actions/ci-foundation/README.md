# Selected foundation verification

The [owning Architecture](../../docs/architecture.md#selected-container-foundation-source)
defines admission, update ownership, withdrawal and rollback. This action checks
the actual checkout before any copied helper executes. It runs offline with
Python's standard library, using only its own resolved checking-source catalog and verifier.

The catalog lists approved core revisions. Synthetic fixture success does
not make a draft core eligible. Human source delivery, required checks, private
derivation evidence and a human-reviewed main merge precede real admission.

## Consumer wiring

Each platform selects one `tools/container-foundation/` directory and a root
`foundation.lock`. Existing `.foundation/` imports remain supported during the
explicit transition. Exactly one of these two fixed payload locations must
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

The application integration owner prepares complete imported updates through
human-reviewed app PRs. The fixed first-party reviewed-import profile is the
pair's narrow management exception; ordinary Renovate/Dependabot ownership for
all other dependencies remains mandatory. A catalog record permits selection;
it does not establish application compatibility. Roll back only a complete
still-approved pair with compatible application configuration. Data migrations
and data are unaffected by source rollback.

Each application supplies its runnable target, images, health, migrations,
secrets and allocation. A disposable core fixture does not qualify a different
application storage profile.

## Prepare an approval record

The designated GitHub operator first verifies canonical repository identity,
human source delivery and required checks through its existing qualified
nonhuman access. In a private workspace, independently derive from that exact
committed source without importing or executing the upstream exporter:

```sh
python3 -I actions/ci-foundation/scripts/foundation_source.py derive \
  --source /absolute/qualified/core-checkout \
  --revision FULL_HUMAN_MERGED_COMMIT \
  --lock-output /absolute/private/new-foundation.lock
```

The output record is a candidate. Local origin text and Git objects do not prove
the numeric hosted identity, human merge, checks or eligibility. Independently
compare the private manifest with canonical blobs/modes and the owned export
serialization. Bind those exact inputs and observations to the proposed record
in qualified private task/artifact custody. Do not put the real lock, inventory,
payload or private receipt into this public repository, CI logs or artifacts.
Public self-CI uses synthetic fixtures exclusively.

Catalog schema version 1 permits an optional trusted record field `payload_paths`:
a nonempty, unique list containing only `.foundation` and/or
`tools/container-foundation`. Existing records without the field permit only
`.foundation`. Qualify the exact helper's support for each permitted location
before adding the field to its record. The derived record intentionally omits
this policy decision. The lock format, upstream identity and inventory remain
unchanged; a consumer cannot add layout eligibility to its lock. New standard
adoption requires a main-adopted record explicitly permitting
`tools/container-foundation`. Preserve a compatible legacy selection until that
record is available, then use the core-owned update and layout-migration
procedures. Moving an older legacy-only helper does not establish compatibility.

An approved record addition goes through the existing human-reviewed shared
policy PR and human merge into protected main. All consumers reuse it; no per-app catalog
or new credential is created. Source admission includes update-coverage review
for that exact payload so future native-manager surfaces cannot acquire an
overlapping updater. The current core's variable image inputs stay app-owned.

For a coordinated source and layout change, human-merge the exact core source
and verify its canonical delivery before merging its shared catalog admission
into protected main. Application source updates and layout migrations follow
that adoption. Execution uses the catalog from its resolved checking source,
never a second catalog fetched from later main. A proposed record in a task branch grants no runtime use.

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
Restore a complete approved pair for checkout drift; request shared admission
for an unavailable core revision; repair malformed shared policy with its owner.
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
