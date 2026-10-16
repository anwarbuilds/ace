import type { ReactNode } from "react";

import { PublicThemeToggle } from "@/components/public/PublicThemeToggle";
import { WineArtwork } from "@/components/public/WineArtwork";

import { AuthWordmark } from "./AuthWordmark";

export function ThemeAwareAuthLayout({
  children,
  action,
  intro,
}: {
  children: ReactNode;
  action?: ReactNode;
  intro?: "Career intelligence" | "Private workspace";
}) {
  return (
    <main className="auth-stage wine-public">
      <WineArtwork />
      <header className="auth-stage-header">
        <AuthWordmark />
        <div className="auth-stage-action">
          <PublicThemeToggle />
          {action}
        </div>
      </header>
      <div className={`auth-stage-content${intro ? " auth-split" : ""}`}>
        {intro ? (
          <section className="auth-intro">
            <span>{intro}</span>
            <h2>Career intelligence,<br />always on.</h2>
            <p>Grow at your own pace.</p>
            {intro === "Career intelligence" ? <small>Your engineering opportunities, applications and resumes in one private workspace.</small> : null}
          </section>
        ) : null}
        <div className="auth-card-column">{children}</div>
      </div>
    </main>
  );
}
