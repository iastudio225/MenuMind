"""Create the first MenuMind SUPER_ADMIN in the development database only.

This is an intentionally narrow, one-shot bootstrap. It does not call the
application seed and refuses to write unless every target and account guard
passes. Run from the backend directory with MENUMIND_DEV_MONGO_HOST supplied
in the shell as the separately approved Atlas development hostname.
"""
import asyncio
import getpass
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from pydantic import EmailStr, TypeAdapter, ValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEVELOPMENT_DB_NAME = "resto_AI_test"


class SafeAbort(Exception):
    """Expected guard failure; messages must never contain connection data."""


def _require_target_config() -> None:
    env_file = PROJECT_ROOT / ".env.development.local"
    if not env_file.is_file():
        raise SafeAbort(".env.development.local is missing; no account was created.")

    # This expected hostname must be injected independently by the operator;
    # do not derive the allowlist from MONGO_URL or from the dotenv file.
    expected_host = os.environ.get("MENUMIND_DEV_MONGO_HOST", "").strip().lower().rstrip(".")
    if not expected_host or not expected_host.endswith(".mongodb.net"):
        raise SafeAbort("MENUMIND_DEV_MONGO_HOST must be set to the approved development Atlas host.")

    load_dotenv(env_file, override=False)

    mode = os.environ.get("MENUMIND_ENV", "").strip().lower()
    if mode != "development":
        raise SafeAbort("MENUMIND_ENV must be exactly development.")

    db_name = os.environ.get("DB_NAME", "")
    if db_name != DEVELOPMENT_DB_NAME:
        raise SafeAbort("DB_NAME does not match the required development database.")

    mongo_uri = os.environ.get("MONGO_URL", "")
    scheme = ""
    try:
        parsed_uri = urlsplit(mongo_uri)
        scheme = parsed_uri.scheme
        actual_host = (parsed_uri.hostname or "").lower().rstrip(".")
    except Exception:
        actual_host = ""
    if scheme not in {"mongodb", "mongodb+srv"} or not actual_host.endswith(".mongodb.net"):
        raise SafeAbort("MONGO_URL is not a valid Atlas URI for the development cluster.")
    if actual_host != expected_host:
        raise SafeAbort("MONGO_URL does not match the independently approved development Atlas host.")


def _prompt_identity():
    name = input("Nom du SUPER_ADMIN : ").strip()
    if not name:
        raise SafeAbort("Name is required; no account was created.")

    raw_email = input("Adresse email du SUPER_ADMIN : ").strip().lower()
    try:
        email = str(TypeAdapter(EmailStr).validate_python(raw_email)).lower()
    except ValidationError:
        raise SafeAbort("Email address is invalid; no account was created.") from None
    return name, email


def _prompt_password() -> str:
    password = getpass.getpass("Mot de passe du SUPER_ADMIN : ")
    confirmation = getpass.getpass("Confirmez le mot de passe : ")
    if password != confirmation:
        raise SafeAbort("Password confirmation did not match; no account was created.")
    # Match the existing RegisterBody minimum without introducing a new role
    # or user-document field.
    if len(password) < 6:
        raise SafeAbort("Password does not meet the existing minimum length; no account was created.")
    return password


async def _has_unique_email_index(users) -> bool:
    try:
        indexes = await asyncio.wait_for(
            users.list_indexes().to_list(length=None),
            timeout=10,
        )
    except Exception as exc:
        raise SafeAbort(
            f"Could not read MongoDB indexes ({type(exc).__name__}); no account was created."
        ) from None
    return any(
        dict(index.get("key", {})) == {"email": 1} and index.get("unique") is True
        for index in indexes
    )


async def _create_superadmin() -> None:
    _require_target_config()

    # Imported only after the development dotenv file and target checks. These
    # imports create the existing Motor client but do not run server startup.
    from auth import hash_password
    from database import db, get_client
    from models import SUPER_ADMIN, now_iso
    from pymongo.errors import DuplicateKeyError

    if db.name != DEVELOPMENT_DB_NAME:
        raise SafeAbort("Connected database name failed the development target check.")

    try:
        await asyncio.wait_for(get_client().admin.command("ping"), timeout=12)
    except Exception as exc:
        raise SafeAbort(f"MongoDB connectivity check failed ({type(exc).__name__}); no account was created.") from None

    users = db.users
    if not await _has_unique_email_index(users):
        raise SafeAbort("The required unique users.email index is absent; no account was created.")
    if await users.count_documents({"role": SUPER_ADMIN}, limit=1):
        raise SafeAbort("A SUPER_ADMIN already exists; no account was created.")

    name, email = _prompt_identity()
    if await users.find_one({"email": email}, {"_id": 1}):
        raise SafeAbort("That email already exists in users; no account was created.")

    password = _prompt_password()
    try:
        password_hash = hash_password(password)
    except Exception as exc:
        del password
        raise SafeAbort(f"Password hashing failed ({type(exc).__name__}); no account was created.") from None
    del password

    confirmation = input('Type "CREATE SUPER_ADMIN" to confirm the one-account insertion: ').strip()
    if confirmation != "CREATE SUPER_ADMIN":
        del password_hash
        raise SafeAbort("Explicit confirmation was not provided; no account was created.")

    # Repeat all account/index checks immediately before the single insert.
    if not await _has_unique_email_index(users):
        del password_hash
        raise SafeAbort("The required unique users.email index is absent; no account was created.")
    if await users.count_documents({"role": SUPER_ADMIN}, limit=1):
        del password_hash
        raise SafeAbort("A SUPER_ADMIN appeared during bootstrap; no account was created.")
    if await users.find_one({"email": email}, {"_id": 1}):
        del password_hash
        raise SafeAbort("That email appeared during bootstrap; no account was created.")

    document = {
        "email": email,
        "password_hash": password_hash,
        "name": name,
        "role": SUPER_ADMIN,
        "restaurant_id": None,
        "token_version": 0,
        "active": True,
        "created_at": now_iso(),
    }
    try:
        await users.insert_one(document)
    except DuplicateKeyError:
        raise SafeAbort("MongoDB rejected a duplicate user key; no existing account was changed.") from None
    except Exception as exc:
        raise SafeAbort(
            f"MongoDB insertion failed or has an uncertain acknowledgement ({type(exc).__name__}); "
            "check users read-only before any retry."
        ) from None
    finally:
        document.clear()
        del password_hash

    print("SUPER_ADMIN created in the verified development database.")


async def _main() -> int:
    client_getter = None
    try:
        _require_target_config()
        from database import get_client
        client_getter = get_client
        await _create_superadmin()
        return 0
    except SafeAbort as exc:
        print(f"Aborted: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(
            f"Aborted: unexpected error ({type(exc).__name__}); no automatic retry was attempted.",
            file=sys.stderr,
        )
        return 1
    finally:
        if client_getter is not None:
            try:
                client_getter().close()
            except Exception:
                pass


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(_main()))
    except KeyboardInterrupt:
        print("Aborted by operator; no further action was attempted.", file=sys.stderr)
        raise SystemExit(130)
