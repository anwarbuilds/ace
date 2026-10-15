import type { ReactNode } from "react";

function GoogleIcon() {
  return (
    <svg className="auth-provider-icon google" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#4285F4" d="M21.6 12.23c0-.71-.06-1.23-.2-1.77H12v3.4h5.52a4.75 4.75 0 0 1-2.05 3.03l-.02.11 2.98 2.3.21.02c1.94-1.8 2.96-4.43 2.96-7.09Z" />
      <path fill="#34A853" d="M12 22c2.7 0 4.97-.89 6.64-2.42l-3.17-2.45c-.85.58-1.99.99-3.47.99a6.02 6.02 0 0 1-5.7-4.16l-.1.01-3.1 2.4-.04.1A10.02 10.02 0 0 0 12 22Z" />
      <path fill="#FBBC05" d="M6.3 13.96A6.2 6.2 0 0 1 5.96 12c0-.68.12-1.34.32-1.96v-.12L3.14 7.48l-.1.05A10.02 10.02 0 0 0 2 12c0 1.6.38 3.12 1.06 4.47l3.24-2.51Z" />
      <path fill="#EA4335" d="M12 5.88c1.88 0 3.15.81 3.88 1.49l2.83-2.76A9.63 9.63 0 0 0 12 2a10.02 10.02 0 0 0-8.94 5.53l3.22 2.51A6.04 6.04 0 0 1 12 5.88Z" />
    </svg>
  );
}

function MicrosoftIcon() {
  return (
    <svg className="auth-provider-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#F25022" d="M2 2h9.4v9.4H2z" />
      <path fill="#7FBA00" d="M12.6 2H22v9.4h-9.4z" />
      <path fill="#00A4EF" d="M2 12.6h9.4V22H2z" />
      <path fill="#FFB900" d="M12.6 12.6H22V22h-9.4z" />
    </svg>
  );
}

function EmailIcon() {
  return (
    <svg className="auth-provider-icon line" viewBox="0 0 24 24" aria-hidden="true">
      <rect x="2.5" y="4.5" width="19" height="15" rx="1.8" />
      <path d="m3.5 6 8.5 7 8.5-7" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg className="auth-provider-arrow" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 12h14m-5-5 5 5-5 5" />
    </svg>
  );
}

const ICONS: Record<"google" | "microsoft" | "email", ReactNode> = {
  google: <GoogleIcon />,
  microsoft: <MicrosoftIcon />,
  email: <EmailIcon />,
};

export function AuthProviderButton({
  provider,
  children,
  featured = false,
  onClick,
}: {
  provider: "google" | "microsoft" | "email";
  children: ReactNode;
  featured?: boolean;
  onClick: () => void;
}) {
  return (
    <button className={`auth-provider${featured ? " featured" : ""}`} type="button" onClick={onClick}>
      {ICONS[provider]}
      <span>{children}</span>
      <ArrowIcon />
    </button>
  );
}
