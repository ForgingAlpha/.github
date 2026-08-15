#!/usr/bin/env python3
"""Single source of approved SPDX licenses for dependency review."""

from __future__ import annotations


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


def main() -> int:
    print(f"allow_licenses={','.join(APPROVED_SPDX)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
