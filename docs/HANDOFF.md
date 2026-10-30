# ACE current handoff

Updated 2026-10-30 Pacific after owner-authorized platform consolidation. This is
the current starting point; the [previous handoff](archive/HANDOFF-before-consolidation-20261030.md)
is preserved as history. Read **all** of [ACE_NEXT_KNOWLEDGE.md](../ACE_NEXT_KNOWLEDGE.md),
[AGENTS.md](../AGENTS.md) and the relevant [knowledge topic](knowledge/README.md)
before changes. Dated pending instructions are not current authorization.

## Canonical source and workspace

- Repository: `anwarbuilds/ace`; GitHub default and canonical branch: **main**.
- The developed `wine-rose-platform` history was renamed intact, starting at
  `98b112a1d13ffd695be9efc1e2d6dd5e90758536`, including PR #19's reviewed merge
  `9c884dc880e9f4419602a4ab5faec536e171ac6a`. No history flattening or force-push.
- `/home/ubuntu/Documents/ace-next` is a fresh standalone main clone. Its `.git`
  is a directory, common dir is `.git`, and it has no object alternates or
  dependency on the former `~/Documents/ace/.git`. Only main is a live local branch.
- The original eleven registered worktree locations and 29 local branch tips
  are privately preserved. Those registrations/branches and the live stash were
  removed after verified independent recovery. Original folders are inert private
  snapshots, with linked `.git` pointer files removed. `~/Documents/ace` is absent.
- Unpacked Chrome extension path remains `ace-next/extension`. All twelve tracked
  extension files are byte-identical across the swap. No reload or publication ran.
- Private release evidence, design kits and reports were restored and hashed.
  Active `.env` contains fresh example development values. The old configuration
  is ignored/inactive `.env.legacy-retired`, mode 600. Do not source it as setup.
- Fetch main before future changes and push only the reviewed source. Private
  `recovery-20261030/*` tags are local recovery material; **do not push all tags**.

## Production is unchanged

Website: **https://ace.opik.net**. Production checkout `/opt/ace` now uses main
tracking origin/main, but deliberately remains at `fca4673033dc92833bbf217182738026f414bf3d`.
Its former single-branch fetch refspec was updated; source files were not moved.

| Running surface | Verified source revision |
| --- | --- |
| API, Inbox parser 15 | `b03d251047f531ba60a75812d9c088b395a6d943` |
| Web | `4116aa01dd5cdd3a6ea3d707017a7d9f7fad5bd7` |
| Discovery scheduler | `fca4673033dc92833bbf217182738026f414bf3d` (181 tracked runtime file hashes matched) |
| Database schema | `0050` |

Exact six production container IDs, images, starts, mount records, Caddy/.env/
Compose hashes and API source hashes matched before and after. Website/API health
passed. No production deployment, rebuild, pull, recreation, restart, migration,
database write or Gmail reclassification ran. Different image revisions are
intentional; a documentation/source push is not deployment permission.

## Legacy retirement and recovery

The identified local Compose project was `ace`, rooted at the former
`~/Documents/ace`; production is `oracle` on the VM. The two legacy writers
were stopped, the single comparison cron was removed, and a final custom dump
was taken. An isolated local restore verified all 28 table counts, twelve protected
table hashes and schema 0040. Only that temporary restore database was dropped.
The six original legacy containers are removed. **Volume `ace_ace_postgres_data`
and exact recovery images remain retained indefinitely pending a separate owner
retention decision.** No production service or volume was removed.

No legacy-only application/resume identities were found under the documented
comparison keys at the read-only snapshot. Differing older owner states, source
history and every legacy record remain archive-only; nothing was merged into
production. Private comparison detail is not public documentation.

Recovery entry point:
`/home/ubuntu/ace-private-backups/consolidation-20261030T170532Z/`
(mode 700). It contains `all-history.bundle`, `shared-git.tar.gz`,
`workspaces-private.tar.gz`, `legacy-final.dump.gz`, exact manifests, restore and
production proofs, job configurations and original workspace snapshots. Bundle
recovery verified all 63 original refs, the stash and 334 reflog/unreferenced
commits independently. Public `legacy-main-final` points to verified old main
`a3c9449370b7ca070c3bad5d5fc68876eb1e6ccb`; local recovery tags also preserve
restored-workspace, backup and stash histories. See the [full recovery record](operations/platform-consolidation-2026-10-30.md).

## Product contracts and remaining limits

The [rewritten README](../README.md) describes the current routes and workflow.
Preserve Wine and Rose V2, the approved Analytics override and Focus Mode V5.1.
ACE never submits or marks Applied after filling; employer-motivation answers
remain employer-owned. Classification, identity and status permission are separate.
Unlinked recognized email history is not a confirmed application-stage event;
assessment/interview history survives a later rejection. Owner decisions/Undo stay.
Global Gmail historical rechecks remain false and parser-7 stays stopped.

PR #19/Inbox parser 15 release and its exact one-email correction were already
complete before consolidation. Do not replay them. Current Inbox and email
Analytics use the July 1, 2026 Pacific floor; older evidence stays for audit.
Classification precision/recall, complete mailbox observation, submitted-file/
channel attribution and response-effectiveness rates remain unestablished.
Source gaps and refusal backoff remain; no source cadence or scheduler policy
changed. Resume tailoring/export and offsite backup remain limitations.

## Validation and CI

Fresh dependency installation, focused fictional backend tests, matcher/Memory,
DOM/calculation checks, TypeScript, lint, production web build and demo seeding
passed. Fourteen local HTTP routes passed with a fictional signed-in session;
this is not browser rendering or signed-in production verification. No Chrome ran.
Read the [testing runbook](operations/testing.md); laptop cooling restrictions remain.

The rechecked PR #19 full run
[41075615441](https://github.com/anwarbuilds/ace/actions/runs/41075615441)
failed on 22 extension-browser cases after backend/web passed; later app-browser
steps were skipped. Dedicated Inbox run
[41075606426](https://github.com/anwarbuilds/ace/actions/runs/41075606426) passed.
Consolidation changes documentation/instructions and archive ignore rules only;
backend, web, extension, workflow and Compose runtime bytes are unchanged.
Main pushes run CI with all assertions intact. See the
[current workflow results](https://github.com/anwarbuilds/ace/actions/workflows/ci.yml)
and private final verification for the consolidation run; do not claim overall green.

## Future sessions

Use the standalone main checkout and current runbooks. Do not recreate old
worktrees, restore an archived `.git` pointer, run the historical comparison
installer, restart the old replica, or treat archived migration procedures as
setup. Recovery is into a separate folder/database; restarting services or
writing production needs a new specific approval. Continue only the owner's
next requested product work and preserve all private recovery material.
