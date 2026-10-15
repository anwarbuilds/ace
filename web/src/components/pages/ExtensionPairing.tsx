"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { useApp } from "@/components/shell/AppProvider";
import { RequestError, sendJson } from "@/lib/client";

import type { TokenRow } from "./SecuritySettings";

function message(err: unknown): string {
  return err instanceof RequestError ? err.message : "ace did not answer. Try again in a moment.";
}

/** Pair the extension with a one-time code, and unpair it. The extension
 *  gets its own revocable key that can read the answer bank and history
 *  and nothing else. */
export function ExtensionPairing({ tokens, when }: { tokens: TokenRow[]; when: Record<string, string> }) {
  const router = useRouter();
  const { toast } = useApp();
  const [code, setCode] = useState<string | null>(null);

  async function pair() {
    try {
      const r = await sendJson<{ code: string }>("POST", "/api/extension/pairing");
      setCode(r.code);
    } catch (err) {
      toast(message(err));
    }
  }

  async function revoke(id: number) {
    try {
      await sendJson("DELETE", `/api/extension/tokens/${id}`);
      toast("Extension unpaired");
      router.refresh();
    } catch (err) {
      toast(message(err));
    }
  }

  return (
    <div className="pairing">
      {code ? (
        <div className="pair-box">
          <span className="pair-code" aria-label="Pairing code">
            {code}
          </span>
          <p className="quiet-note">Type it in the extension under Connection. Shown once; it works for 10 minutes.</p>
        </div>
      ) : null}
      <button className="btn primary" onClick={pair}>
        {code ? "Make a new code" : "Pair the extension"}
      </button>
      <div className="pair-list">
        {tokens.length ? (
          tokens.map((t) => (
            <div className="lineitem" key={t.id}>
              <span>
                <strong>{t.name}</strong> <span className="mono">{t.prefix}</span>
                <br />
                {t.last_used_at ? `Last used ${when[t.last_used_at] ?? ""}` : "Not used yet"}
              </span>
              <button className="btn ghost" onClick={() => revoke(t.id)}>
                Unpair
              </button>
            </div>
          ))
        ) : (
          <p className="quiet-note">No extension is paired yet.</p>
        )}
      </div>
    </div>
  );
}
