"use client";

import Link from "next/link";
import { useState } from "react";

import { authErrorText, sendJson } from "@/lib/client";

export function SignOutPanel({ email }: { email: string | null }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function signOut() {
    setBusy(true);
    setError("");
    try {
      await sendJson("POST", "/api/auth/logout", undefined, { redirectOn401: false });
      // Reload every server component with the cleared session cookie.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign("/login?signed_out=1");
    } catch (err) {
      setError(authErrorText(err));
      setBusy(false);
    }
  }

  return (
    <section className="signout-card" aria-labelledby="signout-title">
      <h2 id="signout-title">Leave this browser?</h2>
      <p className="why">
        {email ? `You are signed in as ${email}. ` : ""}
        Signing out ends this browser session. Your opportunities, applications and settings stay saved.
      </p>
      <div className="signout-actions">
        <button className="btn primary" type="button" onClick={signOut} disabled={busy}>
          {busy ? "Signing out" : "Sign out"}
        </button>
        <Link className="btn ghost" href="/app/pulls">
          Cancel
        </Link>
      </div>
      {error ? (
        <p className="signout-error" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}
