# app/agents/finder/graph.py

from langgraph.graph import StateGraph, END
from app.utils.publisher import publish_event
from typing import Callable
from .nodes import (
    parse_input,
    detect_user_intent,
    clarify_intent_llm,
    product_understanding_llm,
    icp_generator_llm,
    persona_generator_llm,
    discovery_query_generator,
    icp_router
)

def streaming_node(name: str) -> Callable:
    def decorator(fn):
        def wrapped(state):
            tid = state.get("task_id", "unknown")

            publish_event(tid, "finder_agent", "progress", name, f"Starting {name}", {"node": name})

            try:
                result = fn(state)
                publish_event(tid, "finder_agent", "progress", name, f"Completed {name}", {"node": name})
                return result
            except Exception as e:
                publish_event(tid, "finder_agent", "error", name, f"{name} failed: {e}", {"error": str(e)})
                raise
        return wrapped
    return decorator

def build_graph():
    g = StateGraph(dict)

    g.add_node("parse_input", streaming_node("parse_input")(parse_input))
    g.add_node("detect_user_intent", streaming_node("detect_user_intent")(detect_user_intent))
    g.add_node("clarify_intent", streaming_node("clarify_intent")(clarify_intent_llm))
    g.add_node("product_understanding", streaming_node("product_understanding")(product_understanding_llm))
    g.add_node("icp_generator", streaming_node("icp_generator")(icp_generator_llm))
    g.add_node("persona_generator", streaming_node("persona_generator")(persona_generator_llm))
    g.add_node("discovery_query_generator", streaming_node("discovery_query_generator")(discovery_query_generator))
    g.add_node("icp_router", streaming_node("icp_router")(icp_router))

    g.set_entry_point("parse_input")

    g.add_edge("parse_input", "detect_user_intent")
    g.add_edge("detect_user_intent", "clarify_intent")

    g.add_edge("clarify_intent", "product_understanding")
    g.add_edge("product_understanding", "icp_generator")
    g.add_edge("icp_generator", "persona_generator")
    g.add_edge("persona_generator", "discovery_query_generator")
    g.add_edge("discovery_query_generator", "icp_router")

    g.add_edge("icp_router", END)

    return g.compile()
