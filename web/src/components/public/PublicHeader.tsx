import Link from "next/link";

import { AuthWordmark } from "@/components/auth/AuthWordmark";

import { PublicThemeToggle } from "./PublicThemeToggle";

export function PublicHeader({ compact = false }: { compact?: boolean }) {
  return (
    <header className="wine-public-header">
      <AuthWordmark />
      <div className="wine-public-actions">
        <PublicThemeToggle />
        {!compact ? <Link className="wine-header-link" href="/login">Sign in</Link> : null}
        {!compact ? <Link className="wine-header-button" href="/login">Open workspace</Link> : null}
      </div>
    </header>
  );
}
