import { redirect } from "next/navigation";

// ace is private: the root opens Pulls, and the app sends anyone not
// signed in to the sign-in page first.
export default function Home() {
  redirect("/app/pulls");
}
