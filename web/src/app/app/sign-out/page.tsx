import { redirect } from "next/navigation";

export const metadata = { title: "Sign out · ace" };

export default function SignOutPage() {
  redirect("/logout");
}
