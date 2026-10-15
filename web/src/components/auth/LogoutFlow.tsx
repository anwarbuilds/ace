"use client";

import { useEffect, useState } from "react";

import { authErrorText, sendJson } from "@/lib/client";

import { AuthCard } from "./AuthCard";
import { ThemeAwareAuthLayout } from "./ThemeAwareAuthLayout";

export function LogoutFlow() {
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    sendJson("POST", "/api/auth/logout", undefined, { redirectOn401: false })
      .then(() => {
        if (active) window.location.replace("/signed-out");
      })
      .catch((err) => {
        if (active) setError(authErrorText(err));
      });
    return () => {
      active = false;
    };
  }, [attempt]);

  return (
    <ThemeAwareAuthLayout>
      <AuthCard className="auth-transition-panel" aria-live="polite">
        <div className="auth-transition-spinner" aria-hidden="true" />
        <h1>{error ? "Sign-out did not finish" : "Signing out"}</h1>
        {error ? (
          <>
            <p>{error}</p>
            <button type="button" onClick={() => { setError(""); setAttempt((value) => value + 1); }}>Try again</button>
          </>
        ) : (
          <p>Ending this browser session securely.</p>
        )}
      </AuthCard>
    </ThemeAwareAuthLayout>
  );
}
