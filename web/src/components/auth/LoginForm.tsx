"use client";

import { useState } from "react";

import { authErrorText, sendJson } from "@/lib/client";

type Mode = "login" | "login-code" | "forgot" | "reset-code";

interface LoginResult {
  ok: boolean;
  verification_required?: boolean;
}

export function LoginForm({ next, resetByEmail }: { next: string; resetByEmail: boolean }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [email, setEmail] = useState("");
  const [mode, setMode] = useState<Mode>("login");

  function returnToLogin(message = "") {
    setMode("login");
    setError("");
    setNotice(message);
  }

  async function submit(form: FormData) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (mode === "forgot") {
        await sendJson(
          "POST",
          "/api/auth/reset/request",
          { email },
          { redirectOn401: false },
        );
        setMode("reset-code");
      } else if (mode === "reset-code") {
        const password = String(form.get("password") ?? "");
        if (password !== String(form.get("again") ?? "")) {
          setError("The two passwords differ.");
          setBusy(false);
          return;
        }
        await sendJson(
          "POST",
          "/api/auth/reset/confirm",
          { email, code: form.get("code"), new_password: password },
          { redirectOn401: false },
        );
        returnToLogin("Password changed. Sign in with your new password.");
      } else if (mode === "login-code") {
        await sendJson(
          "POST",
          "/api/auth/login/verify",
          { email, code: form.get("code") },
          { redirectOn401: false },
        );
        window.location.assign(next);
        return;
      } else {
        const result = await sendJson<LoginResult>(
          "POST",
          "/api/auth/login",
          { email, password: form.get("password") },
          { redirectOn401: false },
        );
        if (result.verification_required) {
          setMode("login-code");
        } else {
          window.location.assign(next);
          return;
        }
      }
    } catch (err) {
      setError(authErrorText(err));
    }
    setBusy(false);
  }

  const codeMode = mode === "login-code" || mode === "reset-code";

  return (
    <form className="auth-form" action={submit}>
      {codeMode ? (
        <p className="auth-ok">
          {mode === "login-code"
            ? `We sent a sign-in code to ${email}. It works for 10 minutes.`
            : `If ${email} has an account, a reset code is on its way. It works for 10 minutes.`}
        </p>
      ) : null}
      {mode === "login" || mode === "forgot" ? (
        <div className="auth-field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
            autoFocus
          />
        </div>
      ) : (
        <div className="auth-field">
          <label htmlFor="code">Verification code</label>
          <input
            id="code"
            name="code"
            type="text"
            autoComplete="one-time-code"
            inputMode="text"
            minLength={8}
            maxLength={9}
            placeholder="ABCD EFGH"
            required
            autoFocus
          />
        </div>
      )}
      {mode === "login" ? (
        <div className="auth-field">
          <label htmlFor="password">Password</label>
          <input id="password" name="password" type="password" autoComplete="current-password" required />
        </div>
      ) : null}
      {mode === "reset-code" ? (
        <>
          <div className="auth-field">
            <label htmlFor="password">New password</label>
            <input id="password" name="password" type="password" autoComplete="new-password" minLength={12} required />
          </div>
          <div className="auth-field">
            <label htmlFor="again">Type it again</label>
            <input id="again" name="again" type="password" autoComplete="new-password" minLength={12} required />
          </div>
        </>
      ) : null}
      {notice ? <p className="auth-ok">{notice}</p> : null}
      {error ? (
        <p className="auth-err" role="alert">
          {error}
        </p>
      ) : null}
      <button className="btn btn-primary" type="submit" disabled={busy}>
        {busy
          ? "Please wait"
          : mode === "forgot"
            ? "Send reset code"
            : mode === "reset-code"
              ? "Set password"
              : mode === "login-code"
                ? "Verify and sign in"
                : "Sign in"}
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
          <button type="button" className="link-btn" onClick={() => returnToLogin()}>
            Back to sign in
          </button>
        )}
      </div>
    </form>
  );
}
