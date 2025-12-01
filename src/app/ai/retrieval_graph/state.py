from typing import Annotated, Literal, TypedDict
from langchain_core.documents import Document
from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages

from app.ai.shared.state import reduce_docs
from pydantic import BaseModel

class Router(BaseModel):
    logic: str
    type: Literal["more-info", "langchain", "general"]


class InputState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


class AgentState(InputState, total=False):
    router: Router
    steps: list[str]
    documents: Annotated[list[Document], reduce_docs]
