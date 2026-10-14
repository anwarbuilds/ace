import { ScrollArea } from "@/components/shell/ScrollArea";
import { CompanyDirectory, type CompanyRow } from "@/components/browse/CompanyDirectory";
import { apiGetOr } from "@/lib/api";

export const metadata = { title: "Companies · ace" };

export default async function CompaniesPage() {
  const { items } = await apiGetOr<{ items: CompanyRow[] }>("/api/companies", { items: [] });
  const hiring = items.filter((c) => c.open_roles > 0).length;
  return (
    <>
      <div className="head">
        <div className="head-row">
          <h1 className="h1">Companies</h1>
          <span className="h1-count">{hiring} hiring for you</span>
        </div>
      </div>
      <ScrollArea>
        <div className="page">
          <CompanyDirectory companies={items} />
        </div>
      </ScrollArea>
    </>
  );
}
