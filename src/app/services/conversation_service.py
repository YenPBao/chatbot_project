import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.model.conversation import Conversation
from app.model.message import Message
from app.core.redis_client import rds


class ConversationService:
    HISTORY_MAX = 200
    HISTORY_TTL_SECONDS = 600
    LIST_TTL_SECONDS = 600

    def __init__(self, db: AsyncSession):
        self.db = db
        self.redis = rds

    @staticmethod
    def _to_str(v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, bytes):
            return v.decode("utf-8")
        return str(v)

    @staticmethod
    def _conv_history_key(conversation_id: str) -> str:
        return f"conv:{conversation_id}:history"

    @staticmethod
    def _user_conv_list_key(user_id: str, offset: int, limit: int) -> str:
        return f"user:{user_id}:conversation_list:{offset}:{limit}:updated"

    @staticmethod
    def _user_conv_list_pattern(user_id: str) -> str:
        return f"user:{user_id}:conversation_list:*"

    async def _invalidate_user_conv_list(self, user_id: str) -> None:
        pattern = self._user_conv_list_pattern(user_id)
        keys: List[Any] = []
        async for k in self.redis.scan_iter(match=pattern):
            keys.append(k)
        if keys:
            await self.redis.delete(*keys)

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
        await self._invalidate_user_conv_list(user_id)
        return conv

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: dict,
        msg_id: Optional[str] = None,
    ) -> Message:
        conv = await self.db.get(Conversation, conversation_id)
        if not conv:
            raise ValueError("Conversation not found")

        mid = msg_id or str(uuid.uuid4())
        now = datetime.utcnow()

        msg = Message(
            id=mid,
            conversation_id=conversation_id,
            role=role,
            content=json.dumps(content),
        )
        if hasattr(msg, "created_at"):
            msg.created_at = now
        if hasattr(msg, "updated_at"):
            msg.updated_at = now

        self.db.add(msg)

        if hasattr(conv, "updated_at"):
            conv.updated_at = now

        await self.db.flush()

        history_key = self._conv_history_key(conversation_id)
        history_item = {
            "id": mid,
            "role": role,
            "content": content,
            "created_at": now.isoformat(),
        }
        await self.redis.rpush(history_key, json.dumps(history_item))
        await self.redis.ltrim(history_key, -self.HISTORY_MAX, -1)
        await self.redis.expire(history_key, self.HISTORY_TTL_SECONDS)
        await self._invalidate_user_conv_list(conv.user_id)

        return msg

    async def list_conversations(
        self, user_id: str, offset: int = 0, limit: int = 20
    ) -> Dict[str, Any]:
        key = self._user_conv_list_key(user_id, offset, limit)
        cached = await self.redis.get(key)
        cached_s = self._to_str(cached)
        if cached_s:
            try:
                return json.loads(cached_s)
            except Exception:
                pass

        total_res = await self.db.execute(
            select(func.count())
            .select_from(Conversation)
            .where(Conversation.user_id == user_id)
        )
        total = int(total_res.scalar() or 0)
        m2 = aliased(Message)
        sub = (
            select(
                Message.conversation_id.label("cid"),
                func.max(Message.created_at).label("max_created"),
            )
            .group_by(Message.conversation_id)
            .subquery()
        )

        q = (
            select(Conversation, m2)
            .outerjoin(sub, sub.c.cid == Conversation.id)
            .outerjoin(
                m2,
                and_(
                    m2.conversation_id == sub.c.cid,
                    m2.created_at == sub.c.max_created,
                ),
            )
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )

        res = await self.db.execute(q)
        rows: List[Tuple[Conversation, Optional[Message]]] = res.all()

        out_items: List[Dict[str, Any]] = []
        for conv, last_msg in rows:
            last_text = None
            if last_msg and last_msg.content:
                try:
                    last_content = json.loads(last_msg.content)
                except Exception:
                    last_content = {}
                parts = (last_content or {}).get("parts") or []
                last_text = parts[0] if parts else None

            out_items.append(
                {
                    "id": conv.id,
                    "title": getattr(conv, "title", "") or "",
                    "last_message": last_text,
                    "updated_at": (
                        conv.updated_at.isoformat()
                        if getattr(conv, "updated_at", None)
                        else None
                    ),
                }
            )

        payload = {
            "items": out_items,
            "limit": limit,
            "offset": offset,
            "total": total,
        }

        await self.redis.set(key, json.dumps(payload), ex=self.LIST_TTL_SECONDS)
        return payload

    async def get_conversation_messages(
        self, conversation_id: str
    ) -> List[Dict[str, Any]]:
        key = self._conv_history_key(conversation_id)

        items = await self.redis.lrange(key, 0, -1)
        if items:
            out: List[Dict[str, Any]] = []
            for raw in items:
                s = self._to_str(raw)
                if not s:
                    continue
                try:
                    it = json.loads(s)
                except Exception:
                    continue
                it.setdefault("created_at", None)
                out.append(it)
            return out

        res = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        msgs = res.scalars().all()

        out_msgs: List[Dict[str, Any]] = []
        for m in msgs:
            try:
                content_obj = json.loads(m.content) if m.content else {}
            except Exception:
                content_obj = {}

            out_msgs.append(
                {
                    "id": m.id,
                    "role": m.role,
                    "content": content_obj,
                    "created_at": (
                        m.created_at.isoformat()
                        if getattr(m, "created_at", None)
                        else None
                    ),
                }
            )

        if out_msgs:
            to_cache = out_msgs[-self.HISTORY_MAX :]
            await self.redis.rpush(key, *[json.dumps(x) for x in to_cache])
            await self.redis.ltrim(key, -self.HISTORY_MAX, -1)
            await self.redis.expire(key, self.HISTORY_TTL_SECONDS)

        return out_msgs
