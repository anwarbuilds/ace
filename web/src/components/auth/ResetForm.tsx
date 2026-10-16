"use client";

import { useState } from "react";

import { authErrorText, sendJson } from "@/lib/client";

export function ResetForm({ code: initialCode, email: initialEmail }: { code: string; email: string }) {
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  async function submit(form: FormData) {
    const password = String(form.get("password") ?? "");
    if (password !== form.get("again")) {
      setError("The two passwords differ.");
      return;
    }
    try {
      await sendJson(
        "POST",
        "/api/auth/reset/confirm",
        { email: form.get("email"), code: form.get("code"), new_password: password },
        { redirectOn401: false },
      );
      setDone(true);
    } catch (err) {
      setError(authErrorText(err));
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
        <label htmlFor="email">Email</label>
        <input id="email" name="email" type="email" autoComplete="username" defaultValue={initialEmail} required />
      </div>
      <div className="auth-field">
        <label htmlFor="code">Reset code</label>
        <input
          id="code"
          name="code"
          type="text"
          autoComplete="one-time-code"
          defaultValue={initialCode}
          minLength={8}
          maxLength={9}
          placeholder="ABCD EFGH"
          required
        />
      </div>
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
      <button className="btn btn-primary" type="submit">
        Set password
      </button>
    </form>
  );
}
