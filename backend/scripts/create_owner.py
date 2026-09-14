"""Create the account that owns this deployment, and claim its data.

ACE ran for weeks before it had accounts, so there are already 393 rows
of hand-entered data -- marks, answers, application history, a resume --
with no owner. The first account created here claims all of them.

Run once, on the deployment, before opening the port:

    python -m backend.scripts.create_owner --email you@example.com

The password is read from ACE_OWNER_PASSWORD, or prompted for. It is
never taken from a command-line argument, because that lands in shell
history and in the process list where any other user on the box can
read it.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from sqlalchemy import (
    select,
    text,
    update,
)

from backend.app.auth.credentials import (
    hash_password,
)
from backend.app.db.models import (
    UserRecord,
)
from backend.app.db.session import (
    SessionLocal,
)


# Long enough that guessing is hopeless even if the hash leaks. Length
# is the only password rule here: composition rules push people toward
# "Passw0rd!" and buy nothing.
MIN_PASSWORD_LENGTH = 12


OWNED_TABLES = (
    "resumes",
    "job_marks",
    "external_applications",
    "application_answers",
    "history_entries",
)


def _read_password() -> str:
    """Return the password, from the environment or a prompt."""

    from_env = os.environ.get(
        "ACE_OWNER_PASSWORD",
    )

    if from_env:
        return from_env

    first = getpass.getpass(
        "Password: ",
    )

    second = getpass.getpass(
        "Again: ",
    )

    if first != second:
        raise SystemExit(
            "Passwords did not match.",
        )

    return first


def main() -> int:
    """Create the owner account and claim unowned rows."""

    parser = argparse.ArgumentParser(
        description=(
            "Create the account that "
            "owns this deployment."
        ),
    )

    parser.add_argument(
        "--email",
        required=True,
    )

    parser.add_argument(
        "--set-password",
        action="store_true",
        help=(
            "Change the password of an "
            "existing account instead of "
            "creating one. Every session "
            "it has open is ended."
        ),
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Create an additional "
            "account. ACE is single-"
            "owner; this exists for "
            "replacing a lost one."
        ),
    )

    args = parser.parse_args()

    password = _read_password()

    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(
            "Password must be at least "
            f"{MIN_PASSWORD_LENGTH} "
            "characters.",
        )

    with SessionLocal() as session:
        existing = session.scalars(
            select(
                UserRecord,
            )
        ).all()

        if args.set_password:
            wanted = args.email.strip().lower()

            match = [
                row
                for row in existing
                if row.email == wanted
            ]

            if not match:
                print(
                    f"No account for {wanted}.",
                )

                return 1

            match[0].password_hash = hash_password(
                password,
            )

            # A password change must end every session, or a stolen
            # cookie outlives the password it was obtained with.
            ended = session.execute(
                text(
                    "DELETE FROM auth_sessions "
                    "WHERE user_id = :owner"
                ),
                {
                    "owner": match[0].id,
                },
            ).rowcount or 0

            session.commit()

            print(
                f"Password changed for {wanted}. "
                f"{ended} session(s) ended.",
            )

            return 0

        if existing and not args.force:
            print(
                "An account already exists "
                f"({existing[0].email}). "
                "Nothing was changed.",
            )

            return 1

        user = UserRecord(
            email=args.email.strip().lower(),
            password_hash=hash_password(
                password,
            ),
        )

        session.add(
            user,
        )

        session.flush()

        claimed = 0

        # Only the first account claims history. A second one created
        # with --force is a replacement, and silently handing it
        # somebody else's rows would be the wrong default.
        if not existing:
            for table in OWNED_TABLES:
                result = session.execute(
                    text(
                        f"UPDATE {table} "
                        "SET owner_id = :owner "
                        "WHERE owner_id IS NULL"
                    ),
                    {
                        "owner": user.id,
                    },
                )

                claimed += result.rowcount or 0

        session.commit()

        print(
            f"Created {user.email} "
            f"(id {user.id}).",
        )

        if claimed:
            print(
                f"Claimed {claimed} existing "
                "rows of hand-entered data.",
            )

    return 0


if __name__ == "__main__":
    sys.exit(
        main(),
    )
