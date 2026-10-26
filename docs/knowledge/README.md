# ace knowledge set

Everything learned building ace, from the first week to now, split by topic so a session reads only what it needs.
Start with `../../ACE_NEXT_KNOWLEDGE.md` (current verified state) and `../HANDOFF.md` (rules and plan; both load through the root `CLAUDE.md`), then open
a topic file when you work in that area. Reading all of it is about 53k tokens; do not.

| File | Covers | Read when | Size |
| --- | --- | --- | --- |
| `00-overview-limits-roadmap.md` | The whole system on one page: what ace is, the seven invariants, architecture table, known limits, old roadmap, backlog, newest session log | you start cold, or want the rules that must never break | ~3k |
| `01-gate-and-roles.md` | Who passes the eligibility gate and why: experience extraction and ranges, location, contract, security, new grad vs early career, role families, data roles flag | you change a rule or ask why a posting was rejected or admitted | ~3k |
| `02-sources-and-scheduler.md` | Adapters, polling, conditional HTTP, retries, identity and diffing, Eightfold, Amazon, description decoding, scheduler concurrency | you touch a reader or the scheduler, or a source misbehaves | ~5k |
| `03-coverage-and-discovery.md` | Recall audits, board discovery, unreachable companies, feeds vs employer boards, the aggregator that was removed, the 2026-10 sweeps and own-site readers (Apple, Google, Meta, Atlassian, EA, Shopify and more) | a company or role was missed, you add a reader, or you ask whether a site may be read | ~12k |
| `04-matching-and-applications.md` | Resume matching (lexical, then related-skill credit), marks, application status, the old sheet import and its lessons, CSV export, why Inbox looked synced when it was not | you touch scores, marks, statuses, the export or Inbox outcomes (and for the resume scoring gap) | ~7k |
| `05-web-ui.md` | What each screen is for, the triage design, sorts, filters, pulls, activity log, historical redesigns (Wine and Rose is current), browser-test lessons for the UI | you change the old UI or build the Next.js replacement | ~8k |
| `06-extension-autofill.md` | The matcher, the answer bank, the panel, phone and country widgets, repeating blocks, multi-page forms, what real forms taught (Dell, DoorDash, Handshake, JazzHR, Ashby) | you change anything that touches a live application form | ~11k |
| `07-alerts-email-and-auth.md` | Freshness, the removed email subsystem, one alert per pull, email client quirks, why sign-in was built then removed | you touch alerts or Resend, or you start the sign-in work | ~2k |
| `08-operations-and-testing.md` | Operational gotchas (build before up, UTC, restarts, generic plans), incidents, and browser-test craft | you deploy, restart, debug the scheduler or write browser tests | ~3k |
| `09-resume-studio.md` | Resume Studio: documents, the career knowledge base, versions, the ATS checker and its rubric | you work on resumes, facts, the checker, tailoring or export | ~1k |

## How to find things

```
grep -n '^## ' docs/knowledge/0*.md            # every entry title, with its file and line
grep -rn -i 'eightfold' docs/knowledge/        # one subject across all topics
```

## Lessons that keep recurring

These are the habits the whole history teaches. Each is an entry you can read for the evidence.

1. **Silence is the failure mode.** A missed job raises no error, so measure recall against an independent list instead of
   trusting the pipeline (03: "Coverage is 20%, and the 64% was selection bias", "The source audit").
2. **Fix causes, not instances.** A curated list is never finished (01: "A longer list is not a guarantee"; 03: "The
   bottleneck was names, not machinery").
3. **A route that works can stop another from being read.** Reaching a company through a feed stopped ace reaching its own
   board, and a board that stops answering is a company ace stopped reading (03).
4. **Respect refusals and do not restart in loops.** Three restarts in twenty minutes got ace refused by Eightfold (02). A
   403, 405 or 429 is an answer, not an obstacle (08).
5. **Check every number against what the screen shows.** "31 postings seen" meant 31 new out of about 63,000 checked, and
   filter counts were taken over the wrong corpus (05).
6. **Real forms are the specification for autofill.** Each live form found new bugs: Dell, DoorDash, Handshake, JazzHR,
   OpenAI on Ashby (06).
7. **Test the real thing, and wait for it.** The extension harness had never tested the extension (06); a test that writes
   must wait for the write (08).
8. **Never guess.** Not imports, not URL matches (the most confident method matched the wrong job, 04), and not which rows
   are test data (08).
9. **Rebuild every image before `up`**, `migrate` included (08). **Show dates in the user's time zone**, not the
   container's (08).
10. **Design is judged by looking.** Every redesign was corrected from a screenshot (05).

## Conventions

- An entry is `## Title (date)` followed by what was reported or seen, the cause, the fix and the lesson. It describes the
  system on its date: where it disagrees with the code, trust the code and fix the entry.
- A superseded entry keeps its text and gains a `> **Status:**` line saying what replaced it.
- Spelling out reasoning is the point. Prefer why over what; the code already says what.

## Adding knowledge (do this before ending a session)

1. Append a dated entry to the topic file it belongs to; add a Status line to anything it supersedes.
2. Update `docs/HANDOFF.md` section 3 (state) if the state changed, and the plan if the plan changed. Keep it under 450 lines.
3. Commit those docs with the code. Push only when authorized and after reconciling any concurrent branch work. A remote session sees only what is on GitHub; a local session can read local commits.
4. Keep personal data out. This repo is public: no names, contact details, application history, answers or secrets.

## What is deliberately not here

The owner's profile, application history, private cleanup items and any secret live outside the repo (private notes, local
memory, the prompt a session is started with). Do not copy them in.

Historical section 3 notes moved out of the growing handoff on 2026-10-26 are
retained in [11-handoff-state-archive.md](11-handoff-state-archive.md).
