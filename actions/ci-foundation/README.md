# Selected foundation verification

The [owning Architecture](../../docs/architecture.md#selected-container-foundation-source)
defines admission, update ownership, withdrawal and rollback. This action checks
the actual checkout before any copied helper executes. It runs offline with
Python's standard library, using only its own released catalog and verifier.

The catalog currently admits no core revision. Synthetic fixture success does
not make a draft core eligible. Human source delivery, required checks, private
derivation evidence and a reviewed shared release precede real admission.

## Consumer wiring

Each platform selects one `.foundation/` directory and adjacent `foundation.lock`
at its checkout root. Component configuration stays application-owned; its
adapter supplies the platform build root explicitly.

Keep the existing required shared checks and run this gate before the
application-owned adapter. The following steps illustrate ordering inside the
consumer's required `CI` job after checkout; they are not a complete CI workflow
or an application scaffold:

```yaml
- name: Verify selected container core
  uses: ForgingAlpha/.github/actions/ci-foundation@v1
- name: Qualify application containers
  run: python3 -I bin/container-ci.py
```

The adapter path is supplied by the application. The verification step must not
use `continue-on-error`; the adapter must not use `always()` or another condition
that runs after failure. Enrollment tests demonstrate the actual private
checkout, exact resolved shared revision and adapter ordering. The gate neither
executes the adapter nor deploys containers. An ordinary update-ownership check
also invokes this same checker if either pair member exists. No pair there is
reported not applicable; the standalone gate always requires the complete pair.

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

An approved record addition goes through the existing human-reviewed shared
policy PR and protected `v1` release. All consumers reuse it; no per-app catalog
or new credential is created. Source admission includes update-coverage review
for that exact payload so future native-manager surfaces cannot acquire an
overlapping updater. The current core's variable image inputs stay app-owned.

## Evidence and failures

Each decision emits available verifier/catalog and lock fingerprints, an action
reference and a result. A null fingerprint means that input was unavailable.
Successful admission also reports the authenticated core commit/tree. Retain
these with the same job's native
`Set up job` action-acquisition log, which records the resolved `.github` commit.
The action ref `v1` and the consumer workflow SHA are not that commit. A missing
or ambiguous native association leaves source-version evidence incomplete.
Local/candidate action tests do not establish a protected shared release.

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
