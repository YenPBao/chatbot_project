# app/ai/researcher_graph/__init__.py
from app.ai.researcher_graph import graph


async def ainvoke(input_data):
    return await graph(input_data)
