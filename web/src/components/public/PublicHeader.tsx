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
        {!compact ? <Link className="wine-header-button" href="/login?next=%2Fapp%2Fpulls">Preview workspace</Link> : null}
      </div>
    </header>
  );
}
