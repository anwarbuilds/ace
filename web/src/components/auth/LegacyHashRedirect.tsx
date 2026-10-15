"use client";

import { useEffect } from "react";

/** Preserve bookmarks made by the retired single-page interface. */
export function LegacyHashRedirect() {
  useEffect(() => {
    const match = window.location.hash.match(/^#job\/(\d+)$/);
    if (match) window.location.replace(`/app/jobs/${match[1]}`);
  }, []);

  return null;
}
