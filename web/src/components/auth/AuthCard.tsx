import type { ComponentPropsWithoutRef } from "react";

export function AuthCard({ className = "", ...props }: ComponentPropsWithoutRef<"section">) {
  return <section {...props} className={`auth-panel ${className}`.trim()} />;
}
