import { LegacyHashRedirect } from "@/components/auth/LegacyHashRedirect";
import { PublicHome } from "@/components/public/PublicHome";

export default function Home() {
  return (
    <>
      <LegacyHashRedirect />
      <PublicHome />
    </>
  );
}
