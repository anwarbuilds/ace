import Link from "next/link";
import { notFound } from "next/navigation";

import { ScrollArea } from "@/components/shell/ScrollArea";
import { CorrectText } from "@/components/studio/CorrectText";
import { apiGetOr } from "@/lib/api";
import type { StudioDocument, StudioOverview, Version } from "@/lib/studio";

export const metadata = { title: "Document · ace" };

export default async function DocumentPage({ params, searchParams }: PageProps<"/app/resume-studio/documents/[id]">) {
  const { id } = await params;
  const sp = await searchParams;
  const [doc, o] = await Promise.all([
    apiGetOr<StudioDocument | null>(`/api/studio/documents/${encodeURIComponent(id)}`, null),
    apiGetOr<StudioOverview | null>("/api/studio", null),
  ]);
  if (!doc) notFound();
  const wanted = Number(Array.isArray(sp.version) ? sp.version[0] : sp.version);
  const versions = (o?.versions ?? []).filter((v) => v.document_id === doc.id);
  const chosen = versions.find((v) => v.id === wanted) ?? versions[versions.length - 1];
  // The overview leaves text out; read the chosen version whole.
  const version = chosen ? await apiGetOr<Version | null>(`/api/studio/versions/${chosen.id}`, chosen) : undefined;
  const s = doc.structure;
  const r = doc.report;
  const checks: [string, boolean, string][] = [
    ["Text could be read", !r.error && (r.characters ?? 0) > 200, r.error ?? `${r.characters ?? 0} characters`],
    ["Email found", Boolean(s?.emails.length), s?.emails.join(", ") || "none"],
    ["Phone found", Boolean(s?.phones.length), s?.phones.join(", ") || "none"],
    ["Date ranges", Boolean(s?.dates.length), `${s?.dates.length ?? 0} found`],
    ["Bullets", Boolean(s?.bullets), `${s?.bullets ?? 0} found`],
    ["No tables", !r.tables, r.tables ? `${r.tables} table(s)` : "none"],
    ["Single column", !r.columns, r.columns ? "looks like two columns" : "yes"],
    ["Contact in the body", !r.header_footer_contact, r.header_footer_contact ? "in a page header or footer" : "yes"],
  ];
  return (
    <ScrollArea>
      <div className="page">
        <div className="wrap">
          <Link className="link-btn" href="/app/resume-studio/documents">
            Back to documents
          </Link>
          <h2 className="st-h2" style={{ marginTop: 14 }}>
            {doc.filename}
          </h2>
          <p className="why">
            {doc.kind === "template" ? "Template" : "Resume"}, read with {doc.parser}.{" "}
            <a className="link-btn" href={`/api/studio/documents/${doc.id}/file`} download>
              Download the original
            </a>
          </p>
          <div className="st-split sect">
            <div className="card st-card">
              <p className="eyebrow">What a parser can read</p>
              <div className="st-checks">
                {checks.map(([label, ok, detail]) => (
                  <div key={label} className={`st-check ${ok ? "st-ok" : "st-bad"}`}>
                    <span className="st-dot" />
                    <span>{label}</span>
                    <span className="st-muted">{detail}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="card st-card">
              <p className="eyebrow">Sections recognised</p>
              {s?.sections.length ? (
                <div className="st-checks">
                  {s.sections.map((x) => (
                    <div key={`${x.kind}-${x.line}`} className="st-check st-ok">
                      <span className="st-dot" />
                      <span>{x.heading}</span>
                      <span className="st-muted">
                        {x.kind}, line {x.line}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="why">No headings were recognised. Use plain headings such as Experience and Education.</p>
              )}
              {doc.kind === "template" && r.headings?.length ? (
                <p className="why" style={{ marginTop: 10 }}>
                  Template styles: {r.headings.map((h) => `${h.text} (${h.style})`).join(", ")}.
                </p>
              ) : null}
            </div>
          </div>
          {doc.kind === "resume" ? (
            <div className="sect">
              <p className="eyebrow">Extracted text</p>
              <p className="why">
                If something was read wrong, correct it here. The original stays; the correction is saved as a new
                version.
              </p>
              <CorrectText
                key={version?.id ?? 0}
                text={version?.body_text ?? doc.extracted_text ?? ""}
                parentId={version?.id ?? null}
                label={version?.label ?? doc.filename}
              />
            </div>
          ) : null}
        </div>
      </div>
    </ScrollArea>
  );
}
