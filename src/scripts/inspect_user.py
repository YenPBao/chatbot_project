"""Inspect stored user record and test password verification.

Usage (from project root):
python src/scripts/inspect_user.py --username admin01 --password 123

This prints the stored `password_hash` from DB and runs the PasswordHandler.verify_password
to show whether verification succeeds locally. Helpful to diagnose why login returns 401.
"""
import argparse
import asyncio
import sys
from pathlib import Path

# ensure src on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config.db import SessionLocal
from app.repository.user_repository import UserRepository
from app.security.password import PasswordHandler

handle = PasswordHandler()

async def main(username: str, password: str):
    async with SessionLocal() as db:
        repo = UserRepository(db)
        user = await repo.get_by_username(username)
        if not user:
            print(f"User not found: {username}")
            return
        print(f"Found user: id={user.id}, username={user.username}, is_active={user.is_active}")
        ph = getattr(user, 'password_hash', None)
        print(f"Stored password_hash (len={len(ph) if ph else 0}):\n{ph}\n")

        ok = handle.verify_password(password, ph)
        print(f"Password verify returned: {ok}")

        # Also show whether the hash looks like our PBKDF2 format
        looks_pbkdf2 = isinstance(ph, str) and ph.startswith('pbkdf2_sha256$')
        print(f"Looks like pbkdf2 format: {looks_pbkdf2}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--username', required=True)
    parser.add_argument('--password', required=True)
    args = parser.parse_args()
    asyncio.run(main(args.username, args.password))
"""
Inspect a user row in the database for debugging authentication.
Prints: id, username, is_active, password_hash (for debugging only).

Usage:
  python src/scripts/inspect_user.py --username admin

Be careful: this prints the password hash to help debug login issues.
"""
import argparse
import asyncio
from pathlib import Path
import sys

# Ensure src is on path when running from project root
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config.db import SessionLocal
from app.repository.user_repository import UserRepository


async def main(username: str):
    try:
        async with SessionLocal() as db:
            repo = UserRepository(db)
            user = await repo.get_by_username(username)
            if not user:
                print(f"User not found: {username}")
                return
            print("User:")
            print(f"  id: {user.id}")
            print(f"  username: {user.username}")
            print(f"  is_active: {user.is_active}")
            # print the hash so we can verify format
            print(f"  password_hash: {getattr(user, 'password_hash', None)}")
    except Exception as e:
        print("Error accessing the database:", e)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    args = parser.parse_args()
    asyncio.run(main(args.username))
