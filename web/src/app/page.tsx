import { LegacyHashRedirect } from "@/components/auth/LegacyHashRedirect";
import { PublicInfoCard } from "@/components/auth/PublicInfoCard";

export default function Home() {
  return (
    <>
      <LegacyHashRedirect />
      <PublicInfoCard title="Career Intelligence Always On">
        <p>ace is a private, owner-only workspace for reviewing opportunities and preparing applications.</p>
      </PublicInfoCard>
    </>
  );
}
