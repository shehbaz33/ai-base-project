# app/agents/finder/nodes.py

import json, re, time
from typing import Dict, Any, List
from pydantic import ValidationError
from langchain_openai import ChatOpenAI
from .models import ProductContext
from app.utils.web_search import scrape_with_web_unlocker, serp_search

LLM_MINI = "gpt-4o-mini"
LLM_FULL = "gpt-4o"

# -------------------------------
# Generic JSON utilities
# -------------------------------

def extract_json(text: str) -> dict:
    if not text: return {}
    m = re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", text)
    if not m: return {}
    try:
        return json.loads(m.group(0))
    except:
        try:
            return json.loads(m.group(0).replace("'", '"'))
        except:
            return {}

def safe_invoke(llm, prompt: str, retry: int = 3) -> str:
    for i in range(retry):
        try:
            r = llm.invoke(prompt)
            return getattr(r, "content", r)
        except:
            time.sleep(2**i)
    return ""

# -------------------------------
# 1. parse_input
# -------------------------------

def parse_input(state: Dict[str, Any]) -> Dict[str, Any]:
    from app.utils.publisher import publish_event
    task_id = state.get("task_id", "unknown")
    
    print("\n--- NODE: parse_input ---")
    publish_event(task_id, "finder_agent", "thinking", "parse_input", 
                  "📝 Analyzing your request...", {})
    
    raw = state.get("input_text") or state.get("query") or ""
    state["raw_input"] = raw.strip()
    print(f"Raw Input: {state['raw_input']}")
    
    context_text = raw
    
    # Check for URL
    url_match = re.search(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', raw)
    print(url_match,'url_match')
    if url_match:
        url = url_match.group()
        publish_event(task_id, "finder_agent", "thinking", "scraping", 
                      f"🌐 Found URL in query, scraping content from {url}...", {"url": url})
        try:
            # Use Web Unlocker for robust scraping
            scraped_data = scrape_with_web_unlocker(url)
            if scraped_data:
                scraped_text = str(scraped_data)[:8000] 
                context_text = f"User Query: {raw}\n\nScraped Content from {url}:\n{scraped_text}"
                state["scraped_content"] = scraped_text
                publish_event(task_id, "finder_agent", "thinking", "scraping_complete", 
                              "✅ Successfully extracted content from website", {})
        except Exception as e:
            print(f"Scraping failed: {e}")
            publish_event(task_id, "finder_agent", "thinking", "scraping_failed", 
                          f"⚠️ Could not scrape URL, using query text instead", {})

    state["product_context"] = ProductContext(
        product_summary=context_text
    ).dict()

    return state

# -------------------------------
# 2. detect_user_intent (AGENTIC)
# -------------------------------

def detect_user_intent(state: Dict[str, Any]) -> Dict[str, Any]:
    print("\n--- NODE: detect_user_intent ---")
    llm = ChatOpenAI(model=LLM_MINI)
    query = state.get("raw_input", "")

    prompt = f"""
You are an **Intent Classification Agent**.  
You ALWAYS return JSON.

Choose EXACTLY one of these intents:
1. "selling_product"
2. "job_search"
3. "hiring"
4. "investor_search"
5. "vendor_search"
6. "partner_search"
7. "competitor_research"
8. "generic_people_search"
9. "generic_company_search"
10. "expert_search"
11. "market_research"
12. "similar_company_search"

Return ONLY:
{{
  "intent": "<one-of-12>",
  "confidence": <0.0-1.0>,
  "reason": "<short explanation>"
}}

User Query:
\"\"\"{query}\"\"\"
"""

    out = safe_invoke(llm, prompt)
    parsed = extract_json(out)

    state["intent_type"] = parsed.get("intent", "generic_people_search")
    state["intent_confidence"] = parsed.get("confidence", 0.5)
    state["intent_reasoning"] = parsed.get("reason", "")

    print(f"Detected Intent: {state['intent_type']}")
    print(f"Confidence: {state['intent_confidence']}")
    print(f"Reasoning: {state['intent_reasoning']}")

    task_id = state.get("task_id", "unknown")
    from app.utils.publisher import publish_event
    publish_event(task_id, "finder_agent", "thinking", "intent_detected", 
                  f"🎯 Detected intent: {state['intent_type']} (confidence: {state['intent_confidence']:.0%})", 
                  {"intent": state['intent_type'], "confidence": state['intent_confidence']})

    return state

# -------------------------------
# 3. clarify_intent_llm (AGENTIC)
# -------------------------------

def clarify_intent_llm(state: Dict[str, Any]) -> Dict[str, Any]:
    print("\n--- NODE: clarify_intent_llm ---")
    llm = ChatOpenAI(model=LLM_MINI)

    query = state.get("raw_input")
    intent = state.get("intent_type")
    confidence = state.get("intent_confidence")

    prompt = f"""
You are a **Clarification Question Agent**.

RULES:
- Ask clarification only if needed.
- If confidence < 0.8 → ask.
- If user query is vague → ask.
- Max 3 questions.
- Small-business friendly language.
- Return ONLY JSON:
{{
  "need_clarification": true/false,
  "questions": ["...", "..."]
}}

User Query: "{query}"
Detected Intent: "{intent}"
Confidence: {confidence}
"""

    out = safe_invoke(llm, prompt)
    parsed = extract_json(out)

    state["follow_up_needed"] = parsed.get("need_clarification", False)
    state["follow_up_questions"] = parsed.get("questions", [])

    print(f"Follow-up Needed: {state['follow_up_needed']}")
    if state["follow_up_needed"]:
        print(f"Questions: {state['follow_up_questions']}")
        task_id = state.get("task_id", "unknown")
        from app.utils.publisher import publish_event
        publish_event(task_id, "finder_agent", "thinking", "clarification_needed", 
                      "❓ Need more information to proceed", 
                      {"questions": state['follow_up_questions']})
    else:
        task_id = state.get("task_id", "unknown")
        from app.utils.publisher import publish_event
        publish_event(task_id, "finder_agent", "thinking", "intent_clear", 
                      "✅ Query is clear, proceeding with analysis", {})

    return state

# -------------------------------
# 4. product_understanding_llm
# -------------------------------

def product_understanding_llm(state: Dict[str, Any]) -> Dict[str, Any]:
    print("\n--- NODE: product_understanding_llm ---")
    task_id = state.get("task_id", "unknown")
    from app.utils.publisher import publish_event
    
    # Run for selling, hiring, competitors, similar companies
    allowed_intents = ["selling_product", "hiring", "competitor_research", "similar_company_search", "market_research"]
    if state["intent_type"] not in allowed_intents:
        state["product_understanding"] = {}
        return state

    publish_event(task_id, "finder_agent", "thinking", "analyzing_entity", 
                  "🔍 Analyzing product/company/service details...", {})
    
    llm = ChatOpenAI(model=LLM_MINI)

    summary = state["product_context"]["product_summary"]

    prompt = f"""
You are an Entity Analyst (Product/Company/Service).
Return ONLY JSON:
{{
 "core_value_prop": "What does this entity do/offer?",
 "pain_points_solved": [],
 "job_to_be_done": [],
 "beneficiaries": ["Who benefits/buys?"],
 "ideal_industries": ["Industries relevant to this entity"],
 "entity_name": "Name of company/product if found"
}}

Context:
\"\"\"{summary}\"\"\"
"""

    out = safe_invoke(llm, prompt)
    parsed = extract_json(out)

    state["product_understanding"] = parsed or {}
    print(f"Product Understanding: {json.dumps(state['product_understanding'], indent=2)}")
    
    entity_name = parsed.get("entity_name", "entity")
    publish_event(task_id, "finder_agent", "thinking", "entity_analyzed", 
                  f"✅ Understood: {entity_name}", 
                  {"entity": parsed.get("entity_name"), "industries": parsed.get("ideal_industries", [])})
    
    return state

# -------------------------------
# 5. icp_generator_llm
# -------------------------------

def icp_generator_llm(state):
    print("\n--- NODE: icp_generator_llm ---")
    task_id = state.get("task_id", "unknown")
    from app.utils.publisher import publish_event
    
    # ICP generation is useful for selling, but also for hiring (finding candidates from similar companies)
    # or competitor research (finding companies targeting same ICP)
    allowed_intents = ["selling_product", "competitor_research", "similar_company_search", "market_research"]
    if state["intent_type"] not in allowed_intents:
        state["icp_profile"] = {}
        return state
    
    publish_event(task_id, "finder_agent", "thinking", "building_icp", 
                  "🎯 Building ideal customer profile...", {})

    llm = ChatOpenAI(model=LLM_FULL)

    pu = state.get("product_understanding", {})

    prompt = f"""
You are an ICP Builder for small businesses.
Return ONLY JSON:
{{
 "industry": "",
 "company_size": "",
 "regions": [],
 "tech_stack_indicators": [],
 "budget_signals": "",
 "value_drivers": []
}}

ProductUnderstanding:
{json.dumps(pu, indent=2)}
"""

    out = safe_invoke(llm, prompt)
    state["icp_profile"] = extract_json(out) or {}
    print(f"ICP Profile: {json.dumps(state['icp_profile'], indent=2)}")
    
    icp = state["icp_profile"]
    publish_event(task_id, "finder_agent", "thinking", "icp_generated", 
                  f"✅ Target: {icp.get('industry', 'companies')} with {icp.get('company_size', 'various sizes')}", 
                  {"icp": icp})
    
    return state

# -------------------------------
# 6. persona_generator_llm
# -------------------------------

def persona_generator_llm(state):
    print("\n--- NODE: persona_generator_llm ---")
    task_id = state.get("task_id", "unknown")
    from app.utils.publisher import publish_event
    
    if state["intent_type"] != "selling_product":
        state["personas"] = []
        return state

    llm = ChatOpenAI(model=LLM_MINI)
    icp = state.get("icp_profile", {})

    prompt = f"""
Generate 2 simple buyer personas in JSON array.
Each persona:
{{
 "persona_name":"",
 "titles":[],
 "responsibilities":[],
 "pain_points":[],
 "kpis":[],
 "where_they_live_online":[],
 "apollo_search_keywords":[]
}}

ICP:
{json.dumps(icp, indent=2)}
"""

    out = safe_invoke(llm, prompt)
    parsed = extract_json(out)

    state["personas"] = parsed if isinstance(parsed, list) else []
    print(f"Generated {len(state['personas'])} Personas")
    
    titles = []
    for p in state["personas"]:
        titles.extend(p.get("titles", [])[:2])
    publish_event(task_id, "finder_agent", "thinking", "personas_generated", 
                  f"✅ Targeting: {', '.join(titles[:4]) if titles else 'decision makers'}", 
                  {"personas": state["personas"]})
    
    return state

# -------------------------------
# 7. discovery_query_generator
# -------------------------------

def discovery_query_generator(state):
    print("\n--- NODE: discovery_query_generator ---")
    task_id = state.get("task_id", "unknown")
    from app.utils.publisher import publish_event
    
    publish_event(task_id, "finder_agent", "thinking", "planning_search", 
                  "🗺️ Planning search strategy...", {})
    
    intent = state["intent_type"]
    raw = state["raw_input"]
    icp = state.get("icp_profile", {})
    personas = state.get("personas", [])

    # Core query object your Apollo agent expects
    discovery_plan = {
        "apollo": {
            "tier_1": {"filters": {}, "rationale": ""},
            "tier_2": {"filters": {}, "rationale": ""},
            "tier_3": {"filters": {}, "rationale": ""}
        },
        "people": [],
        "serp": [raw],
        "seed_companies": []
    }

    # SELLING PRODUCT → ICP → Personas
    if intent == "selling_product":
        discovery_plan["apollo"]["tier_1"]["filters"] = icp
        discovery_plan["apollo"]["tier_1"]["rationale"] = "ICP strict"
        discovery_plan["apollo"]["tier_2"]["filters"] = icp
        discovery_plan["apollo"]["tier_2"]["rationale"] = "ICP moderate"
        discovery_plan["apollo"]["tier_3"]["filters"] = {"q_keywords": [raw]}
        discovery_plan["apollo"]["tier_3"]["rationale"] = "Broad keyword"

        for p in personas:
            discovery_plan["people"].append({"titles": p.get("titles", [])})

    # GENERIC PEOPLE / JOB SEARCH / HIRING / EXPERTS
    elif intent in ["generic_people_search", "job_search", "hiring", "expert_search"]:
        discovery_plan["apollo"]["tier_1"]["filters"] = {"q_keywords": [raw]}
        discovery_plan["apollo"]["tier_1"]["rationale"] = "People search"

        discovery_plan["people"].append({"titles": []})  # LLM will parse internally in Apollo agent

    # INVESTORS
    elif intent == "investor_search":
        discovery_plan["apollo"]["tier_1"]["filters"] = {"person_titles": ["Investor", "Partner", "VC"]}
        discovery_plan["apollo"]["tier_1"]["rationale"] = "Strict investor search"

    # VENDOR / PARTNER / COMPETITORS / COMPANIES
    # VENDOR / PARTNER / COMPETITORS / COMPANIES
    else:
        # Check if we have an entity name from product understanding
        pu = state.get("product_understanding", {})
        entity_name = pu.get("entity_name")
        
        if intent == "similar_company_search" and entity_name:
             discovery_plan["apollo"]["tier_1"]["filters"] = {"q_organization_keywords": [entity_name]} # Apollo might not have direct "similar" filter exposed here, so we use keywords or rely on downstream agent to interpret "similar to X"
             discovery_plan["apollo"]["tier_1"]["rationale"] = f"Companies similar to {entity_name}"
             discovery_plan["serp"].append(f"companies similar to {entity_name}")
             discovery_plan["serp"].append(f"competitors of {entity_name}")
        else:
            discovery_plan["apollo"]["tier_1"]["filters"] = {"q_organization_keywords": [raw]}
            discovery_plan["apollo"]["tier_1"]["rationale"] = f"{intent} keyword search"
            


    state["discovery_queries"] = discovery_plan
    print(f"Discovery Plan: {json.dumps(discovery_plan, indent=2)}")
    
    publish_event(task_id, "finder_agent", "thinking", "search_plan_ready", 
                  "✅ Search strategy prepared, ready to find matches", 
                  {"plan": discovery_plan})
    
    return state

# -------------------------------
# 8. icp_router
# -------------------------------

def icp_router(state):
    print("\n--- NODE: icp_router ---")
    if state.get("follow_up_needed"):
        state["route_to_discovery"] = False
        return state

    state["route_to_discovery"] = True
    print("Routing to Discovery -> YES")
    return state
