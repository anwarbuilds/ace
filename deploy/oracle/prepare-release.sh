#!/bin/sh
set -eu

cd "$(dirname "$0")/../.."

if [ -n "$(git status --porcelain --untracked-files=no -- Dockerfile compose.yaml web backend deploy scripts)" ]; then
  echo "Release files have local changes. Commit the release before building." >&2
  exit 1
fi

ACE_BUILD_SHA="$(git rev-parse HEAD)"
export ACE_BUILD_SHA

docker compose --env-file .env -f deploy/oracle/compose.yaml build migrate api web

echo "Prepared ACE images for commit ${ACE_BUILD_SHA}."
echo "No production containers were changed."
