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
  const { patchJob, hideJob, settleMarks, transitionApplication, beginJobMutation, endJobMutation, toast } = useApp();

  const mark = useCallback(
    async (job: Job, key: MarkKey) => {
      if (!beginJobMutation(job.id)) return;
      let released = false;
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
      const fromApplication = job.applied_at ? job.application_status ?? "applied" : null;
      const toApplication = key === "applied" ? (was ? null : job.application_status ?? "applied") : fromApplication;
      if (key === "applied") transitionApplication(fromApplication, toApplication);

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
        endJobMutation(job.id);
        released = true;
        settleMarks();
        toast(label, async () => {
          if (!beginJobMutation(job.id)) return;
          transitionApplication(toApplication, fromApplication);
          let undoReleased = false;
          try {
            const back = await putMark(job.id, undoBody);
            patchJob(job.id, fromResult(back));
            if (leaves) hideJob(job.id, false);
            endJobMutation(job.id);
            undoReleased = true;
            settleMarks();
          } catch {
            transitionApplication(fromApplication, toApplication);
            toast("Could not undo that change");
          } finally {
            if (!undoReleased) endJobMutation(job.id);
          }
        });
      } catch {
        patchJob(job.id, {
          is_saved: job.is_saved,
          review_state: job.review_state,
          applied_at: job.applied_at,
          application_status: job.application_status,
        });
        if (key === "applied") transitionApplication(toApplication, fromApplication);
        if (leaves) hideJob(job.id, false);
        toast("Could not save that change");
      } finally {
        if (!released) endJobMutation(job.id);
      }
    },
    [patchJob, hideJob, settleMarks, transitionApplication, beginJobMutation, endJobMutation, toast, listPage],
  );

  const setStatus = useCallback(
    async (job: Job, status: ApplicationStatus) => {
      if (!beginJobMutation(job.id)) return;
      let released = false;
      const was = job.application_status;
      const fromApplication = job.applied_at ? was ?? "applied" : null;
      const toApplication = status;
      patchJob(job.id, { application_status: status, applied_at: job.applied_at ?? new Date().toISOString() });
      transitionApplication(fromApplication, toApplication);
      try {
        const res = await putMark(job.id, { application_status: status });
        patchJob(job.id, fromResult(res));
        endJobMutation(job.id);
        released = true;
        settleMarks();
        toast(`${STATUS_LABEL[status]} recorded`, async () => {
          if (!beginJobMutation(job.id)) return;
          transitionApplication(toApplication, fromApplication);
          let undoReleased = false;
          try {
            const back = await putMark(job.id, was ? { application_status: was } : { applied: false });
            patchJob(job.id, fromResult(back));
            endJobMutation(job.id);
            undoReleased = true;
            settleMarks();
          } catch {
            transitionApplication(fromApplication, toApplication);
            toast("Could not undo that change");
          } finally {
            if (!undoReleased) endJobMutation(job.id);
          }
        });
      } catch {
        patchJob(job.id, { application_status: was, applied_at: job.applied_at });
        transitionApplication(toApplication, fromApplication);
        toast("Could not record that status");
      } finally {
        if (!released) endJobMutation(job.id);
      }
    },
    [patchJob, settleMarks, transitionApplication, beginJobMutation, endJobMutation, toast],
  );

  return { mark, setStatus };
}
