import argparse
import asyncio
import sys
from pathlib import Path
from app.core.db import SessionLocal
from app.repository.user_repository import UserRepository
from app.security.password import PasswordHandler

# Ensure `src` is on sys.path so `import app...` works when running
# the script from the project root (e.g., `python src/scripts/...`).
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


handle = PasswordHandler()


async def main(username: str, password: str):
    try:
        async with SessionLocal() as db:
            repo = UserRepository(db)
            user = await repo.get_by_username(username)
            if not user:
                print(f"User not found: {username}")
                return
            print(
                f"Found user: id={user.id}, username={user.username}, is_active={user.is_active}"
            )
            ph = getattr(user, "password_hash", None)
            print(f"Stored password_hash (len={len(ph) if ph else 0}):\n{ph}\n")

            ok = handle.verify_password(password, ph)
            print(f"Password verify returned: {ok}")

            # Also show whether the hash looks like our PBKDF2 format
            looks_pbkdf2 = isinstance(ph, str) and ph.startswith("pbkdf2_sha256$")
            print(f"Looks like pbkdf2 format: {looks_pbkdf2}")
    except Exception as e:
        print("Error accessing the database:", e)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    asyncio.run(main(args.username, args.password))
