#!/usr/bin/env python3
"""Single source of approved SPDX licenses for dependency review."""

from __future__ import annotations

import os
import re
import sys


APPROVED_SPDX = (
    "0BSD",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "BlueOak-1.0.0",
    "BSL-1.0",
    "CC0-1.0",
    "ISC",
    "MIT",
    "MIT-0",
    "PostgreSQL",
    "Python-2.0",
    "Unicode-3.0",
    "Unicode-DFS-2016",
    "Unlicense",
    "Zlib",
)

# Reviewed artifact policy, not a permissive SPDX classification or vendor-account grant.
# Changing this record requires control-plane review of the exact artifact and terms basis.
MAPBOX_ARTIFACT = {
    "repository": "ForgingAlpha/turnkeyleads-app",
    "manifest": "assets/customer/package-lock.json",
    "package_manifest": "assets/customer/package.json",
    "package_path": "node_modules/mapbox-gl",
    "name": "mapbox-gl",
    "version": "3.31.0",
    "package_url": "pkg:npm/mapbox-gl@3.31.0",
    "source_repository_url": "https://github.com/mapbox/mapbox-gl-js",
    "license": "LicenseRef-bad-see-license-in-license.txt",
    "lock_license": "SEE LICENSE IN LICENSE.txt",
    "resolved": "https://registry.npmjs.org/mapbox-gl/-/mapbox-gl-3.31.0.tgz",
    "integrity": "sha512-7i25NyCPW5jnqsqJq3irgBBEoVTJgfZqTJJS446Q3ZuxyAb5Om75UIcxYIo38oz9eDswnBXr0riz+M/C8V7g3Q==",
    # Reviewed preparation evidence; routine CI enforces the identity and SRI above.
    # Bound receipt: docs/audits/2026-09-26-mapbox-3.31.0-artifact.json.
    "license_member": "package/LICENSE.txt",
    "license_sha256": "c24eff481bf098c82fda9949b2d982589df8b36db11fffa49653d4afe1903998",
    "archive_sha256": "597c8eb058342941fc97857f69ebdcf3e7dcf5a1b2705abd63782f996da418ae",
}


def repository_identity() -> str:
    repository = os.environ.get("DEPENDENCY_REPOSITORY", "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Dependency license policy requires the GitHub repository identity.")
    return repository


def artifact_exception(repository: str) -> dict[str, str] | None:
    return MAPBOX_ARTIFACT if repository == MAPBOX_ARTIFACT["repository"] else None


def main() -> int:
    try:
        exception = artifact_exception(repository_identity())
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"allow_licenses={','.join(APPROVED_SPDX)}")
    # The official action ignores versions here. The always-running evidence guard
    # must independently reject every non-approved member of this whole family.
    exclusion = f"pkg:npm/{exception['name']}" if exception else ""
    print(f"allow_dependencies_licenses={exclusion}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
