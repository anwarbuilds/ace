"""Create the owner account, or set a new password for it.

There is no sign-up page: the owner is created here, on the server, by
someone who can already run commands on it. The password is typed at a
hidden prompt and never appears in the shell history, the process list
or a log.

    python -m backend.scripts.create_owner you@example.com
    python -m backend.scripts.create_owner you@example.com --reset

In Docker:

    docker exec -it ace-web-1 python -m backend.scripts.create_owner you@example.com

--reset also signs every browser out. Paired extensions keep working;
revoke them in Settings if a device was lost.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from datetime import (
    datetime,
    timezone,
)

from backend.app.auth import service
from backend.app.auth.crypto import (
    MIN_PASSWORD_LENGTH,
    WeakPassword,
)


def _ask_password() -> str:
    first = getpass.getpass(f"New password (at least {MIN_PASSWORD_LENGTH} characters): ")
    second = getpass.getpass("Type it again: ")

    if first != second:
        raise SystemExit("The two passwords differ. Nothing was changed.")

    return first


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("email")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="set a new password for the existing owner",
    )
    args = parser.parse_args(argv)

    from backend.app.db.session import SessionLocal

    now = datetime.now(timezone.utc)
    password = _ask_password()

    with SessionLocal() as session:
        try:
            if args.reset:
                user = service.find_user(session, args.email)
                if user is None or user.role != service.OWNER:
                    raise SystemExit("No owner with that email. Nothing was changed.")
                service.set_password(session, user, password, now=now)
                message = "Password changed. Every browser was signed out."
            else:
                service.create_owner(
                    session, email=args.email, password=password, now=now
                )
                message = "Owner created. Sign in at the ace web app."
        except WeakPassword as weak:
            raise SystemExit(f"{weak} Nothing was changed.") from None
        except service.AuthRefused as refused:
            raise SystemExit(f"{refused.message} Nothing was changed.") from None

        session.commit()

    print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
