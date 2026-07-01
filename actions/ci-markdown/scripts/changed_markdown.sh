#!/usr/bin/env bash
set -euo pipefail

base_ref="${MARKDOWN_BASE_REF:-auto}"
ignore_prefixes="${MARKDOWN_IGNORE:-}"
mode="${1:-changed}"

case "${mode}" in
  changed|--changed) mode="changed" ;;
  all|--all) mode="all" ;;
  *)
    echo "✗ Unsupported Markdown file selection mode '${mode}'." >&2
    echo "  WHAT: changed_markdown.sh received '${mode}', expected changed or all." >&2
    echo "  WHY: ci-markdown supports only changed-file and all tracked-file modes." >&2
    echo "  HOW: call changed_markdown.sh with no argument for changed mode or --all for all mode." >&2
    exit 1
    ;;
esac

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "✗ ci-markdown must run inside a Git checkout." >&2
  echo "  WHAT: git could not find a work tree for changed Markdown detection." >&2
  echo "  WHY: changed mode compares tracked Markdown files against a base ref." >&2
  echo "  HOW: run actions/checkout before ForgingAlpha/.github/actions/ci-markdown." >&2
  exit 1
fi

resolve_auto_base() {
  if [ -n "${GITHUB_BASE_REF:-}" ] && git rev-parse --verify --quiet "origin/${GITHUB_BASE_REF}" >/dev/null; then
    printf 'origin/%s\n' "${GITHUB_BASE_REF}"
    return 0
  fi

  for candidate in origin/main origin/dev main dev; do
    if git rev-parse --verify --quiet "${candidate}" >/dev/null; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  return 1
}

if [ "${mode}" = "changed" ] && [ "${base_ref}" = "auto" ]; then
  if ! base_ref="$(resolve_auto_base)"; then
    echo "✗ Could not resolve an automatic base ref for changed Markdown linting." >&2
    echo "  WHAT: none of GITHUB_BASE_REF, origin/main, origin/dev, main, or dev resolved." >&2
    echo "  WHY: changed mode needs a stable comparison point." >&2
    echo "  HOW: fetch the base branch with actions/checkout fetch-depth: 0, set base-ref, or use mode: all." >&2
    exit 1
  fi
elif [ "${mode}" = "changed" ] && ! git rev-parse --verify --quiet "${base_ref}" >/dev/null; then
  echo "✗ Markdown base ref '${base_ref}' was not found." >&2
  echo "  WHAT: git could not resolve '${base_ref}'." >&2
  echo "  WHY: changed mode needs a valid base ref." >&2
  echo "  HOW: fetch the ref, set base-ref to an available ref, or use mode: all." >&2
  exit 1
fi

is_ignored() {
  local file="$1"
  local prefix

  while IFS= read -r prefix; do
    [ -n "${prefix}" ] || continue
    case "${file}" in
      "${prefix}"*) return 0 ;;
    esac
  done <<<"${ignore_prefixes}"

  return 1
}

if [ "${mode}" = "all" ]; then
  file_source=(git ls-files -- '*.md' '*.markdown')
else
  file_source=(git diff --name-only --diff-filter=ACMR "${base_ref}...HEAD" -- '*.md' '*.markdown')
fi

while IFS= read -r file; do
  [ -n "${file}" ] || continue
  case "${file}" in
    *.md|*.markdown)
      if ! is_ignored "${file}"; then
        printf '%s\n' "${file}"
      fi
      ;;
  esac
done < <("${file_source[@]}")
