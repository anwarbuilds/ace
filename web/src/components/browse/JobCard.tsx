import Link from "next/link";

import { Avatar, StatusBadge } from "@/components/bits";
import { TIER_LABEL, ago, clean, expFit, tierLabel, tierOf } from "@/lib/format";
import type { Job } from "@/lib/types";

/** One role as a card: the shop-window view of a job. The whole card is
 *  a link to the role's own page. */
export function JobCard({ job }: { job: Job }) {
  const t = tierOf(job.match_score);
  const fit = expFit(job);
  return (
    <Link className={`jc${job.review_state ? " jc-done" : ""}`} href={`/app/jobs/${job.id}`}>
      <div className="jc-co">
        <Avatar name={job.company} />
        <div className="jc-co-t">
          <span className="jc-co-n">{job.company}</span>
          {TIER_LABEL[job.company_tier] ? <span className="co-tier">{TIER_LABEL[job.company_tier]}</span> : null}
        </div>
      </div>
      <h3 className="jc-title">{clean(job.title)}</h3>
      <p className="jc-loc">{job.location}</p>
      <div className="jc-chips">
        <span className={`chip-exp ${fit.cls}`}>{fit.text}</span>
        {job.application_status ? <StatusBadge status={job.application_status} /> : null}
      </div>
      <div className="jc-foot">
        {t === "unscored" ? (
          <span className="m-unscored">Not scored yet</span>
        ) : (
          <span className={`jc-match m-${t}`}>
            {job.match_score}% <i>{tierLabel(t)}</i>
          </span>
        )}
        <span className="jc-age">{ago(job.first_seen_at)}</span>
      </div>
    </Link>
  );
}

/** A titled row of cards that scrolls sideways, with a link to the full
 *  page for its group. */
export function CardRow({
  title,
  href,
  count,
  jobs,
  empty,
}: {
  title: string;
  href: string;
  count?: number;
  jobs: Job[];
  empty?: string;
}) {
  return (
    <section className="row-sec">
      <div className="row-head">
        <h2 className="row-title">
          <Link href={href}>{title}</Link>
        </h2>
        {count != null ? <span className="h1-count">{count.toLocaleString("en-US")}</span> : null}
        <span className="spacer" />
        <Link className="row-all" href={href}>
          See all
        </Link>
      </div>
      {jobs.length ? (
        <div className="row-track">
          {jobs.map((j) => (
            <JobCard key={j.id} job={j} />
          ))}
        </div>
      ) : (
        <p className="why">{empty ?? "Nothing here right now."}</p>
      )}
    </section>
  );
}
