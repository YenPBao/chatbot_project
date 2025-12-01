from typing import Any, Literal, TypedDict, cast

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.ai.retrieval_graph.configuration import AgentConfiguration
from app.ai.researcher_graph.graph import graph as researcher_graph
from app.ai.retrieval_graph.state import AgentState, InputState, Router
from app.ai.shared.utils import format_docs, load_chat_model


async def analyze_and_route_query(
    state: AgentState, *, config: RunnableConfig
) -> dict[str, dict]:
    configuration = AgentConfiguration.from_runnable_config(config)
    model = load_chat_model(configuration.query_model)

    state_messages: list[BaseMessage] = state.get("messages", [])  # type: ignore[assignment]
    messages = [
        {"role": "system", "content": configuration.router_system_prompt}
    ] + state_messages

    # Router là Pydantic BaseModel
    router_obj = await model.with_structured_output(Router).ainvoke(messages)
    # Lưu vào state dưới dạng dict cho dễ dùng
    return {"router": router_obj.model_dump()}


def route_query(
    state: AgentState,
) -> Literal["create_research_plan", "ask_for_more_info", "respond_to_general_query"]:
    router = state.get("router") or {}
    _type = router.get("type")

    if _type == "langchain":
        return "create_research_plan"
    elif _type == "more-info":
        return "ask_for_more_info"
    elif _type == "general":
        return "respond_to_general_query"
    else:
        raise ValueError(f"Unknown router type {_type}")


async def ask_for_more_info(
    state: AgentState, *, config: RunnableConfig
) -> dict[str, list[BaseMessage]]:
    configuration = AgentConfiguration.from_runnable_config(config)
    model = load_chat_model(configuration.query_model)

    router = state.get("router") or {}
    logic = router.get("logic", "")

    system_prompt = configuration.more_info_system_prompt.format(logic=logic)
    state_messages: list[BaseMessage] = state.get("messages", [])  # type: ignore[assignment]

    messages = [{"role": "system", "content": system_prompt}] + state_messages
    response = await model.ainvoke(messages)
    return {"messages": [response]}


async def respond_to_general_query(
    state: AgentState, *, config: RunnableConfig
) -> dict[str, list[BaseMessage]]:
    configuration = AgentConfiguration.from_runnable_config(config)
    model = load_chat_model(configuration.query_model)

    router = state.get("router") or {}
    logic = router.get("logic", "")

    system_prompt = configuration.general_system_prompt.format(logic=logic)
    state_messages: list[BaseMessage] = state.get("messages", [])  # type: ignore[assignment]

    messages = [{"role": "system", "content": system_prompt}] + state_messages
    response = await model.ainvoke(messages)
    return {"messages": [response]}


async def create_research_plan(
    state: AgentState, *, config: RunnableConfig
) -> dict[str, list[str] | str]:
    class Plan(TypedDict):
        steps: list[str]

    configuration = AgentConfiguration.from_runnable_config(config)
    model = load_chat_model(configuration.query_model).with_structured_output(Plan)

    state_messages: list[BaseMessage] = state.get("messages", [])  # type: ignore[assignment]
    messages = [
        {"role": "system", "content": configuration.research_plan_system_prompt}
    ] + state_messages

    response = cast(Plan, await model.ainvoke(messages))
    return {"steps": response["steps"], "documents": "delete"}


async def conduct_research(state: AgentState) -> dict[str, Any]:
    steps: list[str] = state.get("steps") or []  # type: ignore[assignment]
    if not steps:
        return {"documents": state.get("documents", []), "steps": []}

    result = await researcher_graph.ainvoke({"question": steps[0]})
    return {"documents": result["documents"], "steps": steps[1:]}


def check_finished(state: AgentState) -> Literal["respond", "conduct_research"]:
    steps: list[str] = state.get("steps") or []  # type: ignore[assignment]
    if len(steps) > 0:
        return "conduct_research"
    else:
        return "respond"


async def respond(
    state: AgentState, *, config: RunnableConfig
) -> dict[str, list[BaseMessage]]:
    configuration = AgentConfiguration.from_runnable_config(config)
    model = load_chat_model(configuration.response_model)

    docs = state.get("documents") or []
    context = format_docs(docs)
    prompt = configuration.response_system_prompt.format(context=context)

    state_messages: list[BaseMessage] = state.get("messages", [])  # type: ignore[assignment]
    messages = [{"role": "system", "content": prompt}] + state_messages

    response = await model.ainvoke(messages)
    return {"messages": [response]}


# Define the graph
builder = StateGraph(AgentState, input=InputState, config_schema=AgentConfiguration)
builder.add_node(analyze_and_route_query)
builder.add_node(ask_for_more_info)
builder.add_node(respond_to_general_query)
builder.add_node(conduct_research)
builder.add_node(create_research_plan)
builder.add_node(respond)

builder.add_edge(START, "analyze_and_route_query")
builder.add_conditional_edges("analyze_and_route_query", route_query)
builder.add_edge("create_research_plan", "conduct_research")
builder.add_conditional_edges("conduct_research", check_finished)
builder.add_edge("ask_for_more_info", END)
builder.add_edge("respond_to_general_query", END)
builder.add_edge("respond", END)

graph = builder.compile()
graph.name = "RetrievalGraph"
