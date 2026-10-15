import { redirect } from "next/navigation";

// Pulls is the signed-in home.
export default function AppHome() {
  redirect("/app/pulls");
}
