#!/usr/bin/env bash
set -euo pipefail

# The updater needs a push token. Prefer an injected secret, otherwise use the
# authenticated repository URL configured for this local checkout.
if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  remote_url="$(git config --get remote.origin.url || true)"
  if [[ "$remote_url" =~ ^https://[^:]+:([^@]+)@github\.com/ ]]; then
    export GITHUB_TOKEN="${BASH_REMATCH[1]}"
  fi
fi

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "GITHUB_TOKEN is not available" >&2
  exit 1
fi

exec python3 scripts/update_timeline.py
