import type { ReactNode } from "react";

import { AuthBackdrop } from "./AuthBackdrop";
import { AuthWordmark } from "./AuthWordmark";

export function ThemeAwareAuthLayout({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <main className="auth-stage">
      <AuthBackdrop />
      <header className="auth-stage-header">
        <AuthWordmark />
        {action ? <div className="auth-stage-action">{action}</div> : null}
      </header>
      <div className="auth-stage-content">{children}</div>
    </main>
  );
}
