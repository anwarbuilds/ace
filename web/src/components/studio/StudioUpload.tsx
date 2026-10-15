"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { useApp } from "@/components/shell/AppProvider";
import { csrfHeader } from "@/lib/client";

/** Upload a resume (PDF, DOCX or text) or a DOCX template. The file is
 *  kept exactly as uploaded; a resume also yields suggested facts. */
export function StudioUpload({
  kind = "resume",
  label,
  primary = false,
}: {
  kind?: "resume" | "template";
  label: string;
  primary?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const { toast } = useApp();
  const [busy, setBusy] = useState(false);
  return (
    <>
      <button
        className={`btn ${primary ? "btn-primary" : "btn-secondary"} btn-sm`}
        disabled={busy}
        onClick={() => input.current?.click()}
      >
        {busy ? "Reading" : label}
      </button>
      <input
        ref={input}
        type="file"
        hidden
        accept={kind === "template" ? ".docx" : ".pdf,.docx,.txt,.md"}
        onChange={async (e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (!file) return;
          setBusy(true);
          const body = new FormData();
          body.append("file", file);
          body.append("kind", kind);
          try {
            const res = await fetch("/api/studio/documents", { method: "POST", body, headers: csrfHeader() });
            const data = await res.json().catch(() => ({}));
            if (res.status >= 500) {
              // Not the file's fault: say so, and point at the usual cause.
              toast("ace hit a server error storing the file. If you just updated, run alembic upgrade head, then retry.");
            } else if (!res.ok) {
              toast(typeof data.detail === "string" ? data.detail : `The upload was refused (${res.status}).`);
            } else if (!data.created) {
              toast("That file is already here.");
            } else {
              toast(kind === "template" ? "Template stored" : "Resume read. Review the suggested facts.");
              router.refresh();
            }
          } catch {
            toast("ace did not answer. Try again in a moment.");
          }
          setBusy(false);
        }}
      />
    </>
  );
}
