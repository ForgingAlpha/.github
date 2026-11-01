#!/usr/bin/env python3
"""Single source of approved SPDX licenses for dependency review."""

from __future__ import annotations

import ast
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
    "LGPL-3.0-or-later",
    "MIT",
    "MIT-0",
    "PostgreSQL",
    "PSF-2.0",  # https://spdx.org/licenses/PSF-2.0.html
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


def approved_license_expression(expression: str) -> bool:
    """Enforce exact policy atoms without upstream version-range widening.

    The official action still validates SPDX syntax. This bounded boolean check
    preserves approved alternatives and never executes dependency-supplied text.
    """
    if not isinstance(expression, str) or not expression or len(expression) > 4096:
        return False
    tokens: list[str] = []
    position = 0
    depth = 0
    for match in re.finditer(r"\s+|[()]|[A-Za-z0-9][A-Za-z0-9.+:-]*", expression):
        if match.start() != position:
            return False
        position = match.end()
        token = match.group()
        if token.isspace():
            continue
        tokens.append(token)
        if len(tokens) > 512:
            return False
        depth += (token == "(") - (token == ")")
        if depth < 0 or depth > 32:
            return False
        # The pinned action rewrites OTHER, including OTHER.0, before parsing.
        # A valid LicenseRef atom stays an unapproved alternative, not malformed.
        reference = re.fullmatch(
            r"(?:DocumentRef-[A-Za-z0-9.-]+:)?LicenseRef-[A-Za-z0-9.-]+", token
        )
        if re.search(r"(?<![\w-])OTHER(?![\w-])", token, flags=re.ASCII) and not reference:
            return False
    if position != len(expression) or depth or not tokens:
        return False

    boolean_tokens: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        operator = token
        if token in ("(", ")"):
            boolean_tokens.append(token)
        elif operator in ("AND", "OR"):
            boolean_tokens.append(operator.lower())
        elif operator == "WITH":
            return False
        else:
            if index + 1 < len(tokens) and tokens[index + 1] == "WITH":
                if index + 2 >= len(tokens):
                    return False
                exception = tokens[index + 2]
                if exception in ("(", ")", "AND", "OR", "WITH"):
                    return False
                token += " WITH " + exception
                index += 2
            boolean_tokens.append("True" if token in APPROVED_SPDX else "False")
        index += 1

    try:
        tree = ast.parse(" ".join(boolean_tokens), mode="eval")
    except (SyntaxError, ValueError, RecursionError):
        return False
    nodes = list(ast.walk(tree))
    if len(nodes) > 1024 or any(
        not isinstance(node, (ast.Expression, ast.BoolOp, ast.Constant, ast.And, ast.Or))
        for node in nodes
    ):
        return False

    def admitted(node: ast.AST) -> bool:
        if isinstance(node, ast.Constant):
            return node.value is True
        if isinstance(node, ast.BoolOp):
            values = (admitted(value) for value in node.values)
            return all(values) if isinstance(node.op, ast.And) else any(values)
        return False

    return admitted(tree.body)


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
