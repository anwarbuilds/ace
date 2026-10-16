#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
backup_dir="${ACE_BACKUP_DIR:-${project_dir}/private-backups}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
filename="${backup_dir}/ace-${stamp}.dump.gz"
partial="${filename}.partial"

mkdir -p "${backup_dir}"
chmod 700 "${backup_dir}"
cd "${project_dir}"
trap 'rm -f "${partial}"' EXIT

docker compose -f deploy/oracle/compose.yaml exec -T postgres \
  pg_dump --format=custom --no-owner --no-acl \
  --username="${ACE_DB_USER}" "${ACE_DB_NAME}" | gzip -9 > "${partial}"
mv "${partial}" "${filename}"
chmod 600 "${filename}"

if [[ -n "${OCI_BACKUP_BUCKET:-}" ]]; then
  oci os object put \
    --bucket-name "${OCI_BACKUP_BUCKET}" \
    --name "$(basename "${filename}")" \
    --file "${filename}" \
    --force
fi

find "${backup_dir}" -type f -name 'ace-*.dump.gz' -mtime +14 -delete
trap - EXIT
printf 'backup written: %s\n' "${filename}"
