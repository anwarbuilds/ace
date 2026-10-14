import { redirect } from "next/navigation";

import { LoginForm } from "@/components/auth/LoginForm";
import { authStatus } from "@/lib/api";
import { safeNext } from "@/lib/safeNext";

export const metadata = { title: "Sign in · ace" };

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const next = safeNext((await searchParams).next);
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
            <h1 className="auth-h">Create the owner account</h1>
            <p className="auth-sub">
              ace has one private account and no sign-up page. Create it on the machine that runs ace; the password is
              typed at a hidden prompt.
            </p>
            <pre>python -m backend.scripts.create_owner you@example.com</pre>
            <p className="auth-sub">In Docker, prefix it with docker exec -it ace-web-1. Then reload this page.</p>
          </>
        ) : (
          <>
            <h1 className="auth-h">Sign in</h1>
            <p className="auth-sub">Your opportunities, applications and answers are private to you.</p>
            <LoginForm next={next} resetByEmail={status.reset_by_email} />
          </>
        )}
      </div>
    </main>
  );
}
