from __future__ import annotations
from enum import Enum
from typing import Final


class ROLE(Enum):
    ADMIN = "admin"
    USER = "user"
    USER_PRO = "user_pro"


class TBConstants:
    DEFAULT_USER_PASSWORD: Final[str] = "Change"
