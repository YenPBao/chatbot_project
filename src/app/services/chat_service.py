# app/services/chat_service.py
from __future__ import annotations

import uuid
import asyncio
import json
import os
from dataclasses import asdict, is_dataclass
from typing import Any, AsyncGenerator, Optional

from langchain_core.runnables import RunnableConfig

from app.services.conversation_service import ConversationService
from app.security.jwt_tokens import create_access_token
from app.ai.retrieval_graph import graph as builder

try:
    from app.dto.events import (
        ResumeConversationEvent,
        InputMessageAuthor,
        InputMessageContent,
        InputMessage,
        InputMessageEvent,
        AssistantMessage,
        DeltaAddPayload,
        DeltaAddEvent,
        MessageMarkerEvent,
        JsonPatchOp,
        DeltaPatchEvent,
        MessageStreamCompleteEvent,
    )

    _HAS_EVENTS_DTO = True
except Exception:
    _HAS_EVENTS_DTO = False


def _dump(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, (dict, list, str, int, float, bool)):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if is_dataclass(obj):
        return asdict(obj)
    return obj.__dict__


def _extract_text_from_content(content_obj: dict) -> str:
    parts = (content_obj or {}).get("parts") or []
    return "\n".join([p for p in parts if isinstance(p, str)]).strip()


def _role_to_lc(role: str) -> str:
    if role == "assistant":
        return "ai"
    return role


class ChatService:
    def __init__(self, conversation_service: ConversationService):
        self.conv_svc = conversation_service

    def _make_graph_config(self, req: Any) -> RunnableConfig:
        metadata = getattr(req, "metadata", None) or {}
        temperature = metadata.get("temperature", None)

        configurable: dict[str, Any] = {
            "retriever_provider": os.getenv("RETRIEVER_PROVIDER", "elastic-local"),
            "embedding_model": os.getenv(
                "EMBEDDING_MODEL", "openai/text-embedding-3-small"
            ),
            "query_model": os.getenv(
                "QUERY_MODEL", os.getenv("MODEL", "openai/gpt-4o-mini")
            ),
            "response_model": os.getenv(
                "RESPONSE_MODEL", os.getenv("MODEL", "openai/gpt-4o-mini")
            ),
            "search_kwargs": {"k": int(os.getenv("RETRIEVER_TOP_K", "4"))},
        }
        if temperature is not None:
            configurable["temperature"] = temperature

        return RunnableConfig(configurable=configurable)

    async def stream_conversation(self, req: Any) -> AsyncGenerator[dict[str, Any] | str, None]:
        conv = await self.conv_svc.get_or_create_conversation(
            req.user_id, req.conversation_id
        )

        for m in req.messages:
            message_id = m.id or str(uuid.uuid4())
            await self.conv_svc.add_message(
                conv.id,
                m.role,
                {"content_type": m.content.content_type, "parts": m.content.parts},
                message_id,
            )

        history = await self.conv_svc.get_conversation_messages(conv.id)

        lc_messages: list[tuple[str, str]] = []
        for item in history:
            role = _role_to_lc(item.get("role", "user"))
            text = _extract_text_from_content(item.get("content") or {})
            if text:
                lc_messages.append((role, text))

        input_msg = req.messages[-1] if req.messages else None
        user_text = (
            input_msg.content.parts[0]
            if input_msg and input_msg.content.parts
            else ""
        )

        async def _yield_event(obj: Any, event: Optional[str] = None):
            payload: dict[str, Any] = {"data": _dump(obj)}
            if event is not None:
                payload["event"] = event
            yield payload

        # delta_encoding header
        async for s in _yield_event("v1", event="delta_encoding"):
            yield s

        token = create_access_token(sub=str(conv.id), roles=[])

        if _HAS_EVENTS_DTO:
            resume_evt = ResumeConversationEvent(
                token=token, conversation_id=str(conv.id)
            )
            async for s in _yield_event(resume_evt):
                yield s
        else:
            payload = {
                "type": "resume_conversation_token",
                "token": token,
                "conversation_id": conv.id,
            }
            async for s in _yield_event(payload):
                yield s

        if input_msg:
            if _HAS_EVENTS_DTO:
                evt = InputMessageEvent(
                    conversation_id=conv.id,
                    input_message=InputMessage(
                        id=input_msg.id or "",
                        author=InputMessageAuthor(role=input_msg.role),
                        content=InputMessageContent(
                            content_type=input_msg.content.content_type,
                            parts=input_msg.content.parts,
                        ),
                        status="finished_successfully",
                    ),
                )
                async for s in _yield_event(evt):
                    yield s
            else:
                payload = {
                    "type": "input_message",
                    "input_message": {
                        "id": input_msg.id or "",
                        "author": {"role": input_msg.role},
                        "create_time": None,
                        "content": {
                            "content_type": input_msg.content.content_type,
                            "parts": input_msg.content.parts,
                        },
                        "status": "finished_successfully",
                    },
                    "conversation_id": conv.id,
                }
                async for s in _yield_event(payload):
                    yield s

        assistant_id = str(uuid.uuid4())
        try:
            config = self._make_graph_config(req)
            result = await builder.ainvoke({"messages": lc_messages}, config)
            answer = ""
            msgs = result.get("messages") or []
            if msgs:
                answer = getattr(msgs[-1], "content", "") or ""
            answer = str(answer).strip()
        except Exception as e:
            err_payload = {
                "type": "message_stream_error",
                "error": str(e),
            }
            async for s in _yield_event(err_payload):
                yield s
            complete_payload = {
                "type": "message_stream_complete",
                "conversation_id": conv.id,
            }
            async for s in _yield_event(complete_payload):
                yield s
            yield "[DONE]"
            return

        assistant_msg = await self.conv_svc.add_message(
            conv.id,
            "assistant",
            {"content_type": "text", "parts": [answer]},
            assistant_id,
        )
        assistant_id = assistant_msg.id

        if _HAS_EVENTS_DTO:
            add_evt = DeltaAddEvent(
                o="add",
                v=DeltaAddPayload(
                    message=AssistantMessage(
                        id=assistant_id,
                        author=InputMessageAuthor(role="assistant"),
                        content=InputMessageContent(content_type="text", parts=[""]),
                        status="in_progress",
                        metadata={},
                        parent_id=(input_msg.id if input_msg else None),
                    ),
                    conversation_id=conv.id,
                ),
            )
            async for s in _yield_event(add_evt, event="delta"):
                yield s
        else:
            payload = {
                "o": "add",
                "v": {
                    "message": {
                        "id": assistant_id,
                        "author": {"role": "assistant"},
                        "create_time": None,
                        "update_time": None,
                        "content": {"content_type": "text", "parts": [""]},
                        "status": "in_progress",
                        "metadata": {
                            "parent_id": (input_msg.id if input_msg else None)
                        },
                    },
                    "conversation_id": conv.id,
                },
            }
            async for s in _yield_event(payload, event="delta"):
                yield s

        if _HAS_EVENTS_DTO:
            marker_evt = MessageMarkerEvent(
                conversation_id=conv.id,
                message_id=assistant_id,
                marker="user_visible_token",
                event="first",
            )
            async for s in _yield_event(marker_evt):
                yield s
        else:
            payload = {
                "type": "message_marker",
                "conversation_id": conv.id,
                "message_id": assistant_id,
                "marker": "user_visible_token",
                "event": "first",
            }
            async for s in _yield_event(payload):
                yield s

        for word in answer.split():
            patch = [
                {
                    "p": "/message/content/parts/0",
                    "o": "append",
                    "v": word + " ",
                }
            ]
            if _HAS_EVENTS_DTO:
                ops = [JsonPatchOp(p=o["p"], o=o["o"], v=o["v"]) for o in patch]
                evt = DeltaPatchEvent(v=ops)
                async for s in _yield_event(evt, event="delta"):
                    yield s
            else:
                payload = {"v": patch}
                async for s in _yield_event(payload, event="delta"):
                    yield s
            await asyncio.sleep(0.01)

        final_patch = [
            {"p": "/message/status", "o": "replace", "v": "finished_successfully"},
            {"p": "/message/end_turn", "o": "replace", "v": True},
            {"p": "/message/metadata", "o": "append", "v": {"is_complete": True}},
        ]
        if _HAS_EVENTS_DTO:
            ops = [JsonPatchOp(p=o["p"], o=o["o"], v=o["v"]) for o in final_patch]
            evt = DeltaPatchEvent(v=ops)
            async for s in _yield_event(evt, event="delta"):
                yield s
        else:
            payload = {"v": final_patch}
            async for s in _yield_event(payload, event="delta"):
                yield s

        if _HAS_EVENTS_DTO:
            done_evt = MessageStreamCompleteEvent(conversation_id=conv.id)
            async for s in _yield_event(done_evt):
                yield s
        else:
            payload = {
                "type": "message_stream_complete",
                "conversation_id": conv.id,
            }
            async for s in _yield_event(payload):
                yield s

        yield "[DONE]"
