"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { Icon } from "@/components/Icon";
import { answerSections } from "@/lib/answers";
import type { Answer } from "@/lib/types";

import { useApp } from "./AppProvider";

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // The async clipboard needs a secure context, which plain http on a
    // LAN address does not get. This path is the one that usually runs.
    const t = document.createElement("textarea");
    t.value = text;
    t.style.position = "fixed";
    t.style.opacity = "0";
    document.body.appendChild(t);
    t.select();
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch {}
    document.body.removeChild(t);
    return ok;
  }
}

/** The floating "Answers" button and the drawer it opens: every saved
 *  answer a click from the clipboard, for forms the extension misses. */
export function AnswersDock({ answers }: { answers: Answer[] }) {
  const { answersOpen, setAnswersOpen, toast } = useApp();
  const path = usePathname();
  const [copied, setCopied] = useState<number | null>(null);
  const filled = answers.filter((a) => a.value);

  if (path.startsWith("/app/answers")) return null;

  if (!answersOpen)
    return (
      <button
        className={`btn btn-secondary ab-toggle${filled.length ? "" : " ab-empty"}`}
        onClick={() => setAnswersOpen(true)}
        title={filled.length ? "Your saved answers" : "Save the answers every form asks for"}
      >
        <Icon name="copy" size={14} />
        Answers
        {filled.length ? <span className="n">{filled.length}</span> : null}
      </button>
    );

  return (
    <div className="ab" role="dialog" aria-label="Your answers">
      <div className="ab-head">
        <h3>Your answers</h3>
        <span className="am-count">
          {filled.length} of {answers.length}
        </span>
        <span className="spacer" />
        <button className="iconbtn" onClick={() => setAnswersOpen(false)} aria-label="Close">
          <Icon name="x" />
        </button>
      </div>
      <div className="ab-body">
        {filled.length ? (
          answerSections(answers).map(([title, rows]) => (
            <div key={title}>
              <div className="ab-sec">{title}</div>
              {rows.map((a) => (
                <div key={a.id} className={`ab-row${a.value ? "" : " empty"}`}>
                  <span className="ab-l">{a.label}</span>
                  <span className={`ab-v${a.value ? "" : " blank"}`}>{a.value || "not set"}</span>
                  {a.value ? (
                    <button
                      className={`iconbtn ab-copy${copied === a.id ? " done" : ""}`}
                      title="Copy"
                      aria-label={`Copy ${a.label}`}
                      onClick={async () => {
                        if (await copyText(a.value)) {
                          setCopied(a.id);
                          setTimeout(() => setCopied(null), 1200);
                        } else toast("Could not copy");
                      }}
                    >
                      {copied === a.id ? "copied" : <Icon name="copy" size={14} />}
                    </button>
                  ) : null}
                </div>
              ))}
            </div>
          ))
        ) : (
          <p className="why" style={{ padding: "14px 10px" }}>
            These are the questions every application form asks. Fill them once and they are a click away on every form
            after that.
          </p>
        )}
      </div>
      <div className="ab-foot">
        <Link
          className={`btn ${filled.length ? "btn-secondary" : "btn-primary"} btn-sm`}
          href="/app/answers"
          onClick={() => setAnswersOpen(false)}
        >
          {filled.length ? "Edit" : "Fill these in"}
        </Link>
        <span className="spacer" />
        <span className="am-count">Esc closes</span>
      </div>
    </div>
  );
}
