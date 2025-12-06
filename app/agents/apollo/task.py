# app/agents/apollo/task.py

import time
from typing import Dict, Any
from app.database import SessionLocal
from celery import shared_task
from app.agents.apollo.graph import build_graph
from app.utils.publisher import publish_event
from app.agents.apollo.nodes import State, Intent, ExtractedApolloFilters
import traceback

from app.services.entities import process_and_save_apollo_results

@shared_task(bind=True, name="run_apollo_agent")
def run_apollo_agent(self, query: str, user_id: str):
    """Execute the Apollo search agent workflow."""
    
    task_id = self.request.id
    start_time = time.time()
    db = SessionLocal()

    try:
        # init agent
        agent = build_graph()

        initial_state: State = {
            "query": query,
            "enriched_query": None,
            "intent": Intent(query=query, intent_type="general_search", entity_type="unknown"),
            "discovery_plan": {},
            "apollo_query": None,
            "serp_queries": [],
            "apollo_results": [],
            "apollo_summary": None,
            "extracted_filters": ExtractedApolloFilters(),
            "task_id": task_id,
        }

        # progress event
        publish_event(
            task_id=task_id,
            agent="apollo_agent",
            event_type="started",
            stage="initializing",
            message="Starting Apollo search agent...",
            payload={"query": query}
        )

        final_state = None

        for event in agent.stream(initial_state):
            node = list(event.keys())[0]
            final_state = event[node]

            if node != "__end__":
                publish_event(
                    task_id=task_id,
                    agent="apollo_agent",
                    event_type="progress",
                    stage=node,
                    message=f"Completed {node}",
                    payload={"node": node}
                )

        # --------- SAVE TO DB ---------

        results = final_state.get("apollo_enriched_results") or final_state.get("apollo_results") or []

        if user_id and results:
            # Save entities using the new service
            # We don't have a finder_session_id here, so we pass None
            process_and_save_apollo_results(db, results, session_id=None)

        # --------- SEND FINAL EVENT ---------

        publish_event(
            task_id=task_id,
            agent="apollo_agent",
            event_type="completed",
            stage="done",
            message="Apollo search completed",
            payload={
                "total_results": len(results),
            }
        )

        return {
            "status": "completed",
            "results_count": len(results),
            "execution_time": time.time() - start_time,
        }

    except Exception as e:
        error_msg = str(e)
        print(traceback.format_exc())

        publish_event(
            task_id=task_id,
            agent="apollo_agent",
            event_type="error",
            stage="failed",
            message=f"Error: {error_msg}",
        )

        raise
