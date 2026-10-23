#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
state_dir="${ACE_REPLICA_STATE_DIR:-${HOME}/.local/state/ace-legacy-replica}"
remote_host="${ACE_REPLICA_REMOTE:-ubuntu@161.153.89.170}"
ssh_key="${ACE_REPLICA_SSH_KEY:-${HOME}/.ssh/ace_oracle}"
legacy_container="${ACE_REPLICA_LEGACY_CONTAINER:-ace-scheduler-1}"
cloud_container="${ACE_REPLICA_CLOUD_CONTAINER:-oracle-api-1}"
replica_script="${project_dir}/backend/scripts/legacy_replica.py"
remote_state="/home/ubuntu/.local/state/ace-legacy-replica"
cursor_file="${state_dir}/cursor"
cloud_user_bundle="${state_dir}/cloud-user-data.jsonl.gz"
legacy_bundle="${state_dir}/legacy-delta.jsonl.gz"
user_tables="job_marks,external_applications,application_answers,history_entries"
overlap_minutes="${ACE_REPLICA_OVERLAP_MINUTES:-5}"
started_epoch="$(date +%s)"
phase="initialization"

report_exit() {
  status="$?"
  if [[ "${status}" -ne 0 ]]; then
    printf 'ACE legacy replica failed during %s with exit status %s\n' \
      "${phase}" "${status}" >&2
  fi
}
trap report_exit EXIT

mkdir -p "${state_dir}"
chmod 700 "${state_dir}"
exec 9>"${state_dir}/sync.lock"
flock -n 9 || exit 0

until_time="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [[ -s "${cursor_file}" ]]; then
  # A poll transaction can commit just after an export while carrying a
  # first-seen timestamp from just before that export. Replaying a short
  # overlap makes that boundary safe; all writes below are idempotent upserts.
  since_time="$(
    date -u -d "$(cat "${cursor_file}") - ${overlap_minutes} minutes" \
      +%Y-%m-%dT%H:%M:%SZ
  )"
else
  since_time="$(date -u -d '2 hours ago' +%Y-%m-%dT%H:%M:%SZ)"
fi
ssh_args=(
  -o BatchMode=yes
  -o ConnectTimeout=15
  -i "${ssh_key}"
)

# This historical ID-based replica is safe only while legacy is the sole
# discovery writer. Independent schedulers allocate overlapping job IDs.
# Fail closed if Oracle discovery is active, including on a manual invocation.
phase="independent-writer safety guard"
cloud_scheduler_running="$(
  ssh "${ssh_args[@]}" "${remote_host}" \
    "docker inspect -f '{{.State.Running}}' '${ACE_REPLICA_CLOUD_SCHEDULER:-oracle-scheduler-1}'"
)"
if [[ "${cloud_scheduler_running}" != "false" ]]; then
  printf 'Refusing ID-based replica while Oracle scheduler is active or unknown.\n' >&2
  exit 2
fi
printf 'ACE legacy replica starting: %s through %s\n' \
  "${since_time}" "${until_time}"

ssh "${ssh_args[@]}" "${remote_host}" \
  "mkdir -p '${remote_state}' && chmod 700 '${remote_state}'"
scp "${ssh_args[@]}" "${replica_script}" \
  "${remote_host}:${remote_state}/legacy_replica.py"

# Bring user-managed application data back first. Timestamp guards make the
# most recent edit win when either interface was used between sync runs.
phase="cloud user-data export"
ssh "${ssh_args[@]}" "${remote_host}" \
  "docker cp '${remote_state}/legacy_replica.py' '${cloud_container}:/tmp/legacy_replica.py' && \
   docker exec '${cloud_container}' python /tmp/legacy_replica.py export \
     --since '${since_time}' --until '${until_time}' \
     --tables '${user_tables}' \
     --output /tmp/cloud-user-data.jsonl.gz && \
   docker cp '${cloud_container}:/tmp/cloud-user-data.jsonl.gz' \
     '${remote_state}/cloud-user-data.jsonl.gz'"
scp "${ssh_args[@]}" \
  "${remote_host}:${remote_state}/cloud-user-data.jsonl.gz" \
  "${cloud_user_bundle}"
chmod 600 "${cloud_user_bundle}"
docker cp "${replica_script}" "${legacy_container}:/tmp/legacy_replica.py"
docker cp "${cloud_user_bundle}" \
  "${legacy_container}:/tmp/cloud-user-data.jsonl.gz"
docker exec -u 0 "${legacy_container}" \
  chmod 644 /tmp/cloud-user-data.jsonl.gz
phase="legacy user-data apply"
docker exec "${legacy_container}" python /tmp/legacy_replica.py apply \
  --input /tmp/cloud-user-data.jsonl.gz

# Export discovery data from the only running scheduler, then apply the whole
# bundle to the cloud in one transaction. The cursor moves only after success.
phase="legacy discovery export"
docker exec "${legacy_container}" python /tmp/legacy_replica.py export \
  --since "${since_time}" --until "${until_time}" \
  --output /tmp/legacy-delta.jsonl.gz
docker cp "${legacy_container}:/tmp/legacy-delta.jsonl.gz" "${legacy_bundle}"
chmod 600 "${legacy_bundle}"
scp "${ssh_args[@]}" "${legacy_bundle}" \
  "${remote_host}:${remote_state}/legacy-delta.jsonl.gz"
phase="cloud discovery apply"
ssh "${ssh_args[@]}" "${remote_host}" \
  "docker cp '${remote_state}/legacy-delta.jsonl.gz' \
     '${cloud_container}:/tmp/legacy-delta.jsonl.gz' && \
   docker exec -u 0 '${cloud_container}' \
     chmod 644 /tmp/legacy-delta.jsonl.gz && \
   docker exec '${cloud_container}' python /tmp/legacy_replica.py apply \
     --input /tmp/legacy-delta.jsonl.gz"

cursor_tmp="${cursor_file}.tmp"
printf '%s\n' "${until_time}" > "${cursor_tmp}"
mv "${cursor_tmp}" "${cursor_file}"
chmod 600 "${cursor_file}"
duration="$(( $(date +%s) - started_epoch ))"
phase="complete"
printf 'ACE legacy replica synchronized through %s in %ss\n' \
  "${until_time}" "${duration}"
