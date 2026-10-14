import { redirect } from "next/navigation";

// ace is private: the root opens the signed-in overview.
export default function Home() {
  redirect("/app");
}
