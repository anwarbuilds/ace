import { redirect } from "next/navigation";

import { SignedOutCard } from "@/components/auth/SignedOutCard";
import { ThemeAwareAuthLayout } from "@/components/auth/ThemeAwareAuthLayout";
import { authStatus } from "@/lib/api";

export const metadata = { title: "Signed out · ace" };

export default async function SignedOutPage() {
  const status = await authStatus();
  if (status?.signed_in) redirect("/app/pulls");

  return (
    <ThemeAwareAuthLayout intro="Private workspace">
      <SignedOutCard />
    </ThemeAwareAuthLayout>
  );
}
