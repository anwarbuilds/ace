import { ResetForm } from "@/components/auth/ResetForm";
import { AuthCard } from "@/components/auth/AuthCard";
import { AuthWordmark } from "@/components/auth/AuthWordmark";
import { ThemeAwareAuthLayout } from "@/components/auth/ThemeAwareAuthLayout";

export const metadata = { title: "New password · ace" };

export default async function ResetPage({ searchParams }: PageProps<"/login/reset">) {
  const raw = (await searchParams).token;
  const token = Array.isArray(raw) ? raw[0] : raw;
  return (
    <ThemeAwareAuthLayout>
      <AuthCard className="auth-info-panel auth-reset-panel">
        <AuthWordmark compact linked={false} />
        <h1>Choose a new password</h1>
        <p className="auth-dialog-copy">At least 12 characters. Every signed-in browser will be signed out.</p>
        <ResetForm token={token ?? ""} />
      </AuthCard>
    </ThemeAwareAuthLayout>
  );
}
