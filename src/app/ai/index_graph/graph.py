import json
from typing import Optional

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.ai.index_graph.configuration import IndexConfiguration
from app.ai.index_graph.state import IndexState
from app.ai.shared import retrieval
from app.ai.shared.state import reduce_docs


async def index_docs(state: IndexState, *, config: Optional[RunnableConfig] = None) -> dict[str, str]:
    if not config:
        raise ValueError("Configuration required to run index_docs.")

    configuration = IndexConfiguration.from_runnable_config(config)

    docs = state.get("docs") or []
    if not docs:
        with open(configuration.docs_file, encoding="utf-8") as f:
            serialized_docs = json.load(f)
            docs = reduce_docs([], serialized_docs)

    with retrieval.make_retriever(config) as retriever:
        await retriever.aadd_documents(docs)
    return {"docs": []}


# Define the graph
builder = StateGraph(IndexState, config_schema=IndexConfiguration)
builder.add_node(index_docs)
builder.add_edge(START, "index_docs")
builder.add_edge("index_docs", END)
graph = builder.compile()
graph.name = "IndexGraph"
