import { redirect } from "next/navigation";

import { LoginForm } from "@/components/auth/LoginForm";
import { SetupForm } from "@/components/auth/SetupForm";
import { authStatus } from "@/lib/api";
import { safeNext } from "@/lib/safeNext";

export const metadata = { title: "Sign in · ace" };

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const params = await searchParams;
  const next = safeNext(params.next);
  const signedOut = params.signed_out === "1";
  const status = await authStatus();

  if (status?.signed_in) redirect(next);

  return (
    <main className="auth">
      <div className="auth-card">
        <span className="brand-name">ace</span>
        {status === null ? (
          <>
            <h1 className="auth-h">ace is not answering</h1>
            <p className="auth-sub">
              The API did not respond. Start it, then reload this page.
            </p>
          </>
        ) : !status.owner_exists ? (
          <>
            <h1 className="auth-h">Create your account</h1>
            {status.setup_allowed ? (
              <>
                <p className="auth-sub">
                  ace has one private account. Create it now; after this, the page only signs you in.
                </p>
                <SetupForm next={next} needsToken={status.setup_needs_token} />
              </>
            ) : (
              <p className="auth-sub">
                For safety, the account can only be created from the computer that runs ace. Open this page there.
              </p>
            )}
          </>
        ) : (
          <>
            <h1 className="auth-h">Sign in</h1>
            <p className="auth-sub">Your opportunities, applications and answers are private to you.</p>
            {signedOut ? <p className="auth-ok auth-status" role="status">You are signed out.</p> : null}
            <LoginForm next={next} resetByEmail={status.reset_by_email} />
          </>
        )}
      </div>
    </main>
  );
}
