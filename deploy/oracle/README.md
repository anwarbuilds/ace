# ACE on Oracle Cloud Always Free

Current production status, 2026-10-23: the owner requires both the legacy and
Oracle schedulers to run for independent comparison. They write to separate
databases. The laptop cross-database replica cron is disabled because numeric
job IDs have diverged; do not turn it back on without reconciliation. The
parallel-monitoring and cutover steps below describe earlier migration modes,
not the current operating state. See `ACE_NEXT_KNOWLEDGE.md` for current rules.

This deployment keeps PostgreSQL, FastAPI, Next.js and the scheduler on one
Ampere A1 VM. Caddy is the only public container. PostgreSQL and FastAPI have
no public host ports. Docker restarts the scheduler after a process failure or
VM reboot, so pulling no longer depends on a laptop being awake.

Oracle can reclaim an idle Always Free compute instance. ACE's scheduler is
normally active, but Always Free is a service limit rather than a contractual
uptime guarantee. Keep verified backups outside the VM.

## Inputs the owner provides

1. An Oracle Cloud account with an Always Free eligible home region.
2. A domain or subdomain whose DNS A record points to the VM public IP.
3. A Google Cloud Web application OAuth client, after the HTTPS domain works.
4. The existing ACE database dump, transferred privately and never committed.
5. Resend credentials for password sign-in and recovery codes. A private
   Object Storage bucket for offsite backups remains optional.

Put secrets directly into `.env` on the VM. Do not paste them into an issue,
chat, commit or shell history.

## Provision the VM

Create an Always Free eligible Ampere A1 Ubuntu VM. Two OCPUs and 12 GB RAM fit
within Oracle's documented monthly Always Free A1 allowance. In the subnet
security list allow TCP 22 from your own IP and TCP 80 and 443 from the
internet. Do not open 3000, 5432 or 8000.

Install Docker Engine and its Compose plugin from Docker's official Ubuntu
repository. Add your login user to the `docker` group, sign out, and sign back
in. Clone the repository into `/opt/ace` or your home directory.

```bash
cd /opt/ace
cp deploy/oracle/.env.example .env
chmod 600 .env
```

Edit `.env`. Generate independent database and setup secrets with:

```bash
openssl rand -hex 32
```

Set `ACE_DOMAIN`, `PUBLIC_BASE_URL`, `WEB_BASE_URL`, database values and the
time zone. Keep `ACE_AUTH=required` and `REQUIRE_LOGIN_EMAIL_CODE=true`. Set
`RESEND_API_KEY` and a verified `MAIL_FROM` address before testing password
sign-in. The deployment intentionally refuses password sign-in when a code
cannot be delivered.

## Restore a private copy and verify it

First capture the source inventory and a consistent custom-format dump on the
old machine. This is read-only and does not stop the old scheduler.

```bash
cd /home/ubuntu/Documents/ace-next
set -a
. /home/ubuntu/Documents/ace/.env
set +a
.venv/bin/python -m backend.scripts.data_inventory \
  --output /tmp/ace-before.json

cd /home/ubuntu/Documents/ace
docker compose exec -T postgres pg_dump --format=custom --no-owner --no-acl \
  -U ace ace > /tmp/ace-production.dump
gzip -9 /tmp/ace-production.dump
chmod 600 /tmp/ace-production.dump.gz /tmp/ace-before.json
```

The inventory runs from the new checkout against the old PostgreSQL host port.
It reads aggregate counts only.

Copy both files to the VM using `scp`. Start only PostgreSQL, restore into the
empty database, then run migrations.

```bash
cd /opt/ace
set -a
. ./.env
set +a
docker compose -f deploy/oracle/compose.yaml up -d postgres
gzip -dc /path/to/ace-production.dump.gz | docker compose \
  -f deploy/oracle/compose.yaml exec -T postgres \
  pg_restore --clean --if-exists --no-owner --no-acl \
  -U "$ACE_DB_USER" -d "$ACE_DB_NAME"
docker compose -f deploy/oracle/compose.yaml run --rm migrate
docker compose -f deploy/oracle/compose.yaml run --rm api \
  python -m backend.scripts.backfill_resume_studio --apply
docker compose -f deploy/oracle/compose.yaml run --rm api \
  python -m backend.scripts.data_inventory --compare /path/to/ace-before.json
```

The Resume Studio bridge adds documents, versions and suggested facts, so its
three table counts are expected to be higher after the bridge. Compare the
inventory immediately after restore and migrations first, then run the bridge
and record a second inventory.

## Owner account after restore

The restored production database already contains the owner account together
with the 755 tracked applications. Do not create another account. Sign in with
the existing owner email and password. If the password is unknown, reset that
same owner from a hidden prompt after the restore:

If the desired daily login email differs from the restored owner email, rename
the existing owner first. This preserves all product data, clears the previous
Google binding and signs out earlier browser sessions:

```bash
cd /opt/ace
docker compose -f deploy/oracle/compose.yaml run --rm api \
  python -m backend.scripts.set_owner_email YOUR_DAILY_EMAIL
```

Then reset the password only when needed:

```bash
cd /opt/ace
docker compose -f deploy/oracle/compose.yaml run --rm api \
  python -m backend.scripts.create_owner YOUR_OWNER_EMAIL --reset
```

The password is entered twice without appearing in shell history or logs. If a
restored database unexpectedly reports that no owner exists, stop and verify
the dump and restore before creating anything.

The migration inventory must show 708 `applied_job_marks` and 47
`external_applications`, for 755 tracked applications in total. The
Applications page combines those same two sources.

## Start and verify

Build release images with the exact Git commit embedded in the web image and
response headers. This command prepares images only and does not replace any
running production container:

```bash
deploy/oracle/prepare-release.sh
```

After reviewing the prepared release, start the approved commit with the same
identifier:

```bash
export ACE_BUILD_SHA="$(git rev-parse HEAD)"
docker compose -f deploy/oracle/compose.yaml up -d --build \
  postgres migrate api web caddy
docker compose -f deploy/oracle/compose.yaml ps
docker compose -f deploy/oracle/compose.yaml logs --tail=100 migrate api web caddy
curl -fsS "https://${ACE_DOMAIN}/healthz"
```

The health response and every Next.js response include the frontend commit.
Compare it with `git rev-parse HEAD` before accepting the deployment.

Open the site, sign in with the existing owner password and the code delivered
to the owner's email, and confirm Pulls,
Applications, Analytics, Answers, Resume Studio and Settings show the expected
real records. Keep the old scheduler running during this rehearsal so the old
database remains authoritative.

## Google sign-in

In Google Cloud create an OAuth 2.0 client with application type `Web
application`. Add this exact authorized redirect URI:

```text
https://YOUR_DOMAIN/api/auth/google/callback
```

Add the client ID and secret to `.env`, set `GOOGLE_REDIRECT_URI` to that exact
URL, and recreate the API container:

```bash
docker compose -f deploy/oracle/compose.yaml up -d --force-recreate api
```

ACE requests only `openid email profile`. It accepts only the verified email of the
existing owner and binds the Google account subject on first success. Password
sign-in and password recovery require a one-time email code. Google sign-in
uses Google's verified email claim and does not send a second code.

## Backups

Run one backup manually and test that it is nonempty:

```bash
cd /opt/ace
set -a
. ./.env
set +a
deploy/oracle/backup.sh
ls -lh private-backups
```

Set `OCI_BACKUP_BUCKET` only for a private Object Storage bucket after the OCI
CLI is configured. Use a dedicated bucket with versioning disabled. Install the
14-day deletion policy before the first upload. This command replaces any
existing lifecycle policy, which is why the bucket must be dedicated to ACE.

```bash
oci os object-lifecycle-policy put \
  --bucket-name "$OCI_BACKUP_BUCKET" \
  --items file://deploy/oracle/object-lifecycle-items.json \
  --force
```

The backup script also measures existing ACE objects before every upload and
refuses the upload if it would cross the default 15 GiB ceiling. This leaves
headroom within Oracle's documented 20 GB Always Free Object Storage allowance.
If ACE is installed at `/opt/ace` under the `ubuntu` user, install the included
daily systemd timer:

```bash
sudo cp deploy/oracle/ace-backup.service /etc/systemd/system/
sudo cp deploy/oracle/ace-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ace-backup.timer
systemctl list-timers ace-backup.timer
```

Perform a restore drill into a separate database before cutover and monthly
afterward. A backup that has never been restored is unverified.

## Historical replicated monitoring with the legacy scheduler

During the owner comparison period, keep the legacy scheduler as the only
discovery writer and keep the cloud scheduler stopped. The cloud API can use a
separate migrated database while `sync-legacy-replica.sh` copies discovery
results from the legacy database. User-managed application data is copied back
to the legacy database first, with the newest `updated_at` value winning, so
marks and application updates made through either interface remain consistent.

Install the sync from the legacy host account that can access the local Docker
socket and the cloud SSH key:

```bash
mkdir -p "$HOME/.local/state/ace-legacy-replica"
chmod 700 "$HOME/.local/state/ace-legacy-replica"
(crontab -l 2>/dev/null; printf '%s\n' \
  '* * * * * /home/ubuntu/Documents/ace-next/deploy/oracle/sync-legacy-replica.sh >> /home/ubuntu/.local/state/ace-legacy-replica/cron.log 2>&1') \
  | sort -u | crontab -
```

The cron entry attempts a sync every minute. `flock` permits only one active
transaction, so a large polling batch can take longer without overlapping the
next run. The cursor advances only after the cloud transaction succeeds. A
five-minute replay overlap covers source transactions that commit just after a
snapshot while carrying slightly earlier timestamps. All replayed writes are
idempotent.

Check the most recent successful boundary and log with:

```bash
cat "$HOME/.local/state/ace-legacy-replica/cursor"
tail -n 20 "$HOME/.local/state/ace-legacy-replica/cron.log"
```

`replica-parity.psql` hashes the latest completed pull sessions, their complete
job identities, qualifying opportunities, enabled sources and user-managed
application data. Pass the successful cursor as `cutoff` when running it
against both databases. Compare the output lines exactly. Full mutable job and
evaluation hashes can temporarily differ while the legacy scheduler changes
`last_seen_at` or `evaluated_at` after the completed replica snapshot. The job
identity and qualifying-job hashes prove that the companies and opportunities
shown for settled pulls are the same.

Do not start the cloud scheduler during this monitoring mode. Removing the
cron entry stops replication without changing either database.

## Historical one-writer cutover procedure

Cutover is the only stage that briefly stops writes. On the old machine, stop
only the scheduler, take a final dump, restore it to the VM, run migrations,
run the Resume Studio bridge, compare inventories, and test the cloud UI. Start
the cloud scheduler only after parity succeeds. Leave the old database intact
for rollback. This procedure assumed one discovery writer. The current
owner-requested comparison runs both schedulers independently with the
cross-database replica disabled; their databases will diverge by design.

Start the cloud scheduler only at that final step:

```bash
docker compose -f deploy/oracle/compose.yaml up -d --build scheduler
docker compose -f deploy/oracle/compose.yaml logs --tail=100 scheduler
```
