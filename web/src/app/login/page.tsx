import { redirect } from "next/navigation";

import { AuthSignInExperience } from "@/components/auth/AuthSignInExperience";
import { authStatus } from "@/lib/api";
import { safeNext } from "@/lib/safeNext";

export const metadata = { title: "Sign in · ace" };

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const params = await searchParams;
  const next = safeNext(params.next);
  const oauthError = Array.isArray(params.oauth_error) ? params.oauth_error[0] : params.oauth_error;
  const emailChanged = params.email_changed === "1";
  const status = await authStatus();

  if (status?.signed_in) redirect(next);

  return (
    <AuthSignInExperience
      next={next}
      apiAvailable={status !== null}
      googleSignIn={status?.google_sign_in ?? false}
      oauthError={oauthError ?? ""}
      emailChanged={emailChanged}
      ownerExists={status?.owner_exists ?? true}
      setupAllowed={status?.setup_allowed ?? false}
      setupNeedsToken={status?.setup_needs_token ?? false}
      resetByEmail={status?.reset_by_email ?? false}
    />
  );
}
