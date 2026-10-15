import { AnswersEditor } from "@/components/pages/AnswersEditor";
import { ScrollArea } from "@/components/shell/ScrollArea";
import { apiGet } from "@/lib/api";
import type { Answer, HistoryEntry } from "@/lib/types";

export const metadata = { title: "Answers · ace" };

// Read with apiGet, not apiGetOr: an editor that loaded an empty bank
// because the API hiccuped would save that emptiness over the real one.
export default async function AnswersPage() {
  const [answers, work, education] = await Promise.all([
    apiGet<{ items: Answer[] }>("/api/answers"),
    apiGet<{ items: HistoryEntry[] }>("/api/history/work"),
    apiGet<{ items: HistoryEntry[] }>("/api/history/education"),
  ]);
  return (
    <>
      <div className="head">
        <div className="eyebrow">Autofill Extension</div>
        <div className="head-row">
          <h1 className="h1">Answers</h1>
          <span className="h1-count">{answers.items.filter((a) => a.value).length} filled</span>
          <span className="spacer" />
        </div>
      </div>
      <ScrollArea>
        <div className="page">
          <div className="wrap">
            <p className="why" style={{ maxWidth: "70ch", marginBottom: 22 }}>
              The things every application form asks for. Answer them once and the extension fills them wherever they
              come up, however that form happens to word them. ace knows that a job board and a job portal are the
              same thing, so you pick the answer, not the wording. Leave blank anything you would rather answer by
              hand, and add your own questions at the end.
            </p>
            <AnswersEditor answers={answers.items} work={work.items} education={education.items} />
          </div>
        </div>
      </ScrollArea>
    </>
  );
}
