"""
Create an admin account, or make an existing account an admin.

There is deliberately no web page or API that does this: anyone who could
reach it could make themselves an admin. Only someone who can run commands on
the server machine can.

    # a new admin with an email + password (you type the password; it is not shown)
    .venv\\Scripts\\python.exe scripts\\create_admin.py admin@example.com --name "Control Room"

    # make an account that already exists an admin (e.g. one that signed in with Google)
    .venv\\Scripts\\python.exe scripts\\create_admin.py someone@gmail.com --promote

For Google accounts there is also ADMIN_EMAILS in .env — see .env.example.
"""

from __future__ import annotations

import argparse
import getpass
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("email")
    parser.add_argument("--name", default=None, help="display name for a new account")
    parser.add_argument("--promote", action="store_true",
                        help="make an existing account admin without setting a password")
    args = parser.parse_args()

    from app.database.mongodb import startup_db
    from app.services.auth_service import AuthError, create_or_promote_admin

    startup_db()

    password = None
    if not args.promote:
        password = getpass.getpass("Password for the admin account (min 8 characters): ")
        if password != getpass.getpass("Type it again: "):
            print("The two passwords did not match. Nothing was changed.")
            return 1

    try:
        user = create_or_promote_admin(args.email, name=args.name, password=password)
    except AuthError as exc:
        print(f"Not done: {exc}")
        return 1

    print(f"Done: {user['email']} is now {user['role']}. Sign in on the login page's "
          "Admin Access tab.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
