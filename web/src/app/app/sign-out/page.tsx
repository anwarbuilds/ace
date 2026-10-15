import { SignOutPanel } from "@/components/auth/SignOutPanel";
import { authStatus } from "@/lib/api";

export const metadata = { title: "Sign out · ace" };

export default async function SignOutPage() {
  const auth = await authStatus();

  return (
    <div className="pg">
      <div className="page-hero">
        <div>
          <div className="eyebrow">Account</div>
          <h1 className="h1">Sign out</h1>
        </div>
      </div>
      <SignOutPanel email={auth?.email ?? null} />
    </div>
  );
}
