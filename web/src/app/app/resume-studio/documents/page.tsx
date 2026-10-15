import Link from "next/link";

import { ScrollArea } from "@/components/shell/ScrollArea";
import { MakePrimary } from "@/components/studio/MakePrimary";
import { StudioUpload } from "@/components/studio/StudioUpload";
import { apiGetOr } from "@/lib/api";
import { shortDate } from "@/lib/format";
import { getPrefs } from "@/lib/prefs";
import type { StudioOverview } from "@/lib/studio";

export const metadata = { title: "Documents and versions · ace" };

function size(n: number) {
  return n >= 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`;
}

export default async function DocumentsPage() {
  const [{ tz }, o] = await Promise.all([getPrefs(), apiGetOr<StudioOverview | null>("/api/studio", null)]);
  const docs = o?.documents ?? [];
  const versions = o?.versions ?? [];
  const byId = new Map(versions.map((v) => [v.id, v]));
  return (
    <ScrollArea>
      <div className="page">
        <div className="wrap">
          <div className="sect">
            <div className="st-row-head">
              <p className="eyebrow" style={{ margin: 0 }}>
                Resume versions
              </p>
              <span className="spacer" />
            </div>
            <p className="why">
              A version is wording. The one marked for matching ranks every opportunity. Correcting a version keeps the
              original and saves a new one.
            </p>
            <div className="st-table">
              {versions.map((v) => (
                <div className="st-trow" key={v.id}>
                  <span className="st-trow-main">
                    <b>{v.label}</b>
                    <span className="st-muted">
                      {v.kind === "master" ? "Master" : "Tailored"}
                      {v.parent_id ? `, corrected from ${byId.get(v.parent_id)?.label ?? "an earlier version"}` : ""}
                    </span>
                  </span>
                  <span className="st-muted">{shortDate(v.created_at, tz)}</span>
                  {v.is_primary ? <span className="st-chip st-status-verified">Used for matching</span> : <MakePrimary id={v.id} />}
                  {v.document_id ? (
                    <Link className="link-btn" href={`/app/resume-studio/documents/${v.document_id}?version=${v.id}`}>
                      Inspect
                    </Link>
                  ) : (
                    <span />
                  )}
                </div>
              ))}
              {!versions.length ? <p className="why">No versions yet.</p> : null}
            </div>
          </div>
          <div className="sect">
            <div className="st-row-head">
              <p className="eyebrow" style={{ margin: 0 }}>
                Uploaded files
              </p>
              <span className="spacer" />
              <StudioUpload label="Upload a resume" />
              <StudioUpload kind="template" label="Upload a DOCX template" />
            </div>
            <p className="why">Kept exactly as uploaded, so every extraction can be checked against its source.</p>
            <div className="st-table">
              {docs.map((d) => (
                <div className="st-trow" key={d.id}>
                  <span className="st-trow-main">
                    <b>{d.filename}</b>
                    <span className="st-muted">
                      {d.kind === "template" ? "Template" : "Resume"}, {size(d.size_bytes)}, read with {d.parser}
                      {d.report.pages ? `, ${d.report.pages} page${d.report.pages === 1 ? "" : "s"}` : ""}
                    </span>
                  </span>
                  <span className="st-muted">{shortDate(d.created_at, tz)}</span>
                  {d.report.error ? <span className="st-chip st-sev-high">Unreadable</span> : <span />}
                  <Link className="link-btn" href={`/app/resume-studio/documents/${d.id}`}>
                    Inspect
                  </Link>
                </div>
              ))}
              {!docs.length ? <p className="why">No files yet.</p> : null}
            </div>
          </div>
        </div>
      </div>
    </ScrollArea>
  );
}
