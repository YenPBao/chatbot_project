from typing import Any, List, Literal
from pydantic import BaseModel,Field
import time

class ResumeConversationEvent(BaseModel):
    type: Literal["resume_conversation_token"] = "resume_conversation_token"
    token: str
    conversation_id: str

class InputMessageAuthor(BaseModel):
    role: str

class InputMessageContent(BaseModel):
    content_type: str = "text"
    parts: List[str]

class InputMessage(BaseModel):
    id: str
    author: InputMessageAuthor
    create_time: float = Field(default_factory=time.time)
    content: InputMessageContent
    status: str = "finished_successfully"

class InputMessageEvent(BaseModel):
    type: Literal["input_message"] = "input_message"
    input_message: InputMessage
    conversation_id: str

class AssistantMessage(BaseModel):
    id: str
    author: InputMessageAuthor
    create_time:float = Field(default_factory=time.time)
    update_time: float = Field(default_factory=time.time)
    content: InputMessageContent
    status: str
    metadata: dict

class DeltaAddPayload(BaseModel):
    message: AssistantMessage
    conversation_id: str

class DeltaAddEvent(BaseModel):
    o: Literal["add"] = "add"
    v: DeltaAddPayload

class MessageMarkerEvent(BaseModel):
    type: Literal["message_marker"] = "message_marker"
    conversation_id: str
    message_id: str
    marker: str
    event: str

class JsonPatchOp(BaseModel):
    p: str
    o: str
    v: Any

class DeltaPatchEvent(BaseModel):
    v: List[JsonPatchOp]

class MessageStreamCompleteEvent(BaseModel):
    type: Literal["message_stream_complete"] = "message_stream_complete"
    conversation_id: str
