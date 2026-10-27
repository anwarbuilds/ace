# Adopt answers and reuse compatible context, 2026-10-26

Status: implemented and tested, extension source **1.30.0**. The associated
Memory API change is NOT deployed. The last verified production website is
`1fee671` with logo API source `d0342d4`. Deployment of this separate API
operation requires owner approval, followed by Reload of the unpacked extension
and refresh of employer tabs. No Web Store publication or migration is needed.

## Owner decision and cause

The owner reported repeating screening questions despite having completed them
on earlier applications and requested adoption and reuse when meaning/context
match, without requiring identical wording. This supersedes the blanket ban on
reusing the specific factual binary screenings described below. It does not
approve indiscriminate sensitive reuse, company substitution or employer-motivation
capture. Filling remains explicit, from Fill, toolbar Fill or Alt+A.

The current API rejects protected/company questions outright. Earlier extensions
can acknowledge their completion on one form but cannot save them for the next.
Routine equivalence also accepts few paraphrases; identical duplicate records
were treated as conflicts. Finally, a committed answer entered before the Memory
response was ready was not retried after connection.

## Final behavior

- Real committed applicant edits under the existing auto-save setting can save
  eligible answers without duplicate approval. A delayed Memory connection
  retries the still-current trusted edit. It never starts a passive fill.
- Existing native/custom control adapters must verify actual committed state.
  Only successful private saving earns the compact "saved for next time"
  receipt. Failed saving preserves local completion, explains the failure and
  provides Retry. Unknown options and uncommitted search text stay unlearned.
- Common routine prompt and verb variations match while question type,
  negation, numeric values and timeframe qualifiers remain significant.
  Identical duplicate answers can resolve; disagreeing records require correction.
- The reviewed binary screening catalog covers exact two-status/four-status US
  eligibility questions, combined present/future visa sponsorship, named-employer
  work relationships, temporary-work history, interview history, a 12-month
  agency-submission question and the complete current/former-employer
  post-employment-obligations question. It does not derive a compound answer from
  a narrower stored fact or generalize a simple non-compete answer to all duties.
- Named employer and subsidiary scope remain part of identity. Previous and
  ever scopes differ. Relative company wording and an unspecified work country
  bind to the original hiring tenant/site. Shared Greenhouse/Lever/Ashby/etc.
  hosts use their tenant path; Workday site paths and Oracle sites stay separate.
  Explicit US sponsorship wording stays distinct from unspecified-country wording.
- The new `scoped` Memory policy requires the reviewed fact, exact computed
  concept/scope and an exact Yes/No answer. Ordinary answers retain the existing
  `reusable` policy. The existing `reuse_policy` column is sufficient; no schema
  change. Old entries are retained. No answer-bank/history rows are rewritten.
- Corrections and deletion invalidate the current form's reuse copy. Existing
  employer values are never overwritten. Memory edits retain revision guards.
- Motivation is excluded before reading any value. Attestations, signatures,
  consent, demographic questions and unsupported protected facts remain manual.
  No submit, navigation, Applied, permission or Gmail behavior is added.

Previously rejected saves cannot be reconstructed from past closed forms.
Existing saved profile facts still work. A newly eligible answer must be
committed once with the updated API/extension before later reuse is available.

## Validation and boundaries

- 82 fictional DOM contracts pass against actual extension scripts, including
  cross-application adoption, company/subsidiary/status isolation, implicit ATS
  tenant isolation, late connection, save failure, Workday-style custom choice
  to native choice transfer and correction of an earlier form copy.
- 173 fictional backend Memory/auth/logo tests pass. Shared JSON cases check
  JavaScript/Python scope parity, endpoint idempotency, policy, authentication,
  invalid/unsafe facts and revision conflicts.
- 258 matcher cases, Memory safety/scope/paraphrase checks, JavaScript syntax,
  TypeScript, lint, zero-hit forbidden-dash scan and whitespace checks pass.
- Browser cases are collection only. Chrome remains prohibited by cooling;
  actual employer DOM, installed MV3 behavior and new visual screenshots are
  not verified. No source assertions are called production verification.

Changed runtime files: `extension/{memory,content}.js`, manifest and the existing
Memory input/write handler in `backend/app/api/main.py`, plus
`backend/app/answers/screening.py`. Tests and supporting documentation accompany
those changes. The website, logo service, discovery, existing Inbox work,
authentication model, schema and application tracking are preserved.
