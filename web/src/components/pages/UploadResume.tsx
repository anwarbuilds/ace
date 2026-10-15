"use client";

import { useRouter } from "next/navigation";
import { useRef } from "react";

import { useApp } from "@/components/shell/AppProvider";
import { csrfHeader } from "@/lib/client";

/** Pick a PDF, DOCX or text resume; the server stores it and rescores
 *  every job against it in the same request. */
export function UploadResume({ label, primary = false, link = false }: { label: string; primary?: boolean; link?: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const { toast } = useApp();
  return (
    <>
      <button
        className={link ? "link-btn" : `btn ${primary ? "btn-primary" : "btn-secondary"}`}
        onClick={() => input.current?.click()}
      >
        {label}
      </button>
      <input
        ref={input}
        type="file"
        accept=".pdf,.docx,.txt"
        hidden
        onChange={async () => {
          const file = input.current?.files?.[0];
          if (!file) return;
          const body = new FormData();
          body.append("file", file);
          toast(`Reading ${file.name}`);
          try {
            const res = await fetch("/api/resume", { method: "POST", body, headers: csrfHeader() });
            const d = await res.json();
            if (!res.ok) throw new Error(d.detail || "upload failed");
            toast(`Resume stored, ${d.jobs_scored} jobs rescored, ${d.skills.length} skills found`);
            router.refresh();
          } catch (e) {
            toast(e instanceof Error ? e.message : "Could not read that file");
          } finally {
            if (input.current) input.current.value = "";
          }
        }}
      />
    </>
  );
}
