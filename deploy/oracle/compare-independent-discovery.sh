#!/usr/bin/env bash
set -euo pipefail
umask 077

# Read-only comparison. It never invokes the historical database replica.
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
since="$(date -u -d "${1:-24 hours ago}" +%Y-%m-%dT%H:%M:%SZ)"
report_root="${ACE_COMPARISON_REPORT_DIR:-${project_dir}/private-reports}"
remote_host="${ACE_REPLICA_REMOTE:-ubuntu@161.153.89.170}"
ssh_key="${ACE_REPLICA_SSH_KEY:-${HOME}/.ssh/ace_oracle}"
legacy_container="${ACE_REPLICA_LEGACY_CONTAINER:-ace-scheduler-1}"
cloud_container="${ACE_REPLICA_CLOUD_CONTAINER:-oracle-api-1}"
remote_state="/home/ubuntu/.local/state/ace-discovery-parity"
snapshot_script="${project_dir}/backend/scripts/discovery_parity.py"
inventory_script="${project_dir}/backend/scripts/discovery_inventory.py"
ssh_args=(-o BatchMode=yes -o ConnectTimeout=15 -i "${ssh_key}")

mkdir -p "${report_root}"
chmod 700 "${report_root}"
exec 9>"${report_root}/.monitor.lock"
flock -n 9 || exit 0
minimum_minutes="${ACE_COMPARISON_MIN_INTERVAL_MINUTES:-0}"
if [[ ! "${minimum_minutes}" =~ ^[0-9]+$ ]]; then
  printf 'ACE_COMPARISON_MIN_INTERVAL_MINUTES must be a nonnegative integer\n' >&2
  exit 2
fi
if [[ "${minimum_minutes}" != 0 && -f "${report_root}/latest/report.json" ]]; then
  last_run="$(stat -c %Y "${report_root}/latest/report.json")"
  if (( $(date +%s) - last_run < minimum_minutes * 60 )); then
    exit 0
  fi
fi
run_id="$(date -u +%Y%m%dT%H%M%SZ)"
report_dir="${report_root}/${run_id}"
mkdir -p "${report_dir}"
chmod 700 "${report_dir}"

cleanup() {
  docker exec -u 0 "${legacy_container}" rm -f \
    "/tmp/ace-comparison-${run_id}-snapshot.gz" \
    "/tmp/ace-comparison-${run_id}-inventory.gz" >/dev/null 2>&1 || true
  ssh "${ssh_args[@]}" "${remote_host}" \
    "docker exec -u 0 '${cloud_container}' rm -f \
      '/tmp/ace-comparison-${run_id}-snapshot.gz' \
      '/tmp/ace-comparison-${run_id}-inventory.gz'; \
     rm -f '${remote_state}/${run_id}-snapshot.gz' \
       '${remote_state}/${run_id}-inventory.gz'" >/dev/null 2>&1 || true
}
trap cleanup EXIT

printf 'Exporting independent discovery snapshots since %s\n' "${since}"
docker exec -i "${legacy_container}" python - export \
  --since "${since}" \
  --output "/tmp/ace-comparison-${run_id}-snapshot.gz" \
  < "${snapshot_script}"
docker exec -i "${legacy_container}" python - export \
  --output "/tmp/ace-comparison-${run_id}-inventory.gz" \
  < "${inventory_script}"
docker cp "${legacy_container}:/tmp/ace-comparison-${run_id}-snapshot.gz" \
  "${report_dir}/legacy-snapshot.gz" >/dev/null
docker cp "${legacy_container}:/tmp/ace-comparison-${run_id}-inventory.gz" \
  "${report_dir}/legacy-inventory.gz" >/dev/null

ssh "${ssh_args[@]}" "${remote_host}" \
  "mkdir -p '${remote_state}' && chmod 700 '${remote_state}'"
ssh "${ssh_args[@]}" "${remote_host}" \
  "docker exec -i '${cloud_container}' python - export \
     --since '${since}' \
     --output '/tmp/ace-comparison-${run_id}-snapshot.gz'" \
  < "${snapshot_script}"
ssh "${ssh_args[@]}" "${remote_host}" \
  "docker exec -i '${cloud_container}' python - export \
     --output '/tmp/ace-comparison-${run_id}-inventory.gz'" \
  < "${inventory_script}"
ssh "${ssh_args[@]}" "${remote_host}" \
  "docker cp '${cloud_container}:/tmp/ace-comparison-${run_id}-snapshot.gz' \
     '${remote_state}/${run_id}-snapshot.gz' && \
   docker cp '${cloud_container}:/tmp/ace-comparison-${run_id}-inventory.gz' \
     '${remote_state}/${run_id}-inventory.gz' && \
   chmod 600 '${remote_state}/${run_id}-snapshot.gz' \
     '${remote_state}/${run_id}-inventory.gz'"
scp "${ssh_args[@]}" \
  "${remote_host}:${remote_state}/${run_id}-snapshot.gz" \
  "${report_dir}/cloud-snapshot.gz" >/dev/null
scp "${ssh_args[@]}" \
  "${remote_host}:${remote_state}/${run_id}-inventory.gz" \
  "${report_dir}/cloud-inventory.gz" >/dev/null
chmod 600 "${report_dir}"/*

python_bin="${project_dir}/.venv/bin/python"
if [[ ! -x "${python_bin}" ]]; then
  python_bin="python3"
fi
cd "${project_dir}"
"${python_bin}" -m backend.scripts.discovery_parity compare \
  --legacy-snapshot "${report_dir}/legacy-snapshot.gz" \
  --cloud-snapshot "${report_dir}/cloud-snapshot.gz" \
  --legacy-inventory "${report_dir}/legacy-inventory.gz" \
  --cloud-inventory "${report_dir}/cloud-inventory.gz" \
  --json-output "${report_dir}/report.json" \
  --markdown-output "${report_dir}/report.md"

# Keep the complete comparison but discard bulky transfer inputs after a
# successful report. Each later run takes fresh database snapshots.
rm -f "${report_dir}/legacy-snapshot.gz" \
  "${report_dir}/cloud-snapshot.gz" \
  "${report_dir}/legacy-inventory.gz" \
  "${report_dir}/cloud-inventory.gz"
ln -sfn "${run_id}" "${report_root}/latest"
