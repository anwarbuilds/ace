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
  max_remote_bytes="${ACE_BACKUP_MAX_REMOTE_BYTES:-16106127360}"
  stored_bytes="$(
    oci os object list \
      --bucket-name "${OCI_BACKUP_BUCKET}" \
      --all \
      --query 'sum(data[].size)' \
      --raw-output
  )"
  [[ "${stored_bytes}" == "null" ]] && stored_bytes=0
  local_bytes="$(stat -c %s "${filename}")"
  if [[ ! "${stored_bytes}" =~ ^[0-9]+$ || ! "${max_remote_bytes}" =~ ^[0-9]+$ ]]; then
    printf 'remote upload skipped: backup byte totals were not numeric\n' >&2
    exit 1
  fi
  if (( stored_bytes + local_bytes > max_remote_bytes )); then
    printf 'remote upload skipped: ACE backup ceiling would be exceeded\n' >&2
  else
    oci os object put \
      --bucket-name "${OCI_BACKUP_BUCKET}" \
      --name "$(basename "${filename}")" \
      --file "${filename}" \
      --force
  fi
fi

find "${backup_dir}" -type f -name 'ace-*.dump.gz' -mtime +14 -delete
trap - EXIT
printf 'backup written: %s\n' "${filename}"
