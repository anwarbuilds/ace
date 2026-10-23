#!/usr/bin/env bash
set -euo pipefail
umask 077

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
state_dir="${HOME}/.local/state/ace-discovery-parity"
mkdir -p "${state_dir}"
chmod 700 "${state_dir}"
touch "${state_dir}/monitor.log"
chmod 600 "${state_dir}/monitor.log"

backup="${state_dir}/crontab-before-monitor-$(date -u +%Y%m%dT%H%M%SZ)"
crontab -l > "${backup}" 2>/dev/null || :
chmod 600 "${backup}"
if rg -q -F 'compare-independent-discovery.sh' "${backup}"; then
  printf 'ACE discovery comparison monitor is already installed.\n'
  exit 0
fi

entry="*/15 * * * * ACE_COMPARISON_MIN_INTERVAL_MINUTES=240 /bin/bash ${project_dir}/deploy/oracle/compare-independent-discovery.sh 2026-10-23T15:45:00Z >> ${state_dir}/monitor.log 2>&1"
{
  cat "${backup}"
  printf '\n%s\n' "${entry}"
} | crontab -
printf 'Installed read-only comparison monitor. Previous crontab: %s\n' "${backup}"
