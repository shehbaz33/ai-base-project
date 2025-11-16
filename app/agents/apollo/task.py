# app/agents/apollo/task.py

import time
from typing import Dict, Any
from celery import shared_task
from app.agents.apollo.graph import build_graph
from app.utils.publisher import publish_event
from app.agents.apollo.nodes import State, Intent, ExtractedApolloFilters
import traceback

@shared_task(bind=True, name="run_apollo_agent")
def run_apollo_agent(self, query: str):
    """Execute the Apollo search agent workflow."""
    task_id = self.request.id
    start_time = time.time()
    
    try:
        # Initialize the agent
        agent = build_graph()
        
        # Prepare initial state
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

        # Publish start event
        publish_event(
            task_id=task_id,
            agent="apollo_agent",
            event_type="started",
            stage="initializing",
            message="Starting Apollo search agent...",
            payload={"query": query}
        )

        final_state = None
        
        # Execute the agent workflow
        for event in agent.stream(initial_state):
            node = list(event.keys())[0]
            final_state = event[node]
            
            # Publish progress for each node
            if node != "__end__":
                publish_event(
                    task_id=task_id,
                    agent="apollo_agent",
                    event_type="progress",
                    stage=node,
                    message=f"Completed {node}",
                    payload={"node": node, "status": "in_progress"}
                )

        # Calculate execution time
        execution_time = time.time() - start_time
        
        # Publish completion event
        publish_event(
            task_id=task_id,
            agent="apollo_agent",
            event_type="completed",
            stage="done",
            message="Apollo search completed successfully",
            payload={
                "execution_time": execution_time,
                "results_count": len(final_state.get("apollo_results", [])),
                "summary": final_state.get("apollo_summary")
            }
        )

        return {
            "status": "completed",
            "results": final_state.get("apollo_results", []),
            "summary": final_state.get("apollo_summary"),
            "execution_time": execution_time
        }

    except Exception as e:
        # Publish error event
        error_msg = str(e)
        print(f"Error in run_apollo_agent: {error_msg}")
        print(traceback.format_exc()) 
        publish_event(
            task_id=task_id,
            agent="apollo_agent",
            event_type="error",
            stage="failed",
            message=f"Apollo search failed: {error_msg}",
            payload={"error": error_msg}
        )
        
        # Re-raise the exception to mark the task as failed
        raise