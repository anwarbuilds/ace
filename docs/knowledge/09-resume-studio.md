# Resume Studio

## Foundation and the checker (2026-10-14)

Built on `next-app` from sections 6 and 7 of the master brief, with the
owner's decision of no AI: everything is deterministic and repeatable.

**Shape.** `backend/app/studio/`: `sections.py` (headings, contact,
dates, bullets, from plain text), `facts.py` (suggested facts from those
sections), `documents.py` (text plus a layout report: pages, tables, a
second column, contact in a page header, DOCX heading styles for
templates), `ats.py` (the checker), `service.py` (rules over the
database). HTTP in `backend/app/api/routers/studio.py` under
`/api/studio`. Migration 0039 adds `resume_documents` (original bytes,
kept as uploaded), `career_facts` and `career_fact_events` (the audit
trail, with the fields before each edit), `resume_versions` and
`resume_assessments`. Web pages under `/app/resume-studio`: Overview,
Knowledge base, Documents and versions (with a document inspector and
text correction), ATS checker, History; a job page links to the checker.

**Decisions.**
- Facts are separate from wording. A parsed fact starts `suggested`; one
  the owner types starts `verified`. Retiring sets `deprecated`; nothing
  is hard deleted. Only verified facts count as evidence, and the
  checker names any skill a resume claims that no verified fact backs.
- The primary version feeds the job list: making a version primary
  copies its text into the matcher's `resumes` table and rescores, as an
  upload always did. The first uploaded resume becomes primary only when
  none exists.
- The checker scores four parts, with configurable weights
  (`ats.WEIGHTS`: requirement evidence 45, parseability 20, hard fit 20,
  content quality 15) and returns evidence quotes with line numbers,
  findings, unknowns and prioritised recommendations. Labelled
  "Estimated ace compatibility score", algorithm `ats-2026-10-14-v1`;
  never framed as an employer's system.
- Evidence strength: used in an experience, project or summary line is
  full credit; named only in a skills list is 0.75 ("listed only");
  related through the matching graph is 0.5; preferred skills weigh half.
- A posting under 400 characters, unverified, or naming under three
  skills is `insufficient_job_data`: no aggregate and no requirements
  score, never a zero. A resume under 200 characters is
  `unreadable_resume`.
- Hard fit reuses the gate (`evaluate_job`) for required years and
  authorization conditions; it diagnoses and never filters.

**Adversarial fixtures** (`backend/tests/test_studio_ats.py`): synonyms
(Postgres, k8s), keyword stuffing, a polished resume whose skills are
never shown in use, an unreadable file, dates that end before they start,
an SDE II years mismatch, a sponsorship refusal, claims missing from the
knowledge base, a posting with no section headings, layout problems.

**Lessons.**
- `Go` alone is not matched as a skill (too common a word); fixtures use
  "golang".
- A pdfplumber page count is unknown for a DOCX; the report carries
  `None`, so compare with `(report.get("pages") or 1)`.
- `Tabs` kept one module-level memory for its sliding pill; two tab
  groups slid from each other. It is now keyed per group.

**Not built yet** (Phase 4 of the plan): tailoring requests and
artifacts, the side-by-side diff and approval, DOCX and PDF export into
the owner's template with checksums, and durable background jobs.
