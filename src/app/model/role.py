from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, UniqueConstraint
from app.core.db import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # chỉ phục vụ type checking, không gây import vòng khi chạy
    from app.model.user import User


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("name"),)

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, index=True
    )
    name: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(String(255))

    # Dùng tên chuỗi "User" + secondary="user_roles" (chuỗi) để tránh import vòng
    users: Mapped[list["User"]] = relationship(
        "User",
        secondary="user_roles",  # SQLAlchemy sẽ tìm Table "user_roles" trong Base.metadata
        back_populates="roles",
        lazy="selectin",
    )
