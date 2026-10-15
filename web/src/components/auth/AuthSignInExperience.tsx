"use client";

import { useCallback, useState } from "react";

import { LoginForm } from "./LoginForm";
import { SetupForm } from "./SetupForm";
import { AuthCard } from "./AuthCard";
import { AuthDialog } from "./AuthDialog";
import { AuthLegalLinks } from "./AuthLegalLinks";
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
}: {
  next: string;
  ownerExists: boolean;
  setupAllowed: boolean;
  setupNeedsToken: boolean;
  resetByEmail: boolean;
  apiAvailable: boolean;
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

  const action = (
    <button className="auth-create" type="button" onClick={openCreate}>
      Create account
    </button>
  );

  return (
    <ThemeAwareAuthLayout action={action}>
      <AuthCard className="auth-signin-panel">
        <AuthWordmark compact linked={false} />
        <h1>Career Intelligence<br />Always On</h1>
        <p className="auth-tagline">Grow at your own pace.</p>
        <div className="auth-providers">
          <AuthProviderButton provider="google" featured onClick={() => setDialog("google")}>
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
        <AuthLegalLinks />
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
