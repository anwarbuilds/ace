"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { useApp } from "@/components/shell/AppProvider";
import { RequestError, sendJson } from "@/lib/client";

export function MakePrimary({ id }: { id: number }) {
  const router = useRouter();
  const { toast } = useApp();
  const [busy, setBusy] = useState(false);
  return (
    <button
      className="btn btn-secondary btn-sm"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try {
          await sendJson("POST", `/api/studio/versions/${id}/primary`);
          toast("Now used for matching. Every opportunity was rescored.");
          router.refresh();
        } catch (err) {
          toast(err instanceof RequestError ? err.message : "ace did not answer.");
        }
        setBusy(false);
      }}
    >
      {busy ? "Rescoring" : "Use for matching"}
    </button>
  );
}
