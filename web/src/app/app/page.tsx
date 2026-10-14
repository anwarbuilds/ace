import { redirect } from "next/navigation";

// The signed-in overview arrives in a later slice; until then /app opens
// the Opportunity Hub.
export default function AppHome() {
  redirect("/app/opportunities");
}
