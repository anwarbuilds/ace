import { PublicInfoCard } from "@/components/auth/PublicInfoCard";

export const metadata = { title: "Terms · ace" };

export default function TermsPage() {
  return (
    <PublicInfoCard title="Terms of Service" back>
      <p>ace is a private workspace provided for its configured owner. Use it only for lawful career research and application preparation.</p>
      <p>The owner remains responsible for reviewing all generated materials before using them.</p>
    </PublicInfoCard>
  );
}
