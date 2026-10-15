import Link from "next/link";

export function AuthWordmark({ compact = false, linked = true }: { compact?: boolean; linked?: boolean }) {
  const word = (
    <span className={`auth-wordmark${compact ? " compact" : ""}`} aria-label="ace">
      <span>a</span>ce
    </span>
  );

  return linked ? (
    <Link className="auth-wordmark-link" href="/" aria-label="ace public home">
      {word}
    </Link>
  ) : (
    word
  );
}
