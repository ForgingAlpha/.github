#!/usr/bin/env bash
set -euo pipefail
case "${1:-}" in
  legacy-observed) ;;
  declared-route)
    case "${DECLARED_ROUTE:-}" in direct|staged) ;; *) echo 'WHAT: Missing declared route. WHY: Branch presence is not policy. HOW: Repair trusted enrollment.' >&2; exit 1 ;; esac
    if [[ "${BASE_REF}" = dev ]]; then exit 0; fi
    if [[ "${HEAD_REPOSITORY}" = "${GITHUB_REPOSITORY}" ]]; then
      if [[ "${DECLARED_ROUTE}" = direct && "${BASE_REF}" = main && "${HEAD_REF}" = dev ]]; then exit 0; fi
      if [[ "${DECLARED_ROUTE}" = staged && "${BASE_REF}" = staging && "${HEAD_REF}" = dev ]]; then exit 0; fi
      if [[ "${DECLARED_ROUTE}" = staged && "${BASE_REF}" = main && "${HEAD_REF}" = staging ]]; then exit 0; fi
    fi
    # A staged shortcut is an ordinary promotion refusal, not a security fallback.
    if [[ "${DECLARED_ROUTE}" = staged && "${BASE_REF}" = main && "${HEAD_REF}" = dev ]]; then
      echo 'WHAT: Staged dev-to-main shortcut refused. WHY: The declared route requires staging. HOW: Promote through staging.' >&2
      exit 1
    fi
    if [[ "${BASE_REF}" = main ]]; then
      python3 "${GITHUB_ACTION_PATH}/../security-patch/scripts/security_patch.py" verify-ci-admission --repository "${GITHUB_REPOSITORY}" --pull-request "${PR_NUMBER}" --target-branch main
      exit "$?"
    fi
    echo 'WHAT: Promotion is outside the declared route. WHY: Source branch is not admitted. HOW: Follow the product release route.' >&2
    exit 1 ;;
  *) echo 'WHAT: Unsupported merge-flow interface. WHY: An explicit owned mode is required. HOW: Use the published wrapper.' >&2; exit 1 ;;
esac

# Main-only repos are exempt: skip if no `dev` branch exists.
# Differentiate 404 (no dev) from other failures (auth, rate-limit)
# so transient errors fail closed instead of silently disabling the gate.
if gh_output=$(gh api "repos/${GITHUB_REPOSITORY}/branches/dev" 2>&1); then
  :  # dev branch exists; proceed to policy check
elif echo "$gh_output" | grep -qiE 'not found|"status":[[:space:]]*"404"'; then
  echo "✓ Repo has no 'dev' branch — merge flow policy does not apply"
  exit 0
else
  echo "✗ Unable to verify existence of 'dev' branch on ${GITHUB_REPOSITORY}" >&2
  echo "  gh api output: ${gh_output}" >&2
  echo ""
  echo "  WHY: The merge flow guard refuses to fail open on detection errors."
  echo "  HOW: Re-run the failed CI job; if the problem persists, check" >&2
  echo "       the GITHUB_TOKEN permissions on the calling workflow." >&2
  exit 1
fi

if [[ "$HEAD_REF" == "dev" && "$HEAD_REPOSITORY" == "$GITHUB_REPOSITORY" ]]; then
  echo "✓ Allowed source branch: 'dev' → '${BASE_REF}'"
  exit 0
fi

if [[ "$BASE_REF" == "main" ]]; then
  if python3 "${GITHUB_ACTION_PATH}/../security-patch/scripts/security_patch.py" \
    verify-ci-admission \
    --repository "${GITHUB_REPOSITORY}" \
    --pull-request "${PR_NUMBER}" \
    --target-branch "${BASE_REF}"; then
    echo "✓ Trusted exact security projection admitted to required CI"
    exit 0
  fi
  echo "✗ Non-dev main proposal is not a valid exact security projection." >&2
  exit 1
fi

echo "✗ PR source branch '${HEAD_REF}' may not merge directly into '${BASE_REF}'"
echo ""
echo "  WHY: Alpha Apps merge flow requires all code to land in 'dev' first."
echo "       Only 'dev' may target 'main' or 'staging'. Hotfix and release"
echo "       branches must flow: feature → dev → {staging, main}."
echo "       See the 'Merge Flow' section of Alpha Apps Git and GitHub Process."
echo ""
echo "  HOW: Retarget this PR to 'dev' in the GitHub UI (Edit → change base to 'dev'),"
echo "       or close this PR and open a new one:"
echo "         gh pr create --base dev --head '${HEAD_REF}'"
exit 1
