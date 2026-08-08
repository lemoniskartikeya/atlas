"""CLI: train the completion model from the current database.

Usage:  python -m app.learning.train            # every account
        python -m app.learning.train <username> # just one

Models are per-account (see ``app.learning.registry``), so training is a loop
over accounts rather than a single global fit.
"""
from __future__ import annotations

import json
import sys

from app.core.database import SessionLocal
from app.core.scoping import acting_as
from app.services.auth_service import AuthService
from app.services.ml_service import MLService


def main() -> None:
    session = SessionLocal()
    try:
        auth = AuthService(session)
        wanted = sys.argv[1].strip().lower() if len(sys.argv) > 1 else None
        if wanted:
            user = auth.by_username(wanted)
            if user is None:
                print(json.dumps({"error": f"No account named {wanted!r}."}))
                raise SystemExit(1)
            targets = [(user.id, user.username)]
        else:
            targets = [(u.id, u.username) for u in auth.all_users()]

        if not targets:
            print(json.dumps({"error": "No accounts exist yet — register one first."}))
            raise SystemExit(1)

        results = {}
        for user_id, label in targets:
            with acting_as(session, user_id):
                results[label] = MLService(session).train()
        print(json.dumps(results, indent=2, default=str))
    finally:
        session.close()


if __name__ == "__main__":
    main()
