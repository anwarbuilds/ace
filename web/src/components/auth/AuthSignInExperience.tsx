"use client";

import { useCallback, useState } from "react";

import { LoginForm } from "./LoginForm";
import { SetupForm } from "./SetupForm";
import { AuthCard } from "./AuthCard";
import { AuthDialog } from "./AuthDialog";
import { AuthProviderButton } from "./AuthProviderButton";
import { AuthWordmark } from "./AuthWordmark";
import { ThemeAwareAuthLayout } from "./ThemeAwareAuthLayout";

type DialogKind = "email" | "create" | "google" | "microsoft" | "offline" | null;

export function AuthSignInExperience({
  next,
  ownerExists,
  setupAllowed,
  setupNeedsToken,
  resetByEmail,
  apiAvailable,
  googleSignIn,
  oauthError,
  emailChanged,
}: {
  next: string;
  ownerExists: boolean;
  setupAllowed: boolean;
  setupNeedsToken: boolean;
  resetByEmail: boolean;
  apiAvailable: boolean;
  googleSignIn: boolean;
  oauthError: string;
  emailChanged: boolean;
}) {
  const [dialog, setDialog] = useState<DialogKind>(null);
  const close = useCallback(() => setDialog(null), []);

  function openEmail() {
    if (!apiAvailable) setDialog("offline");
    else setDialog(ownerExists ? "email" : "create");
  }

  function openCreate() {
    if (!apiAvailable) setDialog("offline");
    else setDialog("create");
  }

  function openGoogle() {
    if (!apiAvailable) {
      setDialog("offline");
    } else {
      setDialog("google");
    }
  }

  const oauthMessage = oauthError
    ? oauthError === "cancelled"
      ? "Google sign-in was cancelled."
      : oauthError === "owner_mismatch"
        ? "That Google account is not the owner of this workspace."
        : oauthError === "not_configured"
          ? "Google sign-in has not been configured for this workspace."
          : "Google sign-in could not be completed. Please try again or continue with Email."
    : "";

  const action = !ownerExists ? (
    <button className="auth-create" type="button" onClick={openCreate}>
      Create account
    </button>
  ) : null;

  return (
    <ThemeAwareAuthLayout action={action} intro="Career intelligence">
      <AuthCard className="auth-signin-panel">
        <AuthWordmark compact linked={false} />
        <h1>Welcome back</h1>
        <p className="auth-tagline">Sign in to your ACE account.</p>
        {emailChanged ? <p className="auth-status">Email verified. Sign in with your new address.</p> : null}
        {oauthMessage ? <p className="auth-provider-error" role="alert">{oauthMessage}</p> : null}
        <div className="auth-providers">
          <AuthProviderButton
            provider="google"
            featured
            href={apiAvailable && googleSignIn ? `/api/auth/google/start?next=${encodeURIComponent(next)}` : undefined}
            onClick={apiAvailable && googleSignIn ? undefined : openGoogle}
          >
            Continue with Google
          </AuthProviderButton>
          <AuthProviderButton provider="microsoft" onClick={() => setDialog("microsoft")}>
            Continue with Microsoft
          </AuthProviderButton>
          <AuthProviderButton provider="email" onClick={openEmail}>
            Continue with Email
          </AuthProviderButton>
        </div>
        <div className="auth-or"><span>or</span></div>
        <div className="auth-owner-only">
          <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8.5 10V7.5a3.5 3.5 0 0 1 7 0V10" /></svg>
          Owner-only access
        </div>
        <p className="auth-legal">Secure owner authentication is required. Public registration is disabled.</p>
      </AuthCard>

      {dialog === "email" ? (
        <AuthDialog title="Continue with Email" onClose={close}>
          <LoginForm next={next} resetByEmail={resetByEmail} />
        </AuthDialog>
      ) : null}
      {dialog === "create" ? (
        <AuthDialog title={ownerExists ? "Private workspace" : "Create your account"} onClose={close}>
          {ownerExists ? (
            <p className="auth-dialog-copy">ace has one private owner account. Sign in with the owner email to continue.</p>
          ) : setupAllowed ? (
            <>
              <p className="auth-dialog-copy">Create the single owner account for this ace workspace.</p>
              <SetupForm next={next} needsToken={setupNeedsToken} />
            </>
          ) : (
            <p className="auth-dialog-copy">Account creation is available only from the computer that runs ace.</p>
          )}
        </AuthDialog>
      ) : null}
      {dialog === "google" || dialog === "microsoft" ? (
        <AuthDialog title={`${dialog === "google" ? "Google" : "Microsoft"} sign-in`} onClose={close}>
          <p className="auth-dialog-copy">
            This private workspace has not configured {dialog === "google" ? "Google" : "Microsoft"} sign-in. Continue with Email instead.
          </p>
          <button className="auth-dialog-primary" type="button" onClick={() => setDialog(ownerExists ? "email" : "create")}>
            Continue with Email
          </button>
        </AuthDialog>
      ) : null}
      {dialog === "offline" ? (
        <AuthDialog title="ace is not answering" onClose={close}>
          <p className="auth-dialog-copy">The sign-in service did not respond. Start the API, then try again.</p>
        </AuthDialog>
      ) : null}
    </ThemeAwareAuthLayout>
  );
}
