import argparse
import asyncio
import sys
from pathlib import Path
from app.core.db import SessionLocal
from app.repository.user_repository import UserRepository
from app.security.password import PasswordHandler

ROOT = Path(__file__).resolve().parents[1]  # src/
sys.path.insert(0, str(ROOT))

handle = PasswordHandler()


async def main(username: str, password: str, email: str | None = None):
    try:
        async with SessionLocal() as db:
            repo = UserRepository(db)
            user = await repo.get_by_username(username)
            if user:
                # update existing user's password_hash
                user.password_hash = handle.hash_password(password)
                db.add(user)
                await db.flush()
                await db.commit()
                print(f"Updated password for existing user: {username}")
            else:
                # create basic user
                _email = email or f"{username}@example.com"
                await repo.create_basic_user(
                    username=username, email=_email, password=password
                )
                await db.commit()
                print(f"Created new user: {username} (email: {_email})")
    except Exception as e:
        print("Error accessing the database:", e)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Set or create a user's password (bcrypt-hashed)"
    )
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--email", required=False)
    args = parser.parse_args()
    asyncio.run(main(args.username, args.password, args.email))
