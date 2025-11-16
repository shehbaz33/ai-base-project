# app/agents/apollo/graph.py

from langgraph.graph import StateGraph, END
from app.agents.apollo.nodes import (
    State,
    analyze_intent,
    query_enricher,
    autonomous_discovery_planner,
    planner_pipeline,
    apollo_filter_extractor,
    apollo_people_query_planner_llm,
    apollo_company_query_planner_llm,
    normalize_apollo_locations,
    apollo_people_search,
    apollo_company_search,
    enrich_all_apollo_people,
    enrich_all_apollo_companies,
    summarize_apollo_results,
    fallback_serp_node,
    apollo_router,
    apollo_planner_router,
    apollo_search_type_router,
    apollo_post_process_router
)
from app.utils.publisher import publish_event

def streaming_node(name):
    """Wrapper for nodes to publish progress updates."""
    def decorator(fn):
        def wrapped(state: State) -> State:
            task_id = state.get("task_id", "unknown")
            
            # Publish start of node execution
            publish_event(
                task_id=task_id,
                agent="apollo_agent",
                event_type="progress",
                stage=name,
                message=f"Starting {name.replace('_', ' ')}...",
                payload={"node": name, "status": "started"}
            )
            
            try:
                # Execute the node
                result = fn(state)
                
                # Publish completion
                publish_event(
                    task_id=task_id,
                    agent="apollo_agent",
                    event_type="progress",
                    stage=name,
                    message=f"Completed {name.replace('_', ' ')}",
                    payload={"node": name, "status": "completed"}
                )
                
                return result
            except Exception as e:
                # Publish error
                publish_event(
                    task_id=task_id,
                    agent="apollo_agent",
                    event_type="error",
                    stage=name,
                    message=f"Error in {name}: {str(e)}",
                    payload={"node": name, "status": "error", "error": str(e)}
                )
                raise
        
        return wrapped
    return decorator


def build_graph():
    graph = StateGraph(State)

    # 🧩 Add nodes (including both people + company enrichment steps)
    graph.add_node("analyze_intent", streaming_node("analyze_intent")(analyze_intent))
    graph.add_node("query_enricher", streaming_node("query_enricher")(query_enricher))
    graph.add_node("discovery_planner", streaming_node("discovery_planner")(autonomous_discovery_planner))
    graph.add_node("planner_pipeline", streaming_node("planner_pipeline")(planner_pipeline))
    graph.add_node("apollo_filter_extractor", streaming_node("apollo_filter_extractor")(apollo_filter_extractor))
    graph.add_node("apollo_people_query_planner_llm", streaming_node("apollo_people_query_planner")(apollo_people_query_planner_llm))
    graph.add_node("apollo_company_query_planner_llm", streaming_node("apollo_company_query_planner")(apollo_company_query_planner_llm))
    graph.add_node("normalize_apollo_locations", streaming_node("normalize_locations")(normalize_apollo_locations))
    graph.add_node("apollo_people_search", streaming_node("apollo_people_search")(apollo_people_search))
    graph.add_node("apollo_company_search", streaming_node("apollo_company_search")(apollo_company_search))
    graph.add_node("enrich_all_apollo_people", streaming_node("enrich_people")(enrich_all_apollo_people))
    graph.add_node("enrich_all_apollo_companies", streaming_node("enrich_companies")(enrich_all_apollo_companies))
    graph.add_node("summarize_apollo_results", streaming_node("summarize_results")(summarize_apollo_results))
    graph.add_node("fallback_serp_node", streaming_node("fallback_serp")(fallback_serp_node))

    # ⚙️ Wiring the graph
    graph.set_entry_point("analyze_intent")
    graph.add_edge("analyze_intent", "query_enricher")
    graph.add_edge("query_enricher", "discovery_planner")

    # Discovery Planner → Pipeline
    graph.add_edge("discovery_planner", "planner_pipeline")

    # Pipeline → Conditional Apollo decision
    graph.add_conditional_edges(
        "planner_pipeline",
        apollo_router,
        {
            "apollo_filter_extractor": "apollo_filter_extractor",
            "fallback_serp_node": "fallback_serp_node"
        }
    )

    # Filter extractor → Correct planner (people/company)
    graph.add_conditional_edges(
        "apollo_filter_extractor",
        apollo_planner_router,
        {
            "apollo_people_query_planner_llm": "apollo_people_query_planner_llm",
            "apollo_company_query_planner_llm": "apollo_company_query_planner_llm"
        }
    )

    # Both planners → normalization
    graph.add_edge("apollo_people_query_planner_llm", "normalize_apollo_locations")
    graph.add_edge("apollo_company_query_planner_llm", "normalize_apollo_locations")

    # Normalization → Route based on entity type
    graph.add_conditional_edges(
        "normalize_apollo_locations",
        apollo_search_type_router,
        {
            "apollo_people_search": "apollo_people_search",
            "apollo_company_search": "apollo_company_search",
            "fallback_serp_node": "fallback_serp_node"
        }
    )

    # 👥 PEOPLE flow → enrichment → summary
    graph.add_edge("apollo_people_search", "enrich_all_apollo_people")
    graph.add_edge("enrich_all_apollo_people", "summarize_apollo_results")

    # 🏢 COMPANY flow → enrichment → summary
    graph.add_edge("apollo_company_search", "enrich_all_apollo_companies")
    graph.add_edge("enrich_all_apollo_companies", "summarize_apollo_results")

    # 🌍 Fallback → END
    graph.add_edge("summarize_apollo_results", END)
    graph.add_edge("fallback_serp_node", END)

    return graph.compile()