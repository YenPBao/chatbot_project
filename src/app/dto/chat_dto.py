from pydantic import BaseModel
from typing import List, Optional
from app.dto.message import MessageBase

# Schema cho dữ liệu yêu cầu gửi từ người dùng
class ChatRequest(BaseModel):
    user_id: int
    conversation_id: str
    context: Optional[List[str]] = []  # Các tài liệu hoặc ngữ cảnh thêm (nếu có)
    messages: Optional[List[MessageBase]]

# Schema cho phản hồi trả về từ chatbot
class ChatResponse(BaseModel):
    answer: str  # Câu trả lời của chatbot
    sources: Optional[List[str]] = []  # Các nguồn (tài liệu) mà chatbot sử dụng để trả lời
