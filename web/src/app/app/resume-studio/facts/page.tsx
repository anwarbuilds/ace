import { ScrollArea } from "@/components/shell/ScrollArea";
import { FactsBoard } from "@/components/studio/FactsBoard";
import { apiGetOr } from "@/lib/api";
import type { Fact } from "@/lib/studio";

export const metadata = { title: "Knowledge base · ace" };

const FILTERS = ["review", "verified", "deprecated", "all"] as const;

export default async function FactsPage({ searchParams }: PageProps<"/app/resume-studio/facts">) {
  const sp = await searchParams;
  const raw = Array.isArray(sp.status) ? sp.status[0] : sp.status;
  const kind = (Array.isArray(sp.kind) ? sp.kind[0] : sp.kind) ?? "";
  const { items } = await apiGetOr<{ items: Fact[] }>("/api/studio/facts", { items: [] });
  const filter = (FILTERS as readonly string[]).includes(raw ?? "") ? (raw as (typeof FILTERS)[number]) : "all";
  return (
    <ScrollArea>
      <div className="page">
        <div className="wrap">
          <FactsBoard facts={items} filter={filter} kind={kind} />
        </div>
      </div>
    </ScrollArea>
  );
}
