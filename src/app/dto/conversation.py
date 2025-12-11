from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from app.dto.message import MessageRead, MessageBase


# POST /backend-api/f/conversation
class GenerateMessageRequest(BaseModel):
    user_id: str
    conversation_id: Optional[str] = None
    messages: List[MessageBase]
    metadata: dict | None = None


class GenerateMessageSimpleResponse(BaseModel):
    conversation_id: str
    message: MessageRead


# List conversations
class ConversationListItem(BaseModel):
    id: str
    title: str | None = None
    last_message: str | None = None
    updated_at: datetime


class ConversationListResponse(BaseModel):
    items: List[ConversationListItem]
    limit: int
    offset: int
    total: int


# 1.3 Detail
class ConversationDetailResponse(BaseModel):
    conversation_id: str
    messages: List[MessageRead]
