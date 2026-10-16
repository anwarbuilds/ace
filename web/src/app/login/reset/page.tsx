import { ResetForm } from "@/components/auth/ResetForm";
import { AuthCard } from "@/components/auth/AuthCard";
import { AuthWordmark } from "@/components/auth/AuthWordmark";
import { ThemeAwareAuthLayout } from "@/components/auth/ThemeAwareAuthLayout";

export const metadata = { title: "New password · ace" };

export default async function ResetPage({ searchParams }: PageProps<"/login/reset">) {
  const params = await searchParams;
  const rawCode = params.code;
  const rawEmail = params.email;
  const code = Array.isArray(rawCode) ? rawCode[0] : rawCode;
  const email = Array.isArray(rawEmail) ? rawEmail[0] : rawEmail;
  return (
    <ThemeAwareAuthLayout>
      <AuthCard className="auth-info-panel auth-reset-panel">
        <AuthWordmark compact linked={false} />
        <h1>Choose a new password</h1>
        <p className="auth-dialog-copy">At least 12 characters. Every signed-in browser will be signed out.</p>
        <ResetForm code={code ?? ""} email={email ?? ""} />
      </AuthCard>
    </ThemeAwareAuthLayout>
  );
}
