#!/usr/bin/env bash
set -euo pipefail
archive="actionlint_${ACTIONLINT_VERSION}_linux_amd64.tar.gz"
url="https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}/${archive}"
target_dir="${RUNNER_TEMP:-/tmp}/actionlint-${ACTIONLINT_VERSION}"
mkdir -p "${target_dir}"

if ! curl -fsSLo "${target_dir}/${archive}" "${url}"; then
  echo "✗ Failed to download actionlint ${ACTIONLINT_VERSION}."
  echo "  WHAT: curl could not download ${url}."
  echo "  WHY: ci-github-actions requires a pinned actionlint release for workflow validation."
  echo "  HOW: verify the release asset exists or update ACTIONLINT_VERSION and ACTIONLINT_SHA256 together."
  exit 1
fi

if ! echo "${ACTIONLINT_SHA256}  ${target_dir}/${archive}" | sha256sum -c -; then
  echo "✗ actionlint ${ACTIONLINT_VERSION} archive checksum mismatch."
  echo "  WHAT: downloaded archive did not match ACTIONLINT_SHA256."
  echo "  WHY: downloaded binaries must be verified before execution in shared CI."
  echo "  HOW: confirm the release asset is expected, then update ACTIONLINT_SHA256."
  exit 1
fi

if ! tar -xzf "${target_dir}/${archive}" -C "${target_dir}" actionlint; then
  echo "✗ Failed to extract actionlint ${ACTIONLINT_VERSION}."
  echo "  WHAT: tar could not extract the actionlint binary from ${archive}."
  echo "  WHY: ci-github-actions cannot validate workflows without actionlint."
  echo "  HOW: inspect the downloaded archive and release asset name."
  exit 1
fi

echo "executable=${target_dir}/actionlint" >> "${GITHUB_OUTPUT}"
