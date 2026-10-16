import Link from "next/link";

import { EmptyBox } from "@/components/bits";

export default function NotFound() {
  return (
    <div className="page">
      <EmptyBox
        title="That opportunity could not be found"
        actions={
          <Link className="btn btn-secondary" href="/app/opportunities">
            Back to opportunities
          </Link>
        }
      >
        The link may be mistyped, or the posting was removed from ace.
      </EmptyBox>
    </div>
  );
}
