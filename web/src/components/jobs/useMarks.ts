"use client";

import { useCallback } from "react";

import { useApp } from "@/components/shell/AppProvider";
import { putMark, type MarkBody } from "@/lib/client";
import { STATUS_LABEL } from "@/lib/format";
import type { ApplicationStatus, Job, MarkResult } from "@/lib/types";

export type MarkKey = "saved" | "reviewed" | "dismissed" | "applied";

function fromResult(r: MarkResult): Partial<Job> {
  return {
    is_saved: r.is_saved,
    review_state: r.review_state,
    applied_at: r.applied_at,
    application_status: r.application_status,
    status_changed_at: r.status_changed_at,
    status_note: r.status_note,
  };
}

function current(j: Job, key: MarkKey): boolean {
  if (key === "saved") return j.is_saved;
  if (key === "applied") return Boolean(j.applied_at);
  return j.review_state === key;
}

/** Marks with an optimistic update and a toast that can undo them. */
export function useMarks(listPage?: string) {
  const { patchJob, hideJob, refreshMarks, toast } = useApp();

  const mark = useCallback(
    async (job: Job, key: MarkKey) => {
      const was = current(job, key);
      const body: MarkBody =
        key === "saved"
          ? { saved: !was }
          : key === "applied"
            ? { applied: !was }
            : was
              ? { clear_review: true }
              : { review_state: key };
      const undoBody: MarkBody =
        key === "saved"
          ? { saved: was }
          : key === "applied"
            ? { applied: was }
            : was
              ? { review_state: key }
              : { clear_review: true };
      const label = {
        saved: was ? "Removed from saved" : "Saved",
        reviewed: was ? "Review cleared" : "Marked reviewed",
        dismissed: was ? "Restored" : "Marked not relevant",
        applied: was ? "Applied cleared" : "Marked applied",
      }[key];

      // Shown at once; the server's answer then replaces the guess.
      const guess: Partial<Job> =
        key === "saved"
          ? { is_saved: !was }
          : key === "applied"
            ? {
                applied_at: was ? null : new Date().toISOString(),
                application_status: was ? null : job.application_status ?? "applied",
              }
            : { review_state: was ? null : key };
      patchJob(job.id, guess);

      // Un-marking on the page that lists that mark takes the row away.
      const leaves =
        was &&
        ((listPage === "saved" && key === "saved") ||
          (listPage === "archive" && (key === "reviewed" || key === "dismissed")) ||
          (listPage === "applied" && key === "applied"));
      if (leaves) hideJob(job.id, true);

      try {
        const res = await putMark(job.id, body);
        patchJob(job.id, fromResult(res));
        refreshMarks();
        toast(label, async () => {
          try {
            const back = await putMark(job.id, undoBody);
            patchJob(job.id, fromResult(back));
            if (leaves) hideJob(job.id, false);
            refreshMarks();
          } catch {
            toast("Could not undo that change");
          }
        });
      } catch {
        patchJob(job.id, {
          is_saved: job.is_saved,
          review_state: job.review_state,
          applied_at: job.applied_at,
          application_status: job.application_status,
        });
        if (leaves) hideJob(job.id, false);
        toast("Could not save that change");
      }
    },
    [patchJob, hideJob, refreshMarks, toast, listPage],
  );

  const setStatus = useCallback(
    async (job: Job, status: ApplicationStatus) => {
      const was = job.application_status;
      patchJob(job.id, { application_status: status, applied_at: job.applied_at ?? new Date().toISOString() });
      try {
        const res = await putMark(job.id, { application_status: status });
        patchJob(job.id, fromResult(res));
        refreshMarks();
        toast(`${STATUS_LABEL[status]} recorded`, async () => {
          try {
            const back = await putMark(job.id, was ? { application_status: was } : { applied: false });
            patchJob(job.id, fromResult(back));
            refreshMarks();
          } catch {
            toast("Could not undo that change");
          }
        });
      } catch {
        patchJob(job.id, { application_status: was, applied_at: job.applied_at });
        toast("Could not record that status");
      }
    },
    [patchJob, refreshMarks, toast],
  );

  return { mark, setStatus };
}
