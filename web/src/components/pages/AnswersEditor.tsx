"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Icon } from "@/components/Icon";
import { useApp } from "@/components/shell/AppProvider";
import { answerSections } from "@/lib/answers";
import { getJson, sendJson } from "@/lib/client";
import type { Answer, HistoryEntry } from "@/lib/types";

interface Row {
  key: string;
  label: string;
  value: string;
  kind: Answer["kind"];
  options: string[];
  hint: string;
  known: boolean;
}

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const YEARS = Array.from({ length: 2036 - 1990 + 1 }, (_, i) => 2036 - i);

const toRow = (a: Answer): Row => ({
  key: `a${a.id}`,
  label: a.label,
  value: a.value,
  kind: a.kind,
  options: a.options,
  hint: a.hint,
  known: a.known,
});

const blankHistory = (): HistoryEntry => ({
  employer: "",
  job_title: "",
  location: "",
  is_current: false,
  start_month: null,
  start_year: null,
  end_month: null,
  end_year: null,
  description: "",
});

/** A yes/no answer is two buttons, because it is two answers. */
function YesNo({ value, onChange, clearable = true }: { value: string; onChange: (v: string) => void; clearable?: boolean }) {
  return (
    <div className="ans-yn">
      {["Yes", "No"].map((opt) => (
        <button key={opt} type="button" data-val={opt} aria-pressed={value === opt} onClick={() => onChange(opt)}>
          {opt}
        </button>
      ))}
      {clearable && value ? (
        <button type="button" className="ans-clear" onClick={() => onChange("")}>
          Clear
        </button>
      ) : null}
    </div>
  );
}

function AnswerRow({ row, set, remove }: { row: Row; set: (r: Partial<Row>) => void; remove: () => void }) {
  let control;
  if (row.kind === "boolean") control = <YesNo value={row.value} onChange={(v) => set({ value: v })} />;
  else if (row.kind === "choice") {
    // A value the catalogue no longer offers is kept and shown: it is
    // still the user's answer.
    const opts = row.value && !row.options.includes(row.value) ? [...row.options, row.value] : row.options;
    control = (
      <select className="ans-value" aria-label={row.label} value={row.value} onChange={(e) => set({ value: e.target.value })}>
        <option value="">Not answered</option>
        {opts.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    );
  } else
    control = (
      <textarea
        className="ans-value"
        placeholder="Your answer"
        aria-label="Answer"
        value={row.value}
        onChange={(e) => set({ value: e.target.value })}
      />
    );
  return (
    <div className="ans-edit">
      {/* The question is ace's, not the user's: renaming it would break
          the match that finds it on a form. */}
      {row.known ? (
        <div className="ans-name">{row.label}</div>
      ) : (
        <input
          type="text"
          className="ans-label"
          value={row.label}
          placeholder="Question"
          aria-label="Question"
          onChange={(e) => set({ label: e.target.value })}
        />
      )}
      <div>
        {control}
        {row.hint ? <div className="ans-hint">{row.hint}</div> : null}
      </div>
      <button className="iconbtn" onClick={remove} aria-label="Remove this question">
        <Icon name="x" />
      </button>
    </div>
  );
}

function HistoryBlock({
  kind,
  entry,
  index,
  set,
  remove,
}: {
  kind: "work" | "education";
  entry: HistoryEntry;
  index: number;
  set: (e: Partial<HistoryEntry>) => void;
  remove: () => void;
}) {
  const work = kind === "work";
  const num = (v: string) => (v ? parseInt(v, 10) : null);
  const month = (label: string, value: number | null, field: keyof HistoryEntry) => (
    <div>
      <label>{label}</label>
      <select value={value ?? ""} onChange={(e) => set({ [field]: num(e.target.value) })}>
        <option value="">Month</option>
        {MONTHS.map((m, i) => (
          <option key={m} value={i + 1}>
            {m}
          </option>
        ))}
      </select>
    </div>
  );
  const year = (label: string, value: number | null, field: keyof HistoryEntry) => (
    <div>
      <label>{label}</label>
      <select value={value ?? ""} onChange={(e) => set({ [field]: num(e.target.value) })}>
        <option value="">Year</option>
        {YEARS.map((y) => (
          <option key={y} value={y}>
            {y}
          </option>
        ))}
      </select>
    </div>
  );
  return (
    <div className="hist" data-hist={kind}>
      <div className="hist-foot" style={{ margin: "0 0 10px" }}>
        <span className="hist-n">
          {work ? "Job" : "Study"} {index + 1}
        </span>
        <span className="spacer" style={{ flex: 1 }} />
        <button className="iconbtn" onClick={remove} aria-label="Remove this entry">
          <Icon name="x" />
        </button>
      </div>
      <div className="hist-grid">
        <div>
          <label>{work ? "Employer" : "School"}</label>
          <input value={entry.employer} onChange={(e) => set({ employer: e.target.value })} />
        </div>
        <div>
          <label>{work ? "Job title" : "Degree"}</label>
          <input value={entry.job_title} onChange={(e) => set({ job_title: e.target.value })} />
        </div>
        <div>
          <label>Location</label>
          <input value={entry.location} onChange={(e) => set({ location: e.target.value })} />
        </div>
        <div>
          <label>{work ? "Still working here" : "Still studying here"}</label>
          <YesNo value={entry.is_current ? "Yes" : "No"} onChange={(v) => set({ is_current: v === "Yes" })} clearable={false} />
        </div>
      </div>
      <div className="hist-dates">
        {month("Start month", entry.start_month, "start_month")}
        {year("Start year", entry.start_year, "start_year")}
        {month("End month", entry.end_month, "end_month")}
        {year("End year", entry.end_year, "end_year")}
      </div>
      <div className="hist-wide">
        <label style={{ display: "block", fontSize: "var(--text-label)", fontWeight: "var(--weight-medium)", color: "var(--text-muted)", marginBottom: 4 }}>Description</label>
        <textarea
          placeholder="What you did there. Pasted once, filled every time."
          value={entry.description}
          onChange={(e) => set({ description: e.target.value })}
        />
      </div>
    </div>
  );
}

export function AnswersEditor({
  answers,
  work: initialWork,
  education: initialEducation,
}: {
  answers: Answer[];
  work: HistoryEntry[];
  education: HistoryEntry[];
}) {
  const router = useRouter();
  const { toast } = useApp();
  const [rows, setRows] = useState<Row[]>(() => answerSections(answers.map(toRow)).flatMap(([, r]) => r));
  const [work, setWork] = useState(initialWork);
  const [education, setEducation] = useState(initialEducation);
  const [saving, setSaving] = useState(false);
  const [n, setN] = useState(0);

  const sections = answerSections(rows);
  const setRow = (key: string, patch: Partial<Row>) => setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  const removeRow = (key: string) => setRows((rs) => rs.filter((r) => r.key !== key));

  const save = async () => {
    setSaving(true);
    try {
      // One button for all three: a partial save would leave you
      // guessing which half landed.
      const ordered = sections.flatMap(([, r]) => r);
      await Promise.all([
        sendJson("PUT", "/api/answers", {
          items: ordered.filter((r) => r.label.trim()).map((r) => ({ label: r.label, value: r.value })),
        }),
        sendJson("PUT", "/api/history/work", { items: work }),
        sendJson("PUT", "/api/history/education", { items: education }),
      ]);
      const [a, w, e] = await Promise.all([
        getJson<{ items: Answer[] }>("/api/answers"),
        getJson<{ items: HistoryEntry[] }>("/api/history/work"),
        getJson<{ items: HistoryEntry[] }>("/api/history/education"),
      ]);
      setRows(answerSections(a.items.map(toRow)).flatMap(([, r]) => r));
      setWork(w.items);
      setEducation(e.items);
      toast("Saved");
      router.refresh();
    } catch {
      toast("Could not save");
    } finally {
      setSaving(false);
    }
  };

  const history = (kind: "work" | "education") => {
    const list = kind === "work" ? work : education;
    const setList = kind === "work" ? setWork : setEducation;
    return (
      <>
        <div className="ans-sec">{kind === "work" ? "Work history" : "Education"}</div>
        <div>
          {list.map((entry, i) => (
            <HistoryBlock
              key={`${kind}${entry.id ?? "new"}${i}`}
              kind={kind}
              entry={entry}
              index={i}
              set={(p) => setList((l) => l.map((x, j) => (j === i ? { ...x, ...p } : x)))}
              remove={() => setList((l) => l.filter((_, j) => j !== i))}
            />
          ))}
        </div>
        <button className="btn btn-secondary btn-sm" style={{ marginBottom: 6 }} onClick={() => setList((l) => [...l, blankHistory()])}>
          Add {kind === "work" ? "a job" : "a degree"}
        </button>
      </>
    );
  };

  return (
    <>
      <div id="ansform">
        {sections.map(([title, rs]) => (
          <div key={title}>
            <div className="ans-sec">{title}</div>
            {rs.map((r) => (
              <AnswerRow key={r.key} row={r} set={(p) => setRow(r.key, p)} remove={() => removeRow(r.key)} />
            ))}
          </div>
        ))}
      </div>
      {history("work")}
      {history("education")}
      <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
        <button
          className="btn btn-secondary"
          onClick={() => {
            setN(n + 1);
            setRows((rs) => [...rs, { key: `new${n}`, label: "", value: "", kind: "text", options: [], hint: "", known: false }]);
          }}
        >
          Add a question
        </button>
        <button className="btn btn-primary" onClick={save} disabled={saving}>
          {saving ? "Saving" : "Save everything"}
        </button>
      </div>
    </>
  );
}
