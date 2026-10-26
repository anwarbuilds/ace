"use client";

import { useEffect, useState } from "react";
import { clean } from "@/lib/format";
import { companyLogoFor } from "@/lib/companyLogos";

type LogoSize = "compact" | "small" | "table" | "large";

// Identity-keyed state lets a reused row recover from the previous image's
// failure. Dynamic assets use ACE's authenticated proxy, never a logo service.
export function CompanyLogo({ name, size = "small", className = "" }: { name: string; size?: LogoSize; className?: string }) {
  const label = clean(name).trim() || "Company";
  const asset = companyLogoFor(name)?.asset;
  const src = asset ? `/company-logos/${asset}` : name.trim() ? `/api/company-logo?name=${encodeURIComponent(name)}` : undefined;
  return <LogoImage key={`${label}:${src ?? ""}`} name={label} src={src} dynamic={!asset} size={size} className={className} />;
}

function LogoImage({ name, src, dynamic, size, className }: { name: string; src?: string; dynamic: boolean; size: LogoSize; className: string }) {
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(!dynamic);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!src || !failed || !dynamic || attempt >= 2) return;
    // A busy/offline image must not leave this mounted row on initials forever.
    // Bounded retries still use the backend's shared cache and refusal policy.
    const timer = window.setTimeout(() => { setAttempt(n => n + 1); setFailed(false); }, attempt ? 15_000 : 2_000);
    return () => window.clearTimeout(timer);
  }, [src, failed, dynamic, attempt]);
  const initials = name.split(/\s+/).slice(0, 2).map(word => Array.from(word)[0]).join("").toLocaleUpperCase();
  return <span className={`company-logo company-logo--${size} ${className}`.trim()} title={src && !failed ? loaded ? `${name} official website icon` : `${name}: checking official logo` : `${name}: logo unavailable`}>
    {(!src || failed || !loaded) && <span aria-label={`${name} monogram`}>{initials}</span>}
    {src && !failed && /* eslint-disable-next-line @next/next/no-img-element */
      <img key={attempt} ref={element => { if (element?.complete) { if (element.naturalWidth === 0) setFailed(true); else if (!loaded) setLoaded(true); } }} src={attempt ? `${src}&retry=${attempt}` : src} alt={`${name} logo`} aria-hidden={!loaded} data-pending={!loaded || undefined} loading={size === "large" ? "eager" : "lazy"} referrerPolicy="no-referrer" width={size === "large" ? 56 : 28} height={size === "large" ? 56 : 28} decoding="async" onLoad={() => { setFailed(false); setLoaded(true); }} onError={() => { setLoaded(false); setFailed(true); }} />}
  </span>;
}
