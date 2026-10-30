# Platform consolidation and recovery, 2026-10-30

The owner explicitly authorized branch promotion, recoverable Git/workspace
cleanup, local legacy retirement and a standalone workspace replacement. This
operation changed no application runtime source or production data. No deployment,
image pull/build/recreation, migration, scheduler operation on production, email
reclassification, application-status change or extension publication was authorized
or performed.

## Source and branch outcome

GitHub `main` is the default and retains the Wine Rose history previously named
`wine-rose-platform`, starting from `98b112a1d13ffd695be9efc1e2d6dd5e90758536`.
PR #19's reviewed merge and production notes were already integrated. Old main
was archived as remote tag `legacy-main-final` at
`a3c9449370b7ca070c3bad5d5fc68876eb1e6ccb`, verified before deletion. The temporary
default was Wine Rose, old main was removed, then Wine Rose was renamed main.
An immediate API assertion raced GitHub's rename completion; independent API and
Git-protocol checks then confirmed the intended default and exact tip. No force-push.

There were 21 original remote branches total. Nineteen named obsolete development
branches were deleted atomically after immediately verifying each exact tip and
its independently recoverable archive. The old main name was removed separately
during promotion; Wine Rose was renamed, not discarded. Only main remains as a
remote development branch. No open PR existed, and both branch protections and
rulesets were absent before and after; no protection was silently dropped.
CI already filtered main, so no workflow assertions or filters needed weakening.

Legacy main's bounded resume scoring was already present in canonical source;
no runtime code was merged. Only missing scheduler-incident and corrected
Greenhouse relisting lessons were carried into the relevant knowledge topics.
Historical release branch names remain in dated records. The old handoff and
migration runbook were archived, and active instructions/README were rewritten.

## Private preservation

Private recovery root, outside both former repository folders:

```text
/home/ubuntu/ace-private-backups/consolidation-20261030T170532Z/
```

The root is mode 700. Private evidence/configuration files remain restricted.
Nothing in this private directory was published. Key artifacts:

| Artifact | Recovery purpose |
| --- | --- |
| `all-history.bundle` | Original refs, named recovery tags, stash parents and reflog/unreferenced commits |
| `shared-git.tar.gz` | Exact original Git database including worktree metadata/reflogs |
| `workspaces-private.tar.gz` | Working files, valuable ignored/untracked files, design and private release evidence; regenerable caches excluded |
| `refs-before.txt`, `worktrees-before.txt`, `recovery-tags.txt` | Original branch names, exact tips and layout |
| `independent-recovery.git`, `git-recovery-proof.json` | Independent bundle clone/fsck and recovery proof |
| `workspace-snapshots/`, `retired-shared.git` | Original folders retained privately as inert snapshots; old linked Git pointers removed |
| `legacy-images.tar.gz` | All six exact legacy images, saved privately and checked against their configuration/image hashes |
| `legacy-final.dump.gz`, catalog/checksum/restore proof | Final frozen legacy PostgreSQL backup, verified by actual isolated restore |
| `legacy-archive-only-comparison.json` | Private stable-identity comparison; differing older owner states remain archive-only |
| `local-containers-before.json`, container-private temporary files | Exact original service/config/image recovery material |
| `crontab-before.txt`, `retired-comparison-jobs.txt` | Recoverable comparison job configuration |
| `production-before.json`, `production-after.json`, preservation proof | Exact unchanged production service/configuration evidence |
| `restored-private-files.json`, local validation and HTTP proofs | Hashed private file restoration and fictional verification evidence |

Git recovery verified all 63 original refs, the live stash and 334 reflog or
otherwise unreferenced commits in an independent Git database without alternates.
Named `recovery-20261030/*` tags are also retained locally in standalone ace-next,
including `recovery-20261030/stash`, but are not published. Do not push all tags.
The bundle, raw Git archive and original workspace snapshots provide independent
recovery paths. Final checksums are in `SHA256SUMS`.

## Local legacy retirement

All six targets were verified as local Compose project `ace`, working directory
`/home/ubuntu/Documents/ace`, with exact IDs/images/mounts recorded privately:
`ace-web-1`, `ace-scheduler-1`, `ace-postgres-1`, `ace-migrate-1`,
`ace-backfill-v39` and `ace-notification-worker-1`. Production project `oracle`
is on the VM and was not a deletion target.

Container-only transfer evidence was copied privately. Only the identified
legacy writers and comparison cron were stopped. The final dump was
507,655,165 bytes and passed complete gzip integrity and archive-catalog checks.
A newly named isolated local database was restored with exit-on-error; every one
of 28 table counts and twelve protected table hashes matched, as did schema
0040. Only that temporary verification database was dropped. The original
legacy database records were not changed by the retirement.

After those checks the six legacy containers were removed without `-v`.
**Named volume `ace_ace_postgres_data` and exact `ace-recovery:*` images remain.**
Keep them for recovery until the owner explicitly approves a retention decision;
there is no automatic deletion date. No production volume or service was removed.
The single fifteen-minute comparison cron is removed; old replication remains off.

Applications were compared by `(source, source_account, external_id)`, external
history by its recorded match key, resumes/documents by content hash, and other
owner records by their documented semantic keys. No legacy-only application or
resume identity was found at the snapshot. Older differing states and the entire
legacy discovery corpus remain archive-only. This is a bounded identity comparison,
not a claim of universal semantic equivalence; no database records were transferred.
Legacy schema had no Gmail/event ledger comparable to current Inbox decisions.

## Standalone workspace

A fresh GitHub clone was prepared, dependencies installed independently and its
source verified before swapping it to `/home/ubuntu/Documents/ace-next`. Its own
`.git` directory/common dir contains no alternates, linked-worktree file or
dependency on `~/Documents/ace/.git`. Main is its sole active local branch,
tracking origin/main, and origin/HEAD points to main. The old shared layout's
29 local branches and live stash were removed only after recovery verification.
Original locations are retained under private inert snapshots, not live checkouts.

1,415 private ignored files were restored with hashes, including release evidence
and design references. Registered nested worktrees were excluded from the final
checkout because their complete contents are preserved in recovery snapshots.
Active `.env` uses example development values; the exact old configuration is
retained privately as ignored `.env.legacy-retired` (mode 600), not auto-loaded.
The extension path stays `ace-next/extension`; all twelve tracked extension files
are byte-identical. No Chrome reload or publication occurred.

## Production before and after

Checkout `/opt/ace` was renamed to main and now tracks origin/main; its commit
stays `fca4673033dc92833bbf217182738026f414bf3d`. Its old single-branch fetch
refspec was corrected. No checkout source or mounted Caddyfile was replaced.
The source checkout intentionally differs from newer main and the API/web images.

- API image label and reader source identify `b03d251047f531ba60a75812d9c088b395a6d943`, parser 15.
- Web image label, environment and public health identify `4116aa01dd5cdd3a6ea3d707017a7d9f7fad5bd7`.
- Scheduler source matched all 181 tracked runtime files at `fca4673033dc92833bbf217182738026f414bf3d`.
- Database schema remains 0050, read with enforced read-only SQL.

| Service | Unchanged full container ID | Unchanged image ID |
| --- | --- | --- |
| oracle-api-1 | `fd015f29f5b86eea526a0799b4e308b1dd9eaa5aeb36128e23fcde451b98f3cc` | `sha256:deab872ba15f22e883e669df4769d3e7e55cf3f723620c783ce8dc07f3df3e6a` |
| oracle-scheduler-1 | `6f84682b9c7edcaf9ffd19518d89e9bc581ee9521cbef5e516e2f0a09be2f741` | `sha256:1d26f321ba81f44d0c585f97471ebfa6804703fda5e8f7cc9aac61e720113948` |
| oracle-web-1 | `c836d464343c502450640c5c2e78d674b2907d89ceb55f8af61b7d79fde2e283` | `sha256:049f72137189a1f497aefb12105dde00ac0f9153824f14357e2af1a8cff971e4` |
| oracle-migrate-1 | `ddf4c5f62b1cab34d29ed3e4c8e24caf09c7305ff2a30dede808b02d24e53634` | `sha256:989de66057e6e3f7b204684d8cef550e41cbc1303f4589b6460aacb94a128ff1` |
| oracle-caddy-1 | `103bf7e93f034738c216596d9d1fe549d1d6c89a33c0a00eb629363cfe1d8bf9` | `sha256:d8542f48d34a9cf4e4c11a478865229840e87e4c96ea3f439101f31a5d35f75f` |
| oracle-postgres-1 | `10f240f0d86ba1445a74f4fe281947f2bdaf1d6f2fb3ec85584ddfe34bbf0530` | `sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea` |

All container identities, images, start times, mounts, configuration hashes and
sampled API source hashes matched exactly. `.env`, Compose and the mounted
Caddyfile are unchanged; public website/API health passed. No signed-in
production browser test or frozen production-data interval is claimed. Normal
production discovery/owner activity continues independently of this cleanup.

## Validation

A fresh Python 3.12.12 environment and locked npm install succeeded. Local Node was 24.14.1; CI uses Node 22. Focused fictional
backend, matcher/Memory, extension/company/Inbox DOM and Analytics calculations,
route-type generation, TypeScript, lint, production web build and demo seed all
passed. Fourteen fictional signed-in local HTTP routes passed; no browser ran.
The final repository has no backend/web/extension/workflow/Compose runtime diff
from the reviewed platform baseline. README links/anchors, commands and source
claims are checked separately, with private-file exclusion and whitespace review.

The last pre-consolidation full CI run was
[41075615441](https://github.com/anwarbuilds/ace/actions/runs/41075615441): backend/web
passed, 22 extension-browser cases failed, later application browsers skipped.
Dedicated Inbox [41075606426](https://github.com/anwarbuilds/ace/actions/runs/41075606426)
passed. Main pushes run the unchanged CI assertions. Exact consolidation run
results are recorded privately and reported to the owner; the
[current workflow](https://github.com/anwarbuilds/ace/actions/workflows/ci.yml)
remains the authority. Do not equate these local checks with production
classification accuracy or complete mailbox/source coverage.

Consolidation full CI [41140888866](https://github.com/anwarbuilds/ace/actions/runs/41140888866)
on documentation source `a8d2c5d549f552fcfcaaca91c91a0d665ab73a60` completed:
backend and web passed; extension browsers had **25 pass / 22 fail**. Exact
traceback-name comparison with PR #19 found zero new or resolved failed names.
Later application-browser steps were skipped. Overall CI remains red; no test
was disabled or weakened. The final follow-up records these results and the
verified six-image private backup without changing runtime/test/workflow source.

## Recovery

Do recovery work in a new private directory. Do not overwrite current main,
restore over production, reconnect an old `.git` pointer or restart historical
jobs as a test. Keep the original archive files unchanged.

```bash
# Replace the destination with a new private directory.
umask 077
git clone /home/ubuntu/ace-private-backups/consolidation-20261030T170532Z/all-history.bundle /tmp/ace-recovery
cd /tmp/ace-recovery
git fsck --full
git show legacy-main-final
git show recovery-20261030/extension-context-reuse-20261026
git show recovery-20261030/backup/local-before-sync
git show recovery-20261030/stash
```

Use the manifests to select an exact former branch tip. The stash tag preserves
the stash commit and its index/untracked parents where present; inspect those
before an explicit apply into a separate clean recovery branch. The final live
workspace has no active stash. A bundle clone defaults to the archived HEAD;
choose the exact recovery tag instead of treating it as current development.

Check `SHA256SUMS`, then list private tar archives before extracting only the
needed files into another private directory. Restoring design/release evidence
must never put it in public Git. Original configuration is inactive by design.

For data recovery, inspect the private original container identities, images,
environment and volume manifest. Restore `legacy-final.dump.gz` only into a
newly named isolated database/container, with no production access and no
external scheduler/email writers. The original legacy volume remains available
but must not be attached as a writable production database. Never merge numeric
IDs between the two independent corpora. Recovery service activation is a
separate specific owner operation, not permission inherited from consolidation.

## Removed remote development branches

- `analytics-rebuild-20261027` at `d5c38dc760b247b99d485f42d8c3e3fbe5d5dffd` (incorporated)
- `company-logo-consistency-20261026` at `2a2982e7225ffc223567110fb023ea85deeb627f` (incorporated)
- `company-logo-tenants-20261026` at `e04dffa9ccfdee874b8cdce463747a952e91a5e6` (incorporated)
- `extension-context-reuse-20261026` at `f750f571b3d8d898c8a2d91c4639b6f65cb8a3f3` (unique restored history archived)
- `extension-explicit-fill-20261026` at `b9b88918d40832ab4933ebc10bacb3a2448deffa` (incorporated)
- `extension-learn-20261028` at `b633b7c348b6354955d97a51e0e1cd15ce32b333` (incorporated)
- `extension-quick-fill-20261026` at `37225a539a791ddef87d506e94c8c888b191088f` (incorporated)
- `inbox-analytics-refresh-20261027` at `268e1fc64634abe324f2a4f47503ae4f4fd4e41f` (incorporated)
- `inbox-clarity-20261026` at `d1b9fd2c7c6be0654021b0323775d756f552f1e9` (incorporated)
- `inbox-intelligence-20261028` at `1e68b48247b9f0d28ed225ef12b404a60e3bdee4` (incorporated)
- `inbox-intelligence-company-20261028` at `4f9f025047979df6f3f5bb5cf6b7f2d021ea6916` (incorporated)
- `inbox-intelligence-july-corrections-20261029` at `212e33ac2ff05aac9e1b9ffd8271959ce2099a43` (incorporated)
- `inbox-intelligence-personal-interviews-20261029` at `d995a258567c39967474f733f3efaefad14e9375` (incorporated)
- `inbox-intelligence-segregation-20261028` at `e64c54719245b886aa3db4829cfb41f99b928535` (incorporated)
- `inbox-intelligence-system-20261028` at `5109fcd919b76a588bed848c4ac4bf07d0e5acbc` (incorporated)
- `inbox-job-mail-20261027` at `3cd87a5948f0ac68768c5b9e0a815d25b5abcc31` (incorporated)
- `next-app` at `af4090a0eefdee9d1df651ba8c32d11f0bde99ca` (incorporated)
- `platform-company-logos-20261026` at `45e8c1b19dd193689eae393f198ae7f2d92ca2c3` (incorporated)
- `startup-sources-20261029` at `ccafad95bc830ecf470bf8e88735e3912d8147d5` (incorporated)

## Removed local branch names

The exact original tip of every name is in private `refs-before.txt` and the
same-named `recovery-20261030/*` local tag. Active local main is the new platform.

- `ace-local-docs-history`
- `analytics-fidelity-review-20261027`
- `analytics-release-record-20261027`
- `auth-approved-design`
- `backup/local-before-sync`
- `company-logo-consistency-20261026`
- `company-logo-tenants-20261026`
- `extension-context-reuse-20261026`
- `extension-explicit-fill-20261026`
- `extension-learn-20261028`
- `extension-quick-fill-20261026`
- `inbox-clarity-20261026`
- `inbox-intelligence-20261028`
- `inbox-intelligence-company-20261028`
- `inbox-intelligence-july-corrections-20261029`
- `inbox-intelligence-personal-interviews-20261029`
- `inbox-intelligence-segregation-20261028`
- `inbox-intelligence-system-20261028`
- `inbox-live-evidence-20261027`
- `local-backup-2026-10-15`
- `main`
- `memory-inbox-global-20261030`
- `next-app`
- `platform-company-logos-20261026`
- `release-focus-only`
- `release-focus-v51`
- `startup-sources-20261029`
- `typography-refresh`
- `wine-rose-platform`

## Retired original worktree locations

These paths no longer host the old linked/primary checkouts. The `ace-next`
path now hosts the verified new standalone clone. All originals remain privately
recoverable under `workspace-snapshots/`.

- `/home/ubuntu/Documents/ace`
- `/home/ubuntu/Documents/ace-extension-learn`
- `/home/ubuntu/Documents/ace-inbox`
- `/home/ubuntu/Documents/ace-next`
- `/home/ubuntu/Documents/ace-next/artifacts/analytics-worktree`
- `/home/ubuntu/Documents/ace-next/artifacts/inbox-intelligence-worktree`
- `/home/ubuntu/Documents/ace-next/artifacts/inbox-personal-interviews-worktree`
- `/home/ubuntu/Documents/ace-next/artifacts/memory-inbox-global-20261030`
- `/home/ubuntu/Documents/ace-next/artifacts/startup-sources-worktree`
- `/home/ubuntu/Documents/ace-typography`
- `/home/ubuntu/Documents/ace-typography-base`
