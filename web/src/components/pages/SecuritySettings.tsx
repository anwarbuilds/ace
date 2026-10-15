"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useApp } from "@/components/shell/AppProvider";
import { RequestError, sendJson } from "@/lib/client";

export interface SessionRow {
  id: number;
  created_at: string;
  last_seen_at: string;
  user_agent: string;
  current: boolean;
}

export interface TokenRow {
  id: number;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
}

function browserName(ua: string): string {
  if (!ua) return "Unknown browser";
  const browser = /Edg\//.test(ua)
    ? "Edge"
    : /Chrome\//.test(ua)
      ? "Chrome"
      : /Firefox\//.test(ua)
        ? "Firefox"
        : /Safari\//.test(ua)
          ? "Safari"
          : "Browser";
  const os = /Mac OS X/.test(ua)
    ? "macOS"
    : /Windows/.test(ua)
      ? "Windows"
      : /Android/.test(ua)
        ? "Android"
        : /iPhone|iPad/.test(ua)
          ? "iOS"
          : /Linux/.test(ua)
            ? "Linux"
            : "";
  return os ? `${browser} on ${os}` : browser;
}

function message(err: unknown): string {
  return err instanceof RequestError ? err.message : "ace did not answer. Try again in a moment.";
}

export function SecuritySettings({
  email,
  sessions,
  tokens,
  when,
}: {
  email: string;
  sessions: SessionRow[];
  tokens: TokenRow[];
  /** Server-formatted dates, keyed by ISO string, in the reader's zone. */
  when: Record<string, string>;
}) {
  const router = useRouter();
  const { toast } = useApp();
  const [pwError, setPwError] = useState("");
  const others = sessions.filter((s) => !s.current).length;
  const [allSessions, setAllSessions] = useState(false);
  // The current browser first, then the most recently active.
  const ordered = [...sessions].sort((a, b) => Number(b.current) - Number(a.current));
  const shown = allSessions ? ordered : ordered.slice(0, 4);

  async function revokeOthers() {
    try {
      const r = await sendJson<{ revoked: number }>("POST", "/api/auth/sessions/revoke-others");
      toast(r.revoked === 1 ? "Signed out 1 other browser" : `Signed out ${r.revoked} other browsers`);
      router.refresh();
    } catch (err) {
      toast(message(err));
    }
  }

  async function changePassword(form: FormData) {
    setPwError("");
    const next = String(form.get("new") ?? "");
    if (next !== form.get("again")) {
      setPwError("The two new passwords differ.");
      return;
    }
    try {
      await sendJson("POST", "/api/auth/password", { current_password: form.get("current"), new_password: next });
      toast("Password changed. Other browsers were signed out.");
      router.refresh();
    } catch (err) {
      setPwError(message(err));
    }
  }

  return (
    <>
      <div className="sect">
        <p className="eyebrow">Sign-in</p>
        <div className="gaprow">
          <span>Signed in as {email}</span>
          <Link className="link-btn" href="/logout">
            Sign out
          </Link>
        </div>
        <div className="sec-list" style={{ marginTop: 12 }}>
          {shown.map((s) => (
            <div className="sec-row" key={s.id}>
              <span className="sec-main">
                {browserName(s.user_agent)}
                {s.current ? ", this browser" : ""}
              </span>
              <span className="sec-meta">active {when[s.last_seen_at] ?? ""}</span>
            </div>
          ))}
        </div>
        <div className="controls" style={{ paddingLeft: 0 }}>
          {sessions.length > shown.length ? (
            <button className="link-btn" onClick={() => setAllSessions(true)}>
              Show all {sessions.length}
            </button>
          ) : null}
          {others ? (
            <button className="btn btn-secondary btn-sm" onClick={revokeOthers}>
              Sign out {others === 1 ? "the other browser" : `${others} other browsers`}
            </button>
          ) : null}
        </div>
        <form className="sec-form" action={changePassword}>
          <input name="current" type="password" placeholder="Current password" autoComplete="current-password" required />
          <input name="new" type="password" placeholder="New password, 12 or more" autoComplete="new-password" minLength={12} required />
          <input name="again" type="password" placeholder="New password again" autoComplete="new-password" minLength={12} required />
          <button className="btn btn-secondary btn-sm" type="submit">
            Change password
          </button>
        </form>
        {pwError ? (
          <p className="auth-err" role="alert" style={{ marginTop: 8 }}>
            {pwError}
          </p>
        ) : null}
      </div>
      <div className="sect">
        <p className="eyebrow">Chrome extension</p>
        <p className="why">
          {tokens.length ? `${tokens.length} paired. ` : "Not paired. "}
          Pairing and unpairing are on the <Link href="/app/extension">Autofill Extension</Link> page.
        </p>
      </div>
    </>
  );
}
