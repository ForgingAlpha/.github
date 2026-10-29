#!/usr/bin/env bash
set -euo pipefail
mode="${1:?mode required}"
step="${2:?step required}"
case "$mode" in legacy|central) ;; *) exit 2 ;; esac
case "$step" in
  install) npm ci ;;
  build) npm run build ;;
  script)
    [[ "$mode" = central && "${3:-}" =~ ^[A-Za-z0-9][A-Za-z0-9:_-]{0,63}$ ]] || exit 2
    npm run "$3" ;;
  format|lint|types)
    case "$step" in
      format) tool=prettier; args=(--check .) ;;
      lint) tool=eslint; args=(--max-warnings 0 .) ;;
      types) tool=astro; args=(check) ;;
    esac
    if [[ "$mode" = central ]]; then
      [[ -x "node_modules/.bin/$tool" ]] || { echo "WHAT: Missing locked tool $tool. WHY: Downloads cannot replace locked tools. HOW: Repair dependencies." >&2; exit 1; }
      "./node_modules/.bin/$tool" "${args[@]}"
    else
      npx "$tool" "${args[@]}"
    fi ;;
  *) echo 'WHAT: Unknown Astro check. WHY: Only fixed steps are supported. HOW: Repair the checking source.' >&2; exit 2 ;;
esac
