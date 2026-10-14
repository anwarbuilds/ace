import { redirect } from "next/navigation";

// The public landing page is Phase 3. Until then the root opens the app.
export default function Home() {
  redirect("/app/opportunities");
}
