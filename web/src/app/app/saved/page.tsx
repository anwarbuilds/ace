import { JobListPage } from "@/components/jobs/JobListPage";

export const metadata = { title: "Saved · ace" };

export default async function SavedPage(props: PageProps<"/app/saved">) {
  return <JobListPage page="saved" searchParams={await props.searchParams} />;
}
