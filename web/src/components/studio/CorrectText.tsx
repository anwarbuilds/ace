"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { useApp } from "@/components/shell/AppProvider";
import { RequestError, sendJson } from "@/lib/client";

export function CorrectText({ text, parentId, label }: { text: string; parentId: number | null; label: string }) {
  const router = useRouter();
  const { toast } = useApp();
  const [value, setValue] = useState(text);
  const changed = value !== text;
  return (
    <div className="st-correct">
      <textarea className="st-text" autoComplete="off" value={value} onChange={(e) => setValue(e.target.value)} rows={22} spellCheck />
      <div className="controls" style={{ paddingLeft: 0 }}>
        <button
          className="btn btn-primary btn-sm"
          disabled={!changed}
          onClick={async () => {
            try {
              const v = await sendJson<{ id: number }>("POST", "/api/studio/versions", {
                parent_id: parentId,
                label: `${label}, corrected`,
                body_text: value,
              });
              toast("Saved as a new version");
              router.push(`/app/resume-studio/documents?saved=${v.id}`);
              router.refresh();
            } catch (err) {
              toast(err instanceof RequestError ? err.message : "ace did not answer.");
            }
          }}
        >
          Save as a new version
        </button>
        {changed ? (
          <button className="btn btn-secondary btn-sm" onClick={() => setValue(text)}>
            Discard changes
          </button>
        ) : null}
      </div>
    </div>
  );
}
