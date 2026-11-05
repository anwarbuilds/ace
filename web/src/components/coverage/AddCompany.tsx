"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Icon } from "@/components/Icon";
import { sendJson } from "@/lib/client";
import { ago, clean, shortDate } from "@/lib/format";
import type { SourceResult } from "@/lib/types";

const SEE_IN_SOURCES = "/app/coverage?tab=sources&show=mine";

function firstRead(seconds: number | null): string {
  if (!seconds || seconds <= 900) return "Within 15 minutes";
  if (seconds <= 3600) return "Within an hour";
  return "Within a day";
}

function readAgo(iso: string): string {
  const age = ago(iso);
  return age === "just now" ? age : `${age} ago`;
}

/** The one sentence about the job the owner pasted, when they pasted one. */
function yourJob(d: SourceResult): string | null {
  if (!d.linked) return null;
  if (!d.job) {
    return d.status === "added"
      ? "ace looks for it in the first read."
      : "ace has not stored this job yet. It looks again in its next read.";
  }
  const place = d.job.location ? `, ${clean(d.job.location)}` : "";
  const where = !d.job.active
    ? "It has closed."
    : d.job.passes
      ? "It is in Opportunities."
      : "ace read it, and it does not pass your filters.";
  return `${clean(d.job.title)}${place}. ${where}`;
}

function Answer({ d, tz, undo, undoing }: { d: SourceResult; tz: string; undo: () => void; undoing: boolean }) {
  const company = clean(d.company || "This company");
  const job = yourJob(d);
  const when = d.next_check_at ? shortDate(d.next_check_at, tz) : "";
  const later = when ? ` ace looks again on ${when}.` : "";

  if (d.status === "added") {
    return (
      <div className="cov-answer" role="status" data-status="added">
        <span className="badge cov-good">Added</span>
        <h3>{company} added</h3>
        <p>
          ace checked this board and it belongs to {company}. It has {d.job_count}{" "}
          {d.job_count === 1 ? "job" : "jobs"} today.
        </p>
        {job ? (
          <p>
            <b>Your job:</b> {job}
          </p>
        ) : null}
        <ol className="cov-steps">
          <li className="done">
            <span aria-hidden="true">
              <Icon name="check" size={12} />
            </span>
            <div>
              <strong>Added</strong>
              <small>Just now</small>
            </div>
          </li>
          <li>
            <span aria-hidden="true" />
            <div>
              <strong>First read</strong>
              <small>{firstRead(d.first_read_seconds)}</small>
            </div>
          </li>
          <li>
            <span aria-hidden="true" />
            <div>
              <strong>New jobs appear</strong>
              <small>In Pulls and Opportunities</small>
            </div>
          </li>
        </ol>
        <div className="cov-answer-actions">
          <Link className="btn btn-secondary" href={SEE_IN_SOURCES}>
            See it in Sources
          </Link>
          <button className="btn btn-secondary" type="button" onClick={undo} disabled={undoing}>
            Undo
          </button>
        </div>
      </div>
    );
  }

  if (d.status === "already_known") {
    return (
      <div className="cov-answer" role="status" data-status="already_known">
        <span className="badge cov-plain">Already reading</span>
        <h3>ace already reads {company}</h3>
        <p>Nothing to do.{d.last_read_at ? ` Its board was read ${readAgo(d.last_read_at)}.` : ""}</p>
        {job ? (
          <p>
            <b>Your job:</b> {job}
          </p>
        ) : null}
        <div className="cov-answer-actions">
          {d.job ? (
            <Link className="btn btn-secondary" href={`/app/jobs/${d.job.id}`}>
              Open the job
            </Link>
          ) : null}
          <Link className="btn btn-secondary" href={`/app/coverage?tab=sources&q=${encodeURIComponent(company)}`}>
            See it in Sources
          </Link>
        </div>
      </div>
    );
  }

  if (d.status === "saved_no_reader") {
    return (
      <div className="cov-answer" role="status" data-status="saved_no_reader">
        <span className="badge cov-warn">Saved, not read yet</span>
        <h3>{company} saved, but ace can&rsquo;t read its site yet</h3>
        <p>
          {clean(d.detail)}
          {later} Until then, check it by hand.
        </p>
      </div>
    );
  }

  if (d.status === "saved_refused") {
    return (
      <div className="cov-answer" role="status" data-status="saved_refused">
        <span className="badge cov-bad">Saved, site says no</span>
        <h3>{company} saved, but its site says no</h3>
        <p>
          {clean(d.detail)}
          {later}
        </p>
      </div>
    );
  }

  if (d.status === "known_off") {
    return (
      <div className="cov-answer" role="status" data-status="known_off">
        <span className="badge cov-warn">Switched off</span>
        <h3>ace knows {company}, and has it switched off</h3>
        <p>{clean(d.detail)}</p>
      </div>
    );
  }

  return (
    <div className="cov-answer" role="status" data-status="saved_looking">
      <span className="badge cov-plain">Saved, still looking</span>
      <h3>ace found no job board for {company} yet</h3>
      <p>
        {clean(d.detail)}
        {later}
        {d.linked ? "" : " If you have a job link, paste that instead. It usually works better than a name."}
      </p>
    </div>
  );
}

/** Paste a job link, a careers page or a name, and ace says what happened. */
export function AddCompany({ tz }: { tz: string }) {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [undoing, setUndoing] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [answer, setAnswer] = useState<SourceResult | null>(null);

  // The Add button in the page header lands here.
  useEffect(() => {
    if (window.location.hash === "#cov-input") input.current?.focus();
  }, []);

  const add = async () => {
    const value = text.trim();
    setAnswer(null);
    if (!value) {
      setNote("Paste a link or a company name first.");
      return;
    }
    setBusy(true);
    setNote("Looking for a job board. This can take up to a minute.");
    try {
      const d = await sendJson<SourceResult>("POST", "/api/sources", { text: value });
      setAnswer(d);
      setNote(null);
      setText("");
      router.refresh();
    } catch {
      setNote("Could not reach ace, so nothing was added. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const undo = async () => {
    if (!answer) return;
    setUndoing(true);
    try {
      await sendJson("POST", "/api/sources/undo", {
        source_type: answer.source_type,
        source_account: answer.source_account,
      });
      setNote(`Taken back. ace will not read ${clean(answer.company || "this board")}.`);
      setAnswer(null);
      router.refresh();
    } catch {
      setNote("Could not take it back. Try again.");
    } finally {
      setUndoing(false);
    }
  };

  return (
    <section className="cov-card cov-add-card" aria-labelledby="cov-add-h">
      <h2 id="cov-add-h">Found a job ace doesn&rsquo;t have?</h2>
      <p className="why">
        Paste the job link, the company&rsquo;s careers page, or just its name. ace does the rest and tells you what
        happened.
      </p>
      <form
        className="cov-add"
        onSubmit={(event) => {
          event.preventDefault();
          void add();
        }}
      >
        <label className="sr-only" htmlFor="cov-input">
          Job link, careers page or company name
        </label>
        <input
          id="cov-input"
          ref={input}
          type="text"
          autoComplete="off"
          spellCheck={false}
          placeholder="Paste a job link, or type a company name"
          value={text}
          onChange={(event) => setText(event.target.value)}
        />
        <button className="btn btn-primary" type="submit" disabled={busy}>
          {busy ? "Looking" : "Add"}
        </button>
      </form>
      {note ? (
        <p className="cov-note" role="status">
          {note}
        </p>
      ) : null}
      {answer ? <Answer d={answer} tz={tz} undo={undo} undoing={undoing} /> : null}
    </section>
  );
}
