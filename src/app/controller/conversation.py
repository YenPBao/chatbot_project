from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.dto.conversation import ConversationListResponse, ConversationDetailResponse
from app.services.conversation_service import ConversationService
from app.dto.message import MessageRead, MessageContent
from sse_starlette.sse import EventSourceResponse
from app.security.deps import CurrentUser, get_current_user
from app.services.chat_service import ChatService
from app.dto.chat_dto import ChatRequest

router = APIRouter(tags=["conversation"])


@router.post("/f/conversation")
async def post_conversation(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    payload.user_id = current_user.id

    conv_service = ConversationService(db)
    chat_service = ChatService(conv_service)
    return EventSourceResponse(chat_service.stream_conversation(payload))


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations_endpoint(
    user_id: int | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    order: str = Query("updated"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    is_admin = any("admin" in r.lower() for r in current_user.roles)

    if not is_admin:
        if user_id is not None and user_id != current_user.id:
            raise HTTPException(status_code=403, detail="forbidden")
        target_user_id = current_user.id
    else:
        target_user_id = user_id if user_id is not None else current_user.id

    service = ConversationService(db)
    data = await service.list_conversations(
        user_id=target_user_id,
        offset=offset,
        limit=limit,
    )
    return data


@router.get(
    "/conversation/{conversation_id}", response_model=ConversationDetailResponse
)
async def get_conversation_detail(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    service = ConversationService(db)
    raw_msgs = await service.get_conversation_messages(conversation_id)

    if not raw_msgs:
        raise HTTPException(status_code=404, detail="Conversation not found or empty")

    messages: list[MessageRead] = []
    for m in raw_msgs:
        content = MessageContent(**m["content"])
        messages.append(
            MessageRead(
                id=m["id"],
                role=m["role"],
                content=content,
                created_at=m["created_at"],
            )
        )

    return ConversationDetailResponse(
        conversation_id=conversation_id,
        messages=messages,
    )
