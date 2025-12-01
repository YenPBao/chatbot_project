# src/test/test_ai.py
import asyncio
import os
import sys
from pathlib import Path
from langchain_core.runnables import RunnableConfig
ROOT_DIR = Path(__file__).resolve().parents[1]  # D:\chatbot-project\src
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.ai.retrieval_graph.graph import graph as retrieval_graph  # noqa: E402


async def main() -> None:
    # Debug xem key đã set chưa
    print("GOOGLE_API_KEY set:", bool(os.getenv("GOOGLE_API_KEY")))

    config = RunnableConfig(
        configurable={
            "retriever_provider": os.getenv("RETRIEVER_PROVIDER", "elastic-local"),
            "embedding_model": os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small"),
            "query_model": "google/gemini-2.5-flash",
            "response_model": "google/gemini-2.5-flash",
            "search_kwargs": {"k": 2},
        }
    )

    # messages đúng kiểu mà ChatService truyền
    messages = [("user", "Test graph: hãy tóm tắt ngắn gọn LangGraph là gì.")]

    result = await retrieval_graph.ainvoke({"messages": messages}, config)

    print(">>> Result type:", type(result))
    print(">>> Result keys:", list(result.keys()))

    msgs = result.get("messages") or []
    print(">>> Số messages trong state:", len(msgs))
    if msgs:
        last = msgs[-1]
        print(">>> Last message type:", getattr(last, "type", None))
        print(">>> Last message content:", getattr(last, "content", None))


if __name__ == "__main__":
    asyncio.run(main())
