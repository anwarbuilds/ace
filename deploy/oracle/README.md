# ACE operations

The current application is the Wine and Rose platform on GitHub branch **`main`**, hosted at **https://ace.opik.net**. The local workspace is a standalone `/home/ubuntu/Documents/ace-next` clone. Production uses `/opt/ace` and the `oracle` Compose project.

The local legacy stack and independent-comparison cron have been retired under the owner's 2026-10-30 consolidation authorization. Its database volume and private recovery archives remain preserved. Do not restart it, enable ID-based replication, import its records into production or install comparison jobs as routine setup. See [consolidation and recovery](../../docs/operations/platform-consolidation-2026-10-30.md). Earlier migration procedures are retained in the [historical archive](../../docs/archive/oracle-migration-before-consolidation-20261030.md), not active instructions.

## Production topology

Caddy exposes ports 80/443 and forwards to Next.js, which proxies FastAPI. PostgreSQL and the discovery scheduler use the internal Docker network. The API owns the separately authorized Gmail monitor. Source code is baked into service images; changing checkout files or pushing Git changes does not deploy them.

Always use the repository-root environment file explicitly:

```bash
cd /opt/ace
docker compose --env-file .env -f deploy/oracle/compose.yaml ps
curl -fsS https://ace.opik.net/healthz
```

Only the current Caddyfile is bind-mounted from the checkout. Preserve its contents and inode when aligning source. Never overwrite a mounted configuration as an incidental branch operation. `.env` is private, mode 600; do not print its values or expanded Compose configuration.

## Source and running revisions

The owner-approved Inbox-to-Analytics release activated API/web at **`a48d71be3a33a6188e8fa96f748b4b78ecd19ef0`** on October 30, 2026 at 21:31 Pacific. Production main tracks origin/main and deliberately uses that exact tested source, an ancestor of merged PR #20. Later continuity documentation is not a new deployment.

API remains Inbox parser 15 and schema remains 0050. Scheduler source is still `fca4673033dc92833bbf217182738026f414bf3d`; scheduler, PostgreSQL, Caddy and exited migrate container identities were preserved. Full source, protected-row, public asset/auth and four-range read-only Analytics checks pass. These are dated verified observations, not instructions to rebuild services until version labels agree. `/healthz`'s frontend SHA identifies web, not API or scheduler. See [the completed release](../../docs/analytics/inbox-sync-review.md).

Private backup/rollback entry: `/opt/ace/private-backups/analytics-inbox-sync-20261031T0421Z/`. Its fresh backup passes gzip, catalog and full expansion without a restore drill. Actual prior API/web images are retained under `before-analytics-sync-20261031T0421Z` tags with a guarded image-only rollback. Do not restore database data as image rollback. The Gmail monitor waits 15 seconds after API startup; container health alone can precede its lease. Verify its later single lease and normal sync progress without starting a manual or historical check.

## Release procedure

A release, migration, production write, scheduler change or extension publication requires explicit approval for that specific operation. The consolidation authorization does not authorize any of them.

Before an approved release:

1. Review `ACE_NEXT_KNOWLEDGE.md`, current main and actual running images. Preserve newer integrated Inbox, discovery, auth and application work.
2. Record checkout status, service/container/image identities, schema, protected data and private configuration hashes. Inspect bind mounts.
3. Take a new consistent private backup with no retention pruning. Verify complete gzip integrity, PostgreSQL archive catalog and full expansion; use an isolated restore drill when appropriate. Retain exact rollback images. An archive list is not a restore drill.
4. Fetch main and fast-forward to the exact approved SHA only if tracked changes and mounted files are safe. Do not infer approval for newer source from approval for an older release.
5. Set `ACE_BUILD_SHA` to the full approved SHA and prepare only affected images. `prepare-release.sh` builds migrate/API/web but changes no containers; a schema-free release can instead build only its affected service images.
6. Activate only explicitly approved services. For a schema-free API/web release the scoped command is:

   ```bash
   docker compose --env-file .env -f deploy/oracle/compose.yaml up -d \
     --no-build --no-deps --wait --wait-timeout 180 api web
   ```

   A web-only release names only `web`. Do not trigger migrate, scheduler, PostgreSQL or Caddy through dependencies.
7. Verify exact running source/images, container health, public HTTPS, auth boundaries, served assets and protected data. Confirm all unrelated services and configuration remained unchanged. Report concurrent owner activity separately from cutover preservation.

Never run Compose `down`, remove volumes or restore old data as an application rollback. Roll back only the affected image after checking its retained identity; data compensation is a separate reviewed operation protecting later owner activity. Keep historical Gmail rechecks disabled and the stopped parser-7 operator stopped.

SSH access uses the owner's configured key and host. With `ssh ... 'bash -s'`, redirect commands that need no input from `/dev/null`; otherwise `compose exec -T` can consume the remaining script. Private evidence uses umask 077; public source/assets need normal read permissions.

## Backups

`backup.sh` and the supplied systemd service/timer support production PostgreSQL backups. The script performs retention cleanup, so do not use it for a preservation-only checkpoint. The existing production backup timer is unchanged by consolidation. Optional OCI uploads require privately configured credentials and a dedicated private bucket with an approved lifecycle policy; offsite storage was not configured in the last recorded production state.

A backup stored only on the production VM is vulnerable to VM loss. Verify gzip integrity, catalog and a real isolated restore regularly. Do not restore into production as a test. Keep dumps, manifests with owner records and rollback material outside public Git.

## Authentication and configuration

Use [the production example](.env.example), never real values in documentation. Production uses `ACE_AUTH=required`; preserve the current owner account. Google sign-in and Gmail read-only OAuth have different callbacks and credentials. Do not replace working OAuth clients or infer Gmail authorization from Google sign-in. Email-code login/recovery depends on actual mail configuration; a template's setting does not prove what the running service uses.

## Local persistent development

Use a distinct Compose project and an empty development volume. The retired `ace` project/volume is recovery material, not the development database. From a fresh main clone with a local `.env` copied from the example:

```bash
docker compose -p ace-dev --env-file .env build migrate api web
docker compose -p ace-dev --env-file .env up -d postgres migrate api web
curl -fsS http://127.0.0.1:8000/healthz
curl -fsS http://127.0.0.1:3000/healthz
```

These commands are for a new local development stack; they were not run against either retained or production data during consolidation. A scheduler is a separate deliberate local step. The [SQLite demo](../../README.md#local-setup) needs no containers or external polling and is the verified review path.

## Recovery and historical tooling

Keep `legacy-main-final` and the private `all-history.bundle`, Git database archive, workspace/configuration archive, final legacy dump and named recovery tags. Follow [recovery instructions](../../docs/operations/platform-consolidation-2026-10-30.md#recovery) in a separate directory/database. Historical comparison, installer and replica scripts remain preserved for forensic recovery; their presence is not authorization to run them.
