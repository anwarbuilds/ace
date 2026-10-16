# ACE on Oracle Cloud Always Free

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
5. Optional Resend credentials for alerts and an optional private Object
   Storage bucket for offsite backups.

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
time zone. Keep `ACE_AUTH=required`.

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

## Start and verify

```bash
docker compose -f deploy/oracle/compose.yaml up -d --build
docker compose -f deploy/oracle/compose.yaml ps
docker compose -f deploy/oracle/compose.yaml logs --tail=100 migrate api web scheduler caddy
curl -fsS "https://${ACE_DOMAIN}/healthz"
```

Open the site, sign in with the existing owner password, and confirm Pulls,
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

ACE requests only `openid email`. It accepts only the verified email of the
existing owner and binds the Google account subject on first success. Password
sign-in remains available for recovery.

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

## Cutover

Cutover is the only stage that briefly stops writes. On the old machine, stop
only the scheduler, take a final dump, restore it to the VM, run migrations,
run the Resume Studio bridge, compare inventories, and test the cloud UI. Start
the cloud scheduler only after parity succeeds. Leave the old database intact
for rollback. Never run both schedulers against separate writable databases
after cutover because they will diverge.
