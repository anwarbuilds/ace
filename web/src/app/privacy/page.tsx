import { PublicInfoCard } from "@/components/auth/PublicInfoCard";

export const metadata = { title: "Privacy · ace" };

export default function PrivacyPage() {
  return (
    <PublicInfoCard title="Privacy Policy" back>
      <p>ace keeps career data inside the owner-only workspace. Access requires an authenticated owner session.</p>
      <p>Extension access uses a separate paired token that the owner can revoke from Settings.</p>
    </PublicInfoCard>
  );
}
