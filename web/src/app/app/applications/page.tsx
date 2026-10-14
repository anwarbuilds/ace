import { JobListPage } from "@/components/jobs/JobListPage";

export const metadata = { title: "Applied · ace" };

export default async function AppliedPage(props: PageProps<"/app/applications">) {
  return <JobListPage page="applied" searchParams={await props.searchParams} />;
}
