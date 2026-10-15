import Link from "next/link";

import { AuthCard } from "./AuthCard";
import { SecurityAssurance } from "./SecurityAssurance";

function LockMark() {
  return (
    <div className="auth-lock" aria-hidden="true">
      <svg className="auth-lock-ring" viewBox="0 0 80 80">
        <circle cx="40" cy="40" r="35" />
        <circle className="red" cx="40" cy="40" r="35" />
      </svg>
      <svg className="auth-lock-icon" viewBox="0 0 24 24">
        <rect x="5" y="10" width="14" height="11" rx="2" />
        <path d="M8.5 10V7.5a3.5 3.5 0 0 1 7 0V10M12 14v3" />
      </svg>
    </div>
  );
}

export function SignedOutCard() {
  return (
    <AuthCard className="auth-signedout-panel">
      <LockMark />
      <h1>You’re signed out</h1>
      <p className="auth-signedout-copy">
        Your session has ended securely. Sign back in to continue reviewing new pulls and tailoring resumes.
      </p>
      <div className="auth-signedout-actions">
        <Link className="auth-signin-again" href="/login">Sign in again <span aria-hidden="true">→</span></Link>
        <Link className="auth-public-home" href="/">Go to public home</Link>
      </div>
      <SecurityAssurance />
    </AuthCard>
  );
}
