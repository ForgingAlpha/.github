#!/usr/bin/env bash
set -euo pipefail

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "✗ ci-markdown must run inside a Git checkout." >&2
  echo "  WHAT: git could not find a work tree for tracked Markdown discovery." >&2
  echo "  WHY: ci-markdown validates every tracked Markdown file." >&2
  echo "  HOW: run actions/checkout before ForgingAlpha/.github/actions/ci-markdown." >&2
  exit 1
fi

while IFS= read -r file; do
  [ -n "${file}" ] || continue
  printf '%s\n' "${file}"
done < <(git ls-files -- '*.md' '*.markdown')
