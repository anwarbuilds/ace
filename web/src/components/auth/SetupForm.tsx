"use client";

import { useState } from "react";

import { RequestError, sendJson } from "@/lib/client";

/** The first visit only: create the one account, then go straight in. */
export function SetupForm({ next, needsToken }: { next: string; needsToken: boolean }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(form: FormData) {
    const password = String(form.get("password") ?? "");
    if (password !== form.get("again")) {
      setError("The two passwords differ.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await sendJson(
        "POST",
        "/api/auth/setup",
        { email: form.get("email"), password, setup_token: form.get("token") ?? "" },
        { redirectOn401: false },
      );
      window.location.assign(next);
      return;
    } catch (err) {
      setError(err instanceof RequestError ? err.message : "ace did not answer. Try again in a moment.");
    }
    setBusy(false);
  }

  return (
    <form className="auth-form" action={submit}>
      <div className="auth-field">
        <label htmlFor="email">Email</label>
        <input id="email" name="email" type="email" autoComplete="username" required autoFocus />
      </div>
      <div className="auth-field">
        <label htmlFor="password">Password, 12 or more characters</label>
        <input id="password" name="password" type="password" autoComplete="new-password" minLength={12} required />
      </div>
      <div className="auth-field">
        <label htmlFor="again">Password again</label>
        <input id="again" name="again" type="password" autoComplete="new-password" minLength={12} required />
      </div>
      {needsToken ? (
        <div className="auth-field">
          <label htmlFor="token">Setup code</label>
          <input id="token" name="token" type="password" autoComplete="off" required />
        </div>
      ) : null}
      {error ? (
        <p className="auth-err" role="alert">
          {error}
        </p>
      ) : null}
      <button className="btn btn-primary" type="submit" disabled={busy}>
        {busy ? "Creating" : "Create account"}
      </button>
    </form>
  );
}
