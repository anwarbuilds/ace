"use client";

import { useEffect, useState } from "react";

type PreviewState =
  | { kind: "loading" }
  | { kind: "ready"; url: string }
  | { kind: "error"; message: string };

export function ResumeDocumentPreview({
  documentId,
  filename,
  mediaType,
}: {
  documentId: number;
  filename: string;
  mediaType: string;
}) {
  const source = `/api/studio/documents/${documentId}/file`;
  const canPreview = mediaType === "application/pdf" || filename.toLowerCase().endsWith(".pdf");
  const [state, setState] = useState<PreviewState>({ kind: "loading" });

  useEffect(() => {
    if (!canPreview) return;
    const controller = new AbortController();
    let objectUrl = "";

    void fetch(source, { cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`The resume file could not be loaded (${response.status}).`);
        const bytes = await response.blob();
        objectUrl = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
        setState({ kind: "ready", url: objectUrl });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState({
          kind: "error",
          message: error instanceof Error ? error.message : "The resume file could not be loaded.",
        });
      });

    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [canPreview, source]);

  if (!canPreview) {
    return (
      <div className="studio-v2-document-unavailable">
        <strong>{filename}</strong>
        <p>This file is stored safely, but this browser cannot preview its format here.</p>
        <a className="btn btn-primary btn-sm" href={source} download>
          Download original file
        </a>
      </div>
    );
  }

  if (state.kind === "loading") {
    return (
      <div className="studio-v2-document-status" aria-busy="true">
        <span className="spinner" aria-hidden="true" />
        Loading your PDF
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div className="studio-v2-document-unavailable" role="alert">
        <strong>Preview unavailable</strong>
        <p>{state.message}</p>
        <a className="btn btn-primary btn-sm" href={source} download>
          Download original PDF
        </a>
      </div>
    );
  }

  return (
    <div className="studio-v2-document-preview">
      <iframe className="studio-v2-pdf-frame" src={state.url} title={`${filename} preview`} />
      <div className="studio-v2-document-actions">
        <span title={filename}>{filename}</span>
        <a className="link-btn" href={source} download>
          Download original
        </a>
      </div>
    </div>
  );
}
