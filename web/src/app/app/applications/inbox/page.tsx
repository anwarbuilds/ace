import { InboxIntelligence } from "@/components/inbox/InboxIntelligence";
import { ScrollArea } from "@/components/shell/ScrollArea";

export const metadata = { title: "Inbox Intelligence · ace" };

export default function InboxPage() {
  return <ScrollArea><InboxIntelligence /></ScrollArea>;
}
