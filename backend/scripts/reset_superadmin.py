"""Reset (or create) the MenuMind super-admin password on the configured database.

Usage (inside the backend container, e.g. Coolify Terminal):
    python -m scripts.reset_superadmin --email cooldigital.africa@gmail.com
    python -m scripts.reset_superadmin --email ... --password 'NouveauMotDePasse!2026'
    python -m scripts.reset_superadmin --email ... --create

If --email is omitted, ADMIN_EMAIL is used. When --password is omitted, the
password is prompted securely (never echoed, never logged). An existing session
is invalidated by incrementing token_version.
"""
import argparse
import asyncio
import getpass
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env before importing auth/database (same policy as the app:
# existing environment variables win over the file).
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

from auth import hash_password  # noqa: E402
from database import db  # noqa: E402
from models import SUPER_ADMIN, now_iso  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(
        description="Réinitialise le mot de passe du super-admin MenuMind.")
    parser.add_argument("--email", default=os.environ.get("ADMIN_EMAIL", "").strip(),
                        help="Email du super-admin (défaut : ADMIN_EMAIL).")
    parser.add_argument("--password", default="",
                        help="Nouveau mot de passe (sinon saisie interactive).")
    parser.add_argument("--create", action="store_true",
                        help="Créer le super-admin s'il n'existe pas.")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    email = (args.email or "").strip().lower()
    if not email:
        print("Erreur : --email (ou ADMIN_EMAIL) est requis.", file=sys.stderr)
        return 1

    password = args.password or getpass.getpass("Nouveau mot de passe super-admin : ")
    confirm = args.password or getpass.getpass("Confirmer le mot de passe : ")
    if password != confirm:
        print("Erreur : les mots de passe ne correspondent pas.", file=sys.stderr)
        return 1
    if len(password) < 6:
        print("Erreur : le mot de passe doit contenir au moins 6 caractères.", file=sys.stderr)
        return 1

    if not (os.environ.get("SUPABASE_DB_URL") or "").strip():
        print("Erreur : SUPABASE_DB_URL est manquant.", file=sys.stderr)
        return 1
    try:
        await db.connect()
    except Exception as exc:
        print(f"Erreur de connexion à la base : {type(exc).__name__}", file=sys.stderr)
        return 1

    try:
        user = await db.users.find_one({"email": email})
        if user is None:
            if not args.create:
                print(f"Erreur : aucun utilisateur avec l'email {email}.", file=sys.stderr)
                print("Astuce : relancez avec --create pour le créer.", file=sys.stderr)
                return 1
            await db.users.insert_one({
                "email": email, "password_hash": hash_password(password),
                "name": "Super Admin", "role": SUPER_ADMIN, "restaurant_id": None,
                "token_version": 0, "active": True, "created_at": now_iso(),
            })
            print(f"Super-admin créé : {email}")
            return 0

        if user.get("role") != SUPER_ADMIN:
            print(f"Erreur : {email} existe mais n'est pas SUPER_ADMIN "
                  f"(rôle={user.get('role')}).", file=sys.stderr)
            print("Utilisez la réinitialisation standard pour ce compte.", file=sys.stderr)
            return 1

        await db.users.update_one(
            {"email": email},
            {"$set": {"password_hash": hash_password(password),
                      "updated_at": now_iso(), "active": True},
             "$inc": {"token_version": 1}},
        )
        print(f"OK — mot de passe mis à jour pour {email}")
        print("Les sessions existantes sont invalidées (token_version incrémenté).")
        return 0
    finally:
        await db.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
