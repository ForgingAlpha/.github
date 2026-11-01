#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" != admit ]]; then
  echo 'WHAT: Unsupported admission interface. WHY: Only the checked owner projection selects a route. HOW: Use the published wrapper.' >&2
  exit 1
fi
exec python3 -I -B "${GITHUB_ACTION_PATH}/../ci-org-baseline/scripts/proposal_route.py" admit
