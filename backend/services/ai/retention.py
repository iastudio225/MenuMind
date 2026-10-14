"""Manual purge of old AI conversations (D1.25, retention 90 days).

Scope and honesty notes:
- Conversations are session artifacts only: a chat transcript, a cart draft
  and a customer contact captured during the chat. Orders keep their own
  snapshots in the `orders` collection — purging old conversations never
  touches orders, carts, customers, menus or any business record.
- Conversations with a recent `updated_at` are always kept (active chats and
  recent order follow-ups are not deleted).
- This module is MANUAL by design (the project has no scheduler): it must be
  run explicitly, supports dry_run, and logs only counts and timestamps.
  No data is modified during D1.25 itself.

Usage (manual, from backend/):
    py -3.14 -m services.ai.retention --dry-run
    py -3.14 -m services.ai.retention            # asks confirmation (tapez 'oui')
    py -3.14 -m services.ai.retention --yes      # scripted use, no prompt
"""
import argparse
import asyncio
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = 90


def _cutoff_iso(older_than_days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()


async def purge_old_conversations(db=None, older_than_days: int = DEFAULT_RETENTION_DAYS,
                                  dry_run: bool = False) -> dict:
    """Delete conversations whose updated_at is older than the cutoff.

    Returns {"matched": n, "deleted": n, "cutoff": iso, "dry_run": bool}.
    """
    if older_than_days <= 0:
        raise ValueError("older_than_days must be positive")
    if db is None:
        from database import db  # lazy: keeps this module importable in unit tests
    cutoff = _cutoff_iso(older_than_days)
    q = {"updated_at": {"$lt": cutoff}}
    matched = await db.ai_conversations.count_documents(q)
    deleted = 0
    if matched and not dry_run:
        res = await db.ai_conversations.delete_many(q)
        deleted = res.deleted_count
    logger.info("AI_CONVERSATIONS_PURGE matched=%d deleted=%d cutoff=%s dry_run=%s",
                matched, deleted, cutoff, dry_run)
    return {"matched": matched, "deleted": deleted, "cutoff": cutoff, "dry_run": dry_run}


def main():
    # Load backend/.env so the documented CLI works from a clean shell
    # (database.py reads MONGO_URL from the environment at import time).
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser(description="Purge old AI conversations (manual)")
    ap.add_argument("--days", type=int, default=DEFAULT_RETENTION_DAYS)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true",
                    help="Skip the interactive confirmation (for scripted use)")
    args = ap.parse_args()
    if not args.dry_run and not args.yes:
        answer = input(f"Supprimer definitivement les conversations IA inactives "
                       f"depuis plus de {args.days} jours ? (tapez 'oui' pour confirmer) ")
        if answer.strip().lower() != "oui":
            print("Annule — aucune suppression.")
            return
    res = asyncio.run(purge_old_conversations(older_than_days=args.days, dry_run=args.dry_run))
    print(res)


if __name__ == "__main__":
    main()
