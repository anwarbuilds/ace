"use client";

import { useState } from "react";

import { RequestError, sendJson } from "@/lib/client";

export function LoginForm({ next, resetByEmail }: { next: string; resetByEmail: boolean }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<"login" | "forgot" | "sent">("login");

  async function submit(form: FormData) {
    setBusy(true);
    setError("");
    try {
      if (mode === "forgot") {
        await sendJson("POST", "/api/auth/reset/request", { email: form.get("email") }, { redirectOn401: false });
        setMode("sent");
      } else {
        await sendJson(
          "POST",
          "/api/auth/login",
          { email: form.get("email"), password: form.get("password") },
          { redirectOn401: false },
        );
        // A full load, so every server component reads with the new cookie.
        window.location.assign(next);
        return;
      }
    } catch (err) {
      setError(err instanceof RequestError ? err.message : "ace did not answer. Try again in a moment.");
    }
    setBusy(false);
  }

  if (mode === "sent") {
    return (
      <div className="auth-form">
        <p className="auth-ok">If that address has an account, a reset link is on its way. It works for 30 minutes.</p>
        <button className="link-btn" onClick={() => setMode("login")}>
          Back to sign in
        </button>
      </div>
    );
  }

  return (
    <form className="auth-form" action={submit}>
      <div className="auth-field">
        <label htmlFor="email">Email</label>
        <input id="email" name="email" type="email" autoComplete="username" required autoFocus />
      </div>
      {mode === "login" ? (
        <div className="auth-field">
          <label htmlFor="password">Password</label>
          <input id="password" name="password" type="password" autoComplete="current-password" required />
        </div>
      ) : null}
      {error ? (
        <p className="auth-err" role="alert">
          {error}
        </p>
      ) : null}
      <button className="btn btn-primary" type="submit" disabled={busy}>
        {mode === "forgot" ? "Send reset link" : busy ? "Signing in" : "Sign in"}
      </button>
      <div className="auth-foot">
        {mode === "login" ? (
          resetByEmail ? (
            <button type="button" className="link-btn" onClick={() => setMode("forgot")}>
              Forgot password
            </button>
          ) : (
            <span>Forgot it? Set a new one on the server with create_owner.</span>
          )
        ) : (
          <button type="button" className="link-btn" onClick={() => setMode("login")}>
            Back to sign in
          </button>
        )}
      </div>
    </form>
  );
}
