"use client";

import type { ReactNode } from "react";
import { useEffect, useRef } from "react";

export function AuthDialog({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const current = dialog.current;
    if (!current) return;
    current.showModal();
    const close = () => onClose();
    current.addEventListener("close", close);
    return () => current.removeEventListener("close", close);
  }, [onClose]);

  return (
    <dialog className="auth-dialog" ref={dialog} aria-labelledby="auth-dialog-title">
      <div className="auth-dialog-head">
        <h2 id="auth-dialog-title">{title}</h2>
        <button type="button" onClick={() => dialog.current?.close()} aria-label="Close">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M6 6l12 12M18 6 6 18" />
          </svg>
        </button>
      </div>
      <div className="auth-dialog-body">{children}</div>
    </dialog>
  );
}
