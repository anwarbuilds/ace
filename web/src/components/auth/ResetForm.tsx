"use client";

import { useState } from "react";

import { RequestError, sendJson } from "@/lib/client";

export function ResetForm({ token }: { token: string }) {
  const [error, setError] = useState(token ? "" : "This link is incomplete. Ask for a new one from the sign-in page.");
  const [done, setDone] = useState(false);

  async function submit(form: FormData) {
    const password = String(form.get("password") ?? "");
    if (password !== form.get("again")) {
      setError("The two passwords differ.");
      return;
    }
    try {
      await sendJson("POST", "/api/auth/reset/confirm", { token, new_password: password }, { redirectOn401: false });
      setDone(true);
    } catch (err) {
      setError(err instanceof RequestError ? err.message : "ace did not answer. Try again in a moment.");
    }
  }

  if (done) {
    return (
      <div className="auth-form">
        <p className="auth-ok">Password changed.</p>
        <a className="btn btn-primary" href="/login">
          Sign in
        </a>
      </div>
    );
  }

  return (
    <form className="auth-form" action={submit}>
      <div className="auth-field">
        <label htmlFor="password">New password</label>
        <input id="password" name="password" type="password" autoComplete="new-password" minLength={12} required />
      </div>
      <div className="auth-field">
        <label htmlFor="again">Type it again</label>
        <input id="again" name="again" type="password" autoComplete="new-password" minLength={12} required />
      </div>
      {error ? (
        <p className="auth-err" role="alert">
          {error}
        </p>
      ) : null}
      <button className="btn btn-primary" type="submit" disabled={!token}>
        Set password
      </button>
    </form>
  );
}
