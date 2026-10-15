import Link from "next/link";
import type { ReactNode } from "react";

import { AuthCard } from "./AuthCard";
import { AuthWordmark } from "./AuthWordmark";
import { ThemeAwareAuthLayout } from "./ThemeAwareAuthLayout";

export function PublicInfoCard({ title, children, back = false }: { title: string; children: ReactNode; back?: boolean }) {
  return (
    <ThemeAwareAuthLayout>
      <AuthCard className="auth-info-panel">
        <AuthWordmark compact linked={false} />
        <h1>{title}</h1>
        <div className="auth-info-copy">{children}</div>
        <Link className="auth-info-action" href={back ? "/" : "/login"}>{back ? "Back to public home" : "Sign in"}</Link>
      </AuthCard>
    </ThemeAwareAuthLayout>
  );
}
