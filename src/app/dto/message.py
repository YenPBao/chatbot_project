from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

class MessageContent(BaseModel):
    content_type: Literal["text"] = "text"
    parts: List[str] = Field(default_factory=list)

class MessageBase(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    content: MessageContent

class MessageCreate(MessageBase):
    pass

class MessageRead(MessageBase):
    created_at:  Optional[datetime] = None

    class Config:
        from_attributes = True
