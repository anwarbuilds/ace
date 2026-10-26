"use client";

import { useEffect, useRef, useState } from "react";

// Tall enough for a typical recruiting email; longer ones scroll inside.
const MAX_HEIGHT = 640;

/**
 * The email exactly as it arrived, in a frame that cannot run scripts.
 *
 * The server rebuilt the HTML from an allowlist and gave it a content
 * policy that loads nothing from the network. The sandbox has no
 * allow-scripts, so allow-same-origin only lets this page measure the
 * frame's height; links open in a new tab.
 */
export function EmailFrame({ document, title }: { document: string; title: string }) {
  const frame = useRef<HTMLIFrameElement>(null);
  const watcher = useRef<ResizeObserver | null>(null);
  const [height, setHeight] = useState(260);

  const measure = () => {
    const root = frame.current?.contentDocument?.documentElement;
    if (root) setHeight(Math.min(MAX_HEIGHT, Math.max(120, root.scrollHeight + 2)));
  };
  const loaded = () => {
    measure();
    watcher.current?.disconnect();
    const body = frame.current?.contentDocument?.body;
    if (body && typeof ResizeObserver !== "undefined") {
      watcher.current = new ResizeObserver(measure);
      watcher.current.observe(body);
    }
  };
  useEffect(() => () => watcher.current?.disconnect(), []);

  return (
    <iframe
      ref={frame}
      className="inbox-frame"
      title={title}
      srcDoc={document}
      sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
      referrerPolicy="no-referrer"
      onLoad={loaded}
      style={{ height }}
    />
  );
}
