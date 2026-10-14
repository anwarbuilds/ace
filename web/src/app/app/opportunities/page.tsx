import { JobListPage } from "@/components/jobs/JobListPage";

export const metadata = { title: "Queue · ace" };

export default async function QueuePage(props: PageProps<"/app/opportunities">) {
  return <JobListPage page="queue" searchParams={await props.searchParams} />;
}
