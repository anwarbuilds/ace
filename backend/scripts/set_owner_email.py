"""Change the one active owner's login email without changing product data.

Run this only after restoring the production database into its target. The
operator already has server access, like the owner creation and reset command.
No password or secret is accepted on the command line.

    python -m backend.scripts.set_owner_email new-owner@example.com
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from sqlalchemy import select

from backend.app.auth import service
from backend.app.db.models import UserRecord


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("email")
    args = parser.parse_args(argv)

    from backend.app.db.session import SessionLocal

    with SessionLocal() as session:
        owners = list(
            session.scalars(
                select(UserRecord).where(
                    UserRecord.role == service.OWNER,
                    UserRecord.is_active.is_(True),
                )
            )
        )
        if len(owners) != 1:
            raise SystemExit(
                "Expected exactly one active owner. Nothing was changed."
            )

        try:
            service.set_owner_email(
                session,
                owners[0],
                args.email,
                now=datetime.now(timezone.utc),
            )
        except service.AuthRefused as refused:
            raise SystemExit(f"{refused.message} Nothing was changed.") from None

        session.commit()

    print(
        "Owner email changed. Existing applications and profile data were "
        "preserved. Every browser was signed out."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
