import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.model.conversation import Conversation
from app.model.message import Message
from app.core.redis_client import rds


class ConversationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.redis = rds
    @staticmethod
    def _conv_history_key(conversation_id: str) -> str:
        return f"conv:{conversation_id}:history"

    @staticmethod
    def _user_conv_list_key(user_id: str, offset: int, limit: int) -> str:
        return f"user:{user_id}:conversation_list:{offset}:{limit}:updated"

    @staticmethod
    def _user_conv_list_pattern(user_id: str) -> str:
        return f"user:{user_id}:conversation_list:*"

    async def get_or_create_conversation(
        self,
        user_id: str,
        conversation_id: Optional[str] = None,
    ) -> Conversation:
        if conversation_id:
            res = await self.db.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conv = res.scalar_one_or_none()
            if conv:
                return conv
            
        conv_id = conversation_id or str(uuid.uuid4())
        now = datetime.utcnow()

        conv = Conversation(id=conv_id, user_id=user_id)
        if hasattr(conv, "created_at"):
            conv.created_at = now
        if hasattr(conv, "updated_at"):
            conv.updated_at = now

        self.db.add(conv)
        await self.db.flush() 
        pattern = self._user_conv_list_pattern(user_id)
        async for k in self.redis.scan_iter(match=pattern):
            await self.redis.delete(k)

        return conv

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: dict,
        msg_id: Optional[str] = None,
    ) -> Message:

        mid = msg_id or str(uuid.uuid4())
        content_json = json.dumps(content)
        now = datetime.utcnow()

        msg = Message(
            id=mid,
            conversation_id=conversation_id,
            role=role,
            content=content_json,
        )
        # nếu model có created_at/updated_at thì set
        if hasattr(msg, "created_at"):
            msg.created_at = now
        if hasattr(msg, "updated_at"):
            msg.updated_at = now

        self.db.add(msg)

        # Cập nhật updated_at của conversation
        conv = await self.db.get(Conversation, conversation_id)
        if conv and hasattr(conv, "updated_at"):
            conv.updated_at = now

        await self.db.flush()

        # Lưu vào Redis history, kèm created_at để controller dùng luôn
        history_key = self._conv_history_key(conversation_id)
        history_item = {
            "id": mid,
            "role": role,
            "content": content,
            "created_at": now.isoformat(),
        }
        await self.redis.rpush(history_key, json.dumps(history_item))

        await self.redis.ltrim(history_key, -200, -1)
        # TTL 10 phút
        await self.redis.expire(history_key, 600)

        # Invalidate cache list hội thoại của user (đổi last_message, updated_at)
        if conv:
            pattern = self._user_conv_list_pattern(conv.user_id)
            async for k in self.redis.scan_iter(match=pattern):
                await self.redis.delete(k)

        return msg


    async def list_conversations(self, user_id: str, offset: int = 0, limit: int = 20):

        key = self._user_conv_list_key(user_id, offset, limit)
        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)

        q = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        res = await self.db.execute(q)
        items = res.scalars().all()

        out_items = []
        for c in items:
            last_text = None

            msg_res = await self.db.execute(
                select(Message)
                .where(Message.conversation_id == c.id)
                .order_by(Message.created_at.desc())
                .limit(1)
            )
            last_msg = msg_res.scalar_one_or_none()
            if last_msg:
                try:
                    last_content = json.loads(last_msg.content)
                except Exception:
                    last_content = {}
                parts = (last_content or {}).get("parts") or []
                last_text = parts[0] if parts else None

            out_items.append(
                {
                    "id": c.id,
                    "title": c.title or "",
                    "last_message": last_text,
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                }
            )

        payload = {
            "items": out_items,
            "limit": limit,
            "offset": offset,
            "total": len(out_items),
        }

        await self.redis.set(key, json.dumps(payload), ex=600)
        return payload

    async def get_conversation_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        key = self._conv_history_key(conversation_id)
        items = await self.redis.lrange(key, 0, -1)

        if items:
            parsed = [json.loads(i) for i in items]
            # đảm bảo luôn có created_at (phòng trường hợp dữ liệu cache cũ)
            for it in parsed:
                it.setdefault("created_at", None)
            return parsed

        # Cache không có -> đọc từ DB
        res = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        msgs = res.scalars().all()

        out: List[Dict[str, Any]] = []
        for m in msgs:
            try:
                content_obj = json.loads(m.content)
            except Exception:
                content_obj = {}

            out.append(
                {
                    "id": m.id,
                    "role": m.role,
                    "content": content_obj,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
            )

        # Ghi vào cache để lần sau dùng
        if out:
            payload_for_cache = [
                {
                    "id": o["id"],
                    "role": o["role"],
                    "content": o["content"],
                    "created_at": o["created_at"],
                }
                for o in out
            ]
            await self.redis.rpush(
                key,
                *[json.dumps(x) for x in payload_for_cache],
            )
            await self.redis.expire(key, 600)

        return out
