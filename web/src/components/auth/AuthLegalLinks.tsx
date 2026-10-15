import Link from "next/link";

export function AuthLegalLinks() {
  return (
    <p className="auth-legal">
      By continuing, you agree to our <Link href="/terms">Terms of Service</Link>
      <br />
      and <Link href="/privacy">Privacy Policy</Link>.
    </p>
  );
}
