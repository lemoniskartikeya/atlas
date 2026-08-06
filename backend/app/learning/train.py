"""CLI: train the completion model from the current database.

Usage:  python -m app.learning.train
"""
from __future__ import annotations

import json

from app.core.database import SessionLocal
from app.services.ml_service import MLService


def main() -> None:
    session = SessionLocal()
    try:
        result = MLService(session).train()
        print(json.dumps(result, indent=2, default=str))
    finally:
        session.close()


if __name__ == "__main__":
    main()
