from __future__ import annotations

from typing import Optional, List
from datetime import datetime

from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.model.conversation import Conversation
from app.model.conversation_message import ConversationMessage


class ConversationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_conversation(
        self,
        *,
        user_id: int,
        title: str | None = None,
        metadata: dict | None = None,
    ) -> Conversation:
        conv = Conversation(
            user_id=user_id,
            title=title,
            metadata=metadata or {},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(conv)
        await self.db.flush()  # để có conv.id
        return conv

    async def get_conversation_by_id(
        self, conversation_id: int
    ) -> Optional[Conversation]:
        res = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        return res.scalar_one_or_none()

    async def get_conversation_with_messages(
        self,
        conversation_id: int,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Optional[Conversation]:
        conv = await self.get_conversation_by_id(conversation_id)
        if conv is None:
            return None

        # load messages theo limit/offset, newest last (tăng dần thời gian)
        res = await self.db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.id.asc())
            .offset(offset)
            .limit(limit)
        )
        conv.messages = list(res.scalars().all())  # type: ignore[attr-defined]
        return conv

    async def list_conversations_by_user(
        self,
        user_id: int,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Conversation]:
        res = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(desc(Conversation.updated_at), desc(Conversation.id))
            .offset(offset)
            .limit(limit)
        )
        return list(res.scalars().all())

    async def update_title(self, conversation_id: int, title: str) -> bool:
        conv = await self.get_conversation_by_id(conversation_id)
        if conv is None:
            return False
        conv.title = title
        conv.updated_at = datetime.utcnow()
        await self.db.flush()
        return True

    async def touch(self, conversation_id: int) -> None:
        conv = await self.get_conversation_by_id(conversation_id)
        if conv is None:
            return
        conv.updated_at = datetime.utcnow()
        await self.db.flush()

    async def delete_conversation(self, conversation_id: int) -> bool:
        conv = await self.get_conversation_by_id(conversation_id)
        if conv is None:
            return False
        await self.db.delete(conv)
        await self.db.flush()
        return True

    # ---------- Messages ----------
    async def add_message(
        self,
        *,
        conversation_id: int,
        role: str,  # "user" | "assistant" | "system"
        content: str,
        metadata: dict | None = None,
    ) -> ConversationMessage:
        msg = ConversationMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata=metadata or {},
            created_at=datetime.utcnow(),
        )
        self.db.add(msg)

        # update updated_at của conversation cho tiện sort
        res = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = res.scalar_one_or_none()
        if conv is not None:
            conv.updated_at = datetime.utcnow()

        await self.db.flush()
        return msg

    async def get_messages(
        self,
        conversation_id: int,
        *,
        limit: int = 50,
        offset: int = 0,
        newest_first: bool = False,
    ) -> List[ConversationMessage]:
        q = select(ConversationMessage).where(
            ConversationMessage.conversation_id == conversation_id
        )
        q = q.order_by(
            desc(ConversationMessage.id)
            if newest_first
            else ConversationMessage.id.asc()
        )
        q = q.offset(offset).limit(limit)

        res = await self.db.execute(q)
        return list(res.scalars().all())

    async def count_messages(self, conversation_id: int) -> int:
        res = await self.db.execute(
            select(func.count(ConversationMessage.id)).where(
                ConversationMessage.conversation_id == conversation_id
            )
        )
        return int(res.scalar() or 0)

    async def delete_messages(self, conversation_id: int) -> int:
        msgs = await self.get_messages(
            conversation_id, limit=10_000, offset=0, newest_first=False
        )
        for m in msgs:
            await self.db.delete(m)
        await self.db.flush()
        return len(msgs)
