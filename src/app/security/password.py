import hashlib
import hmac
import secrets
from typing import Optional


class PasswordHandler:
    """Simple password handler using PBKDF2-HMAC-SHA256 (hashlib).

    Stored format: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>

    The handler will also try to verify bcrypt hashes via passlib if
    passlib and bcrypt are available (helps migrating existing bcrypt
    entries). New hashes are created with PBKDF2.
    """

    DEFAULT_ITERATIONS = 300_000
    SALT_BYTES = 16

    def _pbkdf2_hash(self, password: str, salt: bytes, iterations: int) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        if not plain_password or not hashed_password:
            return False

        try:
            if hashed_password.startswith("pbkdf2_sha256$"):
                # parse
                parts = hashed_password.split("$")
                if len(parts) != 4:
                    return False
                _, iter_s, salt_hex, hash_hex = parts
                iterations = int(iter_s)
                salt = bytes.fromhex(salt_hex)
                expected = bytes.fromhex(hash_hex)
                derived = self._pbkdf2_hash(plain_password, salt, iterations)
                return hmac.compare_digest(derived, expected)

            # fallback: try passlib bcrypt if available (best-effort)
            try:
                from passlib.context import CryptContext

                pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
                return pwd_context.verify(plain_password, hashed_password)
            except Exception:
                return False
        except Exception:
            return False

    def get_password_hash(self, password: str, iterations: Optional[int] = None) -> str:
        if password is None:
            raise ValueError("password must be a string")
        it = iterations or self.DEFAULT_ITERATIONS
        salt = secrets.token_bytes(self.SALT_BYTES)
        dk = self._pbkdf2_hash(password, salt, it)
        return f"pbkdf2_sha256${it}${salt.hex()}${dk.hex()}"

    # Backwards-compatible alias used elsewhere in the codebase
    def hash_password(self, password: str) -> str:
        return self.get_password_hash(password)
