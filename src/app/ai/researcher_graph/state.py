from typing import Annotated, TypedDict
from langchain_core.documents import Document
from app.ai.shared.state import reduce_docs


class QueryState(TypedDict):
    """Private state for the retrieve_documents node in the researcher graph."""

    query: str


class ResearcherState(TypedDict, total=False):
    """State of the researcher graph / agent."""

    question: str
    queries: list[str]
    documents: Annotated[list[Document], reduce_docs]
