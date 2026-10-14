import { JobListPage } from "@/components/jobs/JobListPage";

export const metadata = { title: "Archive · ace" };

export default async function ArchivePage(props: PageProps<"/app/archive">) {
  return <JobListPage page="archive" searchParams={await props.searchParams} />;
}
