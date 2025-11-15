# app/agents/search_apollo_agent.py
import time
from typing import Dict
from celery import shared_task
from langgraph.graph import StateGraph, END
from app.utils.publisher import publish_event


class AgentState(Dict):
    query: str
    result: str = ""


def create_test_agent():
    workflow = StateGraph(AgentState)

    def make_node(step_num):
        def node(state: AgentState) -> AgentState:
            time.sleep(5)

            publish_event(
                task_id=state.get("task_id"),
                agent="search_agent",
                event_type="progress",
                stage=f"node_{step_num}",
                message=f"Node {step_num} executed",
                payload={"node": step_num},
            )

            # just pass state forward
            return state

        return node

    # Create 4 nodes dynamically
    workflow.add_node("node_1", make_node(1))
    workflow.add_node("node_2", make_node(2))
    workflow.add_node("node_3", make_node(3))
    workflow.add_node("node_4", make_node(4))

    # Final worker
    def final_node(state: AgentState) -> AgentState:
        time.sleep(1)
        publish_event(
            task_id=state.get("task_id"),
            agent="search_agent",
            event_type="progress",
            stage="finalizing",
            message="Finalizing output...",
            payload={},
        )
        state["result"] = f"Query processed: {state['query']}"
        return state

    workflow.add_node("final_node", final_node)

    # Define flow
    workflow.set_entry_point("node_1")
    workflow.add_edge("node_1", "node_2")
    workflow.add_edge("node_2", "node_3")
    workflow.add_edge("node_3", "node_4")
    workflow.add_edge("node_4", "final_node")
    workflow.add_edge("final_node", END)

    return workflow.compile()


agent = create_test_agent()


@shared_task(bind=True, name="run_apollo_agent")
def run_apollo_agent(self, query: str):
    task_id = self.request.id

    try:
        final_state = None

        # STREAM execution of graph (IMPORTANT)
        for event in agent.stream({"query": query, "task_id": task_id}):
            node = list(event.keys())[0]
            state = event[node]

            publish_event(
                task_id=task_id,
                agent="search_agent",
                event_type="progress",
                stage=node,
                message=f"{node} executed",
                payload=state,
            )

            final_state = state

        # Send final event
        publish_event(
            task_id=task_id,
            agent="search_agent",
            event_type="completed",
            stage="done",
            message="Search completed!",
            payload={"result": final_state["result"]},
        )

        return final_state["result"]

    except Exception as e:
        publish_event(
            task_id=task_id,
            agent="search_agent",
            event_type="error",
            stage="failed",
            message=str(e),
        )
        raise

