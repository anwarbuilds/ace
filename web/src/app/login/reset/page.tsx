import { ResetForm } from "@/components/auth/ResetForm";

export const metadata = { title: "New password · ace" };

export default async function ResetPage({ searchParams }: PageProps<"/login/reset">) {
  const raw = (await searchParams).token;
  const token = Array.isArray(raw) ? raw[0] : raw;
  return (
    <main className="auth">
      <div className="auth-card">
        <span className="brand-name">ace</span>
        <h1 className="auth-h">Choose a new password</h1>
        <p className="auth-sub">At least 12 characters. Every signed-in browser will be signed out.</p>
        <ResetForm token={token ?? ""} />
      </div>
    </main>
  );
}
