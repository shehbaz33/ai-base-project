# app/agents/finder/task.py

import time, traceback, sys
from celery import shared_task
from typing import Optional, Dict, Any
import json
sys.setrecursionlimit(3000)

from app.utils.publisher import publish_event
from .graph import build_graph
from app.agents.apollo.graph import build_graph as build_apollo_graph
from app.database import SessionLocal
from app.services.finder import (
    create_finder_session,
    update_finder_session_query,
    update_finder_session_status
)

def run_finder_agent_impl(task_id: str, input_text: str, user_id: Optional[str] = None):

    # task_id passed explicitly
    start = time.time()
    db = SessionLocal()
    finder_session = None

    publish_event(task_id, "finder_agent", "started", "initializing",
                  "Finder Agent started", {"input": input_text})

    initial_state = {
        "input_text": input_text,
        "query": input_text,
        "task_id": task_id,
        "follow_up_needed": False,
        "follow_up_questions": []
    }

    try:
        finder_graph = build_graph()
        final_state = None

        for ev in finder_graph.stream(initial_state):
            node = list(ev.keys())[0]
            final_state = ev[node]

        print(final_state,'final_state')
        
        # --- SAVE FINDER SESSION TO DATABASE ---
        if user_id:
            try:
                finder_session = create_finder_session(
                    db=db,
                    user_id=user_id,
                    task_id=task_id,
                    raw_input=final_state.get("raw_input", input_text),
                    intent_type=final_state.get("intent_type"),
                    intent_confidence=final_state.get("intent_confidence"),
                    intent_reasoning=final_state.get("intent_reasoning"),
                    product_understanding=final_state.get("product_understanding", {}),
                    icp_profile=final_state.get("icp_profile", {}),
                    personas=final_state.get("personas", []),
                    discovery_queries=final_state.get("discovery_queries", {}),
                    scraped_content=final_state.get("scraped_content"),
                    follow_up_questions=final_state.get("follow_up_questions", [])
                )
                print(f"✅ Saved Finder session to database: {finder_session.id}")
            except Exception as e:
                print(f"⚠️ Failed to save Finder session: {e}")
                traceback.print_exc()


        # If clarification needed → return immediately
        if final_state.get("follow_up_needed"):
            # Update session status
            if finder_session:
                try:
                    update_finder_session_status(db, finder_session, "needs_clarification")
                except Exception as e:
                    print(f"⚠️ Failed to update session status: {e}")
            
            db.close()
            publish_event(task_id, "finder_agent", "needs_input", "clarification",
                          "Need user clarification", {"questions": final_state["follow_up_questions"]})

            return {
                "status": "need_clarification",
                "questions": final_state["follow_up_questions"],
                "execution_time": time.time() - start}

        print(final_state,'final_state')


        # If discovery needed → handoff to Apollo agent
        if final_state.get("route_to_discovery"):
            
            # --- SYNTHESIZE QUERY FOR APOLLO AGENT (LLM-DRIVEN) ---
            # Use an LLM to intelligently synthesize the best query for Apollo
            # based on all the context we've gathered
            
            from langchain_openai import ChatOpenAI
            
            intent_type = final_state.get("intent_type")
            icp = final_state.get("icp_profile", {})
            personas = final_state.get("personas", [])
            pu = final_state.get("product_understanding", {})
            raw_input = final_state.get("raw_input", "")
            
            # Build context for LLM
            context = {
                "original_query": raw_input,
                "detected_intent": intent_type,
                "product_understanding": pu,
                "icp_profile": icp,
                "personas": personas
            }
            
            llm = ChatOpenAI(model="gpt-4o-mini")
            
            # Pre-compute the JSON string to avoid scoping issues in f-string
            context_json = json.dumps(context, indent=2)
            
            publish_event(task_id, "finder_agent", "thinking", "synthesizing_query", 
                          "🤖 Using AI to create the perfect search query...", 
                          {"context": context})
            
            synthesis_prompt = f"""You are a query synthesis expert for the Apollo.io search API.

                    Your task is to create a natural language search query that Apollo can understand and execute effectively.

                    Apollo works best with queries like:
                    - "Find CTOs in fintech companies with 50-200 employees"
                    - "Companies similar to Stripe in financial services"
                    - "Angel Investors and VCs interested in AI startups"
                    - "Senior React developers in San Francisco"

                    Context from analysis:
                    {context_json}

                    Guidelines:
                    1. For SELLING/PRODUCT queries: Focus on finding the RIGHT PEOPLE (titles from personas) at the RIGHT COMPANIES (ICP criteria)
                    2. For INVESTOR queries: Target PEOPLE with investor titles, mention the industry/stage
                    3. For HIRING queries: Focus on PEOPLE with specific skills/titles
                    4. For COMPANY queries (similar/competitor): Target COMPANIES with descriptive criteria
                    5. Keep it concise but specific - include key filters like industry, size, location, funding stage

                    Return ONLY the synthesized query text, nothing else. Make it sound natural.
            """
            
            try:
                response = llm.invoke(synthesis_prompt)
                apollo_query_text = response.content.strip()
                
                # Fallback if LLM returns empty
                if not apollo_query_text or len(apollo_query_text) < 10:
                    apollo_query_text = raw_input
                else:
                    publish_event(task_id, "finder_agent", "thinking", "query_synthesized", 
                                  f"✅ Optimized search: \"{apollo_query_text}\"", 
                                  {"synthesized_query": apollo_query_text})
                    
                    # Save synthesized query to database
                    if finder_session:
                        try:
                            update_finder_session_query(db, finder_session, apollo_query_text)
                        except Exception as e:
                            print(f"⚠️ Failed to update synthesized query: {e}")
                    
            except Exception as e:
                print(f"⚠️ LLM synthesis failed: {e}, using raw input")
                apollo_query_text = raw_input
                publish_event(task_id, "finder_agent", "thinking", "synthesis_fallback", 
                              "⚠️ Using original query for search", {})

            print(f"\n🚀 Handoff to Apollo Agent with Synthesized Query: '{apollo_query_text}'\n")

            publish_event(task_id, "finder_agent", "thinking", "apollo_handoff", 
                          f"🔄 Searching Apollo database for: \"{apollo_query_text}\"", 
                          {"query": apollo_query_text})

            apollo_graph = build_apollo_graph()

            apollo_seed = {
                "query": apollo_query_text, # Pass the synthesized NL query
                "enriched_query": None,
                "intent": {
                    "query": apollo_query_text, 
                    "intent_type": "general_search", 
                    "entity_type": "mixed"
                },
                "discovery_plan": final_state.get("discovery_queries", {}),
                "apollo_query": None,
                "serp_queries": final_state.get("discovery_queries", {}).get("serp", []),
                "apollo_results": [],
                "apollo_summary": None,
                "extracted_filters": {},
                "task_id": task_id,
            }

            apollo_final = None
            for ev in apollo_graph.stream(apollo_seed):
                node = list(ev.keys())[0]
                apollo_final = ev[node]

            results = apollo_final.get("apollo_enriched_results") or apollo_final.get("apollo_results") or []

            # Update session status to completed
            if finder_session:
                try:
                    update_finder_session_status(db, finder_session, "completed")
                except Exception as e:
                    print(f"⚠️ Failed to update session status: {e}")

            publish_event(task_id, "finder_agent", "completed", "done",
                          "Finder Agent + Apollo completed", {"results_count": len(results)})

            db.close()  # Close database connection
            
            return {
                "status": "completed",
                "results": results,
                "results_count": len(results),
                "session_id": str(finder_session.id) if finder_session else None,
                "execution_time": time.time() - start
            }

        # publish_event(task_id, "finder_agent", "completed", "done",
        #               "Finder Agent finished (no discovery)", {})

        db.close()
        return {"status": "ok", "execution_time": time.time() - start}

    except Exception as e:
        traceback.print_exc()
        
        # Update session status to failed
        if finder_session:
            try:
                update_finder_session_status(db, finder_session, "failed")
            except:
                pass
        
        db.close()
        publish_event(task_id, "finder_agent", "error", "failed", str(e))
        raise
