# app/agents/apollo/nodes.py
from typing import Optional, Dict, Any, List, Literal, TypedDict
from pydantic import BaseModel, Field, ValidationError
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
import json, re, os, requests
import time
from urllib.parse import urlencode, quote
import urllib.parse

load_dotenv()

# =======================================================
# 0️⃣ CONSTANTS
# =======================================================

LLM_MINI = "gpt-4o-mini"
LLM_FULL = "gpt-4o"
MAX_APOLLO_RESULTS = 10
APOLLO_API_URL = "https://api.apollo.io/v1/mixed_people/search"
APOLLO_COMPANY_API_URL = "https://api.apollo.io/v1/mixed_companies/search"

# =======================================================
# 1️⃣ DATA MODELS (Pydantic for validation & structured output)
# =======================================================

class Filters(BaseModel):
    location: Optional[str] = None
    role: Optional[str] = None
    expertise: Optional[str] = None
    industry: Optional[str] = None
    investment_stage: Optional[str] = None
    check_size: Optional[str] = None
    company_type: Optional[str] = None
    nationality: Optional[str] = None
    age_range: Optional[str] = None
    gender: Optional[str] = None
    profession: Optional[str] = None
    business_function: Optional[str] = None

class ApolloTier(BaseModel):
    filters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Apollo People Search filters for this tier."
    )
    rationale: Optional[str] = Field(
        default=None,
        description="Reasoning for this tier’s configuration."
    )

    class Config:
        extra = "forbid"
        json_schema_extra = {"additionalProperties": False}


class ApolloQueryPlan(BaseModel):
    tier_1: ApolloTier = Field(..., description="Strict filters.")
    tier_2: ApolloTier = Field(..., description="Moderately relaxed filters.")
    tier_3: ApolloTier = Field(..., description="Broad, minimal filters.")

    class Config:
        extra = "forbid"
        json_schema_extra = {"additionalProperties": False}

# =======================================================
# 1️⃣ DATA MODELS (Apollo-Native Filter Schema)
# =======================================================

class ExtractedApolloFilters(BaseModel):
    person_titles: List[str] = Field(default_factory=list, description="Extracted job titles or roles.")
    person_locations: List[str] = Field(default_factory=list, description="Extracted geographic locations.")
    q_organization_keywords: List[str] = Field(default_factory=list, description="Extracted keywords describing company domain (e.g. AI, Renewable Energy).")
    organization_industries: List[str] = Field(default_factory=list, description="Extracted industry verticals (e.g., Renewables & Environment).")
    organization_funding_stages: List[str] = Field(default_factory=list, description="Extracted funding stages (e.g., Series A, Seed).")
    organization_num_employees_ranges: List[str] = Field(default_factory=list, description="Company size filters like 1-10, 11-50, 51-200.")
    q_keywords: List[str] = Field(default_factory=list, description="Extra search context such as check size, early stage, etc.")



class Intent(BaseModel):
    query: str
    intent_type: Literal[
        "investor_search",
        "talent_search",
        "company_search",
        "partner_search",
        "customer_search",
        "general_search"
    ]
    entity_type: Literal[
        "person",
        "company",
        "organization",
        "ngo",
        "fund",
        "mixed",
        "unknown"
    ]
    filters: Filters = Field(default_factory=Filters)


class Output(BaseModel):
    intent: Intent
    reasoning: str
    followup_needed: bool
    followup_question: Optional[str] = None


# State must remain a TypedDict for langgraph, but keys hold Pydantic models
class State(TypedDict):
    query: str
    enriched_query: Optional[str]
    intent: Intent
    discovery_plan: Dict[str, Any]
    apollo_query: Optional[str]
    serp_queries: List[str]
    apollo_results: Optional[List[Dict[str, Any]]]
    apollo_summary: Optional[str]
    extracted_filters: Optional[ExtractedApolloFilters]
    apollo_query_plan: Optional[ApolloQueryPlan]
    apollo_enriched_results: Optional[List[Dict[str, Any]]]
    apollo_enriched_companies: Optional[List[Dict[str, Any]]]

class NormalizedLocations(BaseModel):
    person_locations: List[str]

class NormalizedEmployeeRanges(BaseModel):
    organization_num_employees_ranges: List[str] = Field(
        default_factory=list,
        description="Normalized Apollo-compatible employee ranges ('min,max')"
    )

# =======================================================
# HELPERS
# =======================================================

def extract_json(text: str) -> dict:
    """Safely extract JSON object from LLM output (for non-Pydantic calls)."""
    if not text:
        return {}
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        print("⚠️ No JSON block found.")
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        try:
            fixed_text = match.group(0).replace("'", '"')
            return json.loads(fixed_text)
        except json.JSONDecodeError as e2:
            print(f"⚠️ Failed to parse JSON (1: {e}, 2: {e2}).")
            return {}

def safe_invoke(llm: ChatOpenAI, prompt: str, max_retries: int = 3) -> str:
    """Call LLM and return raw content with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            r = llm.invoke(prompt)
            return getattr(r, "content", r)
        except Exception as e:
            if attempt < max_retries - 1:
                delay = 2 ** attempt
                print(f"⚠️ LLM invoke failed ({e}). Retrying in {delay}s...")
                time.sleep(delay)
            else:
                print(f"❌ LLM invoke failed after {max_retries} attempts.")
                return ""
    return ""

def generate_serp_queries(discovery_plan: Dict[str, Any]) -> List[str]:
    """Generates specific, site-prefixed SERP queries from the discovery plan."""
    serp_queries = []
    q_source_map = {
        "linkedin": "site:linkedin.com/in",
        "crunchbase": "site:crunchbase.com",
        "pitchbook": "site:pitchbook.com",
        "angel": "site:angel.co",
    }
    for tier, entries in discovery_plan.items():
        if not isinstance(entries, list): continue
        for e in entries:
            q = e.get("query", "")
            src = e.get("source", "").lower()
            if not q or not src:
                continue
            matched = False
            for key, prefix in q_source_map.items():
                if key in src:
                    serp_queries.append(f"{prefix} {q}")
                    matched = True
                    break
            if not matched and "google" not in src and "bing" not in src:
                clean_src = src.replace(" ", "").split(".")[0]
                serp_queries.append(f"{q} site:{clean_src}.com")
            if "google" in src or "bing" in src:
                serp_queries.append(q)
    return list(dict.fromkeys([s.strip() for s in serp_queries if s.strip()]))

def merge_list(*items):
    out = []
    for it in items:
        if not it:
            continue
        if isinstance(it, list):
            out.extend([x for x in it if x])
        else:
            out.append(it)
    return list(dict.fromkeys([str(x).strip() for x in out if x]))

# =======================================================
# 2️⃣ INTENT ANALYZER
# =======================================================

def analyze_intent(state: State) -> State:
    llm = ChatOpenAI(model=LLM_MINI).with_structured_output(Output)
    prompt = """
    You are an intent analyzer for an entity discovery system.
    Identify:
      - intent_type (why user is searching)
      - entity_type (what is being searched)
      - filters (where / what characteristics)
    If unclear, set followup_needed=True and provide a clarifying question.
    """
    result = llm.invoke(f"{prompt}\n\nQuery: {state['query']}")
    state["intent"] = result.intent
    return state 

# =======================================================
# 2.5️⃣ QUERY ENRICHER
# =======================================================

def query_enricher(state: State) -> State:
    llm = ChatOpenAI(model=LLM_MINI)
    raw_query = state["query"]
    prompt = f"""
    You are a query enhancer for search systems. Expand and normalize the user's query
    to make it explicit and search-optimized. Expand shorthand (e.g., 'Series A' -> 'Series A funding'),
    normalize currencies (e.g., '$1-5M' -> 'between 1 million and 5 million USD'), and add common synonyms.

    Return the enriched single-line query string only.

    Input: "{raw_query}"
    """
    enriched = safe_invoke(llm, prompt).strip()
    if not enriched:
        enriched = raw_query
    state["enriched_query"] = enriched
    return state

# =======================================================
# 3️⃣ AUTONOMOUS DISCOVERY PLANNER
# =======================================================

def autonomous_discovery_planner(state: State) -> State:
    intent = state["intent"]
    llm = ChatOpenAI(model=LLM_FULL)
    q = state.get("enriched_query") or intent.query

    planning_prompt = f"""
    You are an expert research strategist creating an online discovery plan.

    Given this search intent:
    ---
    Query: {q}
    Intent Type: {intent.intent_type}
    Entity Type: {intent.entity_type}
    Filters: {json.dumps(intent.filters.dict(exclude_none=True))}
    ---

    Think carefully about where such entities can be found online (e.g., Apollo.io, LinkedIn, Crunchbase, Google, Pitchbook).
    Return a pure JSON object (no prose) describing three tiers of discovery with `source`, `rationale`, and `query`.
    """
    raw = safe_invoke(llm, planning_prompt)
    plan = extract_json(raw)
    if not plan or not plan.get("tier_1"):
        plan = {
            "tier_1": [{"source": "Apollo.io", "rationale": "B2B contact database", "query": q}],
            "tier_2": [{"source": "LinkedIn", "rationale": "Professional network", "query": q}],
            "tier_3": [{"source": "Google", "rationale": "General fallback search", "query": q}],
        }
    state["discovery_plan"] = plan
    return state

# =======================================================
# 4️⃣ RULE-BASED APOLLO DECISIONER (NEW & OPTIMIZED)
# =======================================================

def should_use_apollo_rule(state: State) -> bool:
    """Always use Apollo"""
    return True

def apollo_people_query_planner_llm(state: State) -> State:
    llm = ChatOpenAI(model=LLM_FULL)
    extracted = state.get("extracted_filters") or ExtractedApolloFilters()

    prompt = f"""
    You are an expert at diagnosing overly strict search filters for Apollo.io.

    Given these extracted filters:
    {json.dumps(extracted.dict(exclude_none=True), indent=2)}

    Apollo searches can fail if filters are too restrictive.
    Create 3 tiers of search configurations:
    - tier_1: strict, all filters included
    - tier_2: moderately relaxed (drop strict filters like funding stage, industry)
    - tier_3: broad (keep only core role + location + domain keyword)

    Return pure JSON only (no extra text) with this format:
    {{
      "tier_1": {{
         "filters": {{ ... }},
         "rationale": "..."
      }},
      "tier_2": {{
         "filters": {{ ... }},
         "rationale": "..."
      }},
      "tier_3": {{
         "filters": {{ ... }},
         "rationale": "..."
      }}
    }}
    """
    raw = safe_invoke(llm, prompt)
    plan = extract_json(raw)

    if not plan or not isinstance(plan, dict):
        print("⚠️ Apollo planner returned invalid JSON, using fallback plan.")
        plan = {
            "tier_1": {"filters": extracted.dict(), "rationale": "Default strict filters"},
            "tier_2": {"filters": {}, "rationale": "Relaxed filters (fallback)"},
            "tier_3": {"filters": {}, "rationale": "Broad filters (fallback)"}
        }

    state["apollo_query_plan"] = plan
    print(f"🧠 Generated Apollo Query Plan:\n{json.dumps(plan, indent=2)}")
    return state

# =======================================================
# 5️⃣ LLM-BASED APOLLO QUERY BUILDER
# =======================================================

def build_apollo_query_llm(intent: Intent, enriched_query: Optional[str] = None) -> str:
    llm = ChatOpenAI(model=LLM_MINI)
    q = enriched_query or intent.query
    prompt = f"""
    You are an Apollo.io search query builder.

    Convert this intent and query into an Apollo-optimized boolean query string using fields like:
    - title, location, industry_keywords (only use keywords derived from the query, NOT filters which are handled separately).

    Input Query: "{q}"
    Filters (for context only): {json.dumps(intent.filters.dict(exclude_none=True), indent=2)}

    Return only the boolean query string (e.g. '(title:Investor OR title:Partner) AND (industry_keywords:"Renewable Energy")')
    """
    raw = safe_invoke(llm, prompt).strip()
    if not raw:
        raw = q
    return raw

def build_apollo_query_url(base_url: str, filters: dict) -> str:
    parts = []
    for key, value in filters.items():
        if isinstance(value, list):
            for v in value:
                encoded_value = urllib.parse.quote(str(v))
                parts.append(f"{key}={encoded_value}")
        else:
            encoded_value = urllib.parse.quote(str(value))
            parts.append(f"{key}={encoded_value}")
    return f"{base_url}?" + "&".join(parts)

def apollo_company_query_planner_llm(state: dict) -> dict:
    llm_full = ChatOpenAI(model=LLM_FULL)
    llm_mini = ChatOpenAI(model=LLM_MINI)
    extracted = state.get("extracted_filters") or ExtractedApolloFilters()
    query = state.get("enriched_query") or state["query"]

    prompt = f"""
    You are an Apollo.io company search planner.

    Generate a **3-tier plan** for the endpoint `/api/v1/mixed_companies/search`.

    Use only these official parameters:
      - organization_num_employees_ranges[]
      - organization_locations[]
      - organization_not_locations[]
      - revenue_range[min], revenue_range[max]
      - currently_using_any_of_technology_uids[]
      - q_organization_keyword_tags[]
      - q_organization_name
      - organization_ids[]
      - latest_funding_amount_range[min], latest_funding_amount_range[max]
      - total_funding_range[min], total_funding_range[max]
      - latest_funding_date_range[min], latest_funding_date_range[max]
      - q_organization_job_titles[]
      - organization_job_locations[]
      - organization_num_jobs_range[min], organization_num_jobs_range[max]
      - organization_job_posted_at_range[min], organization_job_posted_at_range[max]
      - page, per_page

    Rules:
    - Tier 1: strict (use all filters)
    - Tier 2: drop numeric/date filters
    - Tier 3: keep only tags + locations
    - Return valid JSON only (no prose).

    Enriched Query: "{query}"
    Extracted Context:
    {json.dumps(extracted.dict(exclude_none=True), indent=2)}
    """
    raw = safe_invoke(llm_full, prompt)
    plan = extract_json(raw)

    if not isinstance(plan, dict) or not all(k in plan for k in ["tier_1", "tier_2", "tier_3"]):
        print("⚠️ Invalid Apollo plan from LLM — using fallback.")
        plan = {
            "tier_1": {"filters": extracted.dict(exclude_none=True), "rationale": "Default strict filters"},
            "tier_2": {"filters": {}, "rationale": "Relaxed fallback filters"},
            "tier_3": {"filters": {}, "rationale": "Broad fallback filters"}
        }

    def normalize_employee_ranges_llm(values: list) -> list:
        if not values:
            return []
        prompt = f"""
        Normalize these employee range descriptions into Apollo format ('min,max').
        Rules:
        - '11 to 50 employees' → '11,50'
        - 'less than 100' → '1,100'
        - 'more than 500' or '500+' → '500,10000'
        - 'about 200' → '200,200'
        - Always return a JSON list of strings.
        Input: {json.dumps(values, indent=2)}
        Example Output: ["1,10","11,50","1,100","500,10000","200,200"]
        """
        raw = safe_invoke(llm_mini, prompt)
        parsed = extract_json(raw)
        print(parsed,'parsed')
        if isinstance(parsed, list):
            return [str(v).strip() for v in parsed if v]
        print("⚠️ LLM normalization failed, skipping employee normalization.")
        return values

    def build_apollo_company_url(base_url: str, filters: dict) -> str:
        parts = []
        for key, val in filters.items():
            if not val:
                continue
            if isinstance(val, list):
                if key == "organization_num_employees_ranges":
                    val = normalize_employee_ranges_llm(val)
                for v in val:
                    safe_val = urllib.parse.quote(str(v), safe=",[]")
                    parts.append(f"{key}[]={safe_val}")
            else:
                safe_val = urllib.parse.quote(str(val), safe=",[]")
                parts.append(f"{key}={safe_val}")
        return f"{base_url}?" + "&".join(parts)

    base_url = "https://api.apollo.io/api/v1/mixed_companies/search"
    for tier, tier_data in plan.items():
        filters = tier_data.get("filters", {})
        plan[tier]["query_url"] = build_apollo_company_url(base_url, filters)

    state["apollo_query_plan"] = plan
    print("\n🏢 Generated Apollo COMPANY Query Plan:")
    print(json.dumps(plan, indent=2))
    return state

# =======================================================
# 6️⃣ LLM-BASED APOLLO FILTER EXTRACTOR (Enhanced for Apollo Fields)
# =======================================================

def apollo_filter_extractor(state: State) -> State:
    llm = ChatOpenAI(model=LLM_MINI).with_structured_output(ExtractedApolloFilters)
    intent = state["intent"]
    q = state.get("enriched_query") or state["query"]

    prompt = f"""
    You are an expert at constructing structured filters for the Apollo.io People Search API.

    Given the user's search query and intent, extract the relevant Apollo-compatible filters.
    Output must be a valid JSON object strictly following this schema:
    {{
      "person_titles": [],
      "person_locations": [],
      "q_organization_keywords": [],
      "organization_industries": [],
      "organization_funding_stages": [],
      "organization_num_employees_ranges": [],
      "q_keywords": []
    }}

    Use these mappings:
    - person_titles → job titles like "Founder", "CEO", "Investor", "Venture Partner"
    - person_locations → city, region, or country (e.g. "New York, United States", "Europe")
    - q_organization_keywords → company domain focus or keywords (e.g. "Artificial Intelligence", "Renewable Energy")
    - organization_industries → Apollo industries (e.g. "Information Technology", "Renewables & Environment")
    - organization_funding_stages → funding stage filters (e.g. "Seed", "Series A", "Series B")
    - organization_num_employees_ranges → company size categories for startups (["1-10", "11-50", "51-200"])
    - q_keywords → contextual keywords like "early stage", "$1-5M", "Seed to Series A"

    Input:
    Query: "{q}"
    Existing Filters: {json.dumps(intent.filters.dict(exclude_none=True), indent=2)}

    Return JSON only (no text or commentary).
    """

    try:
        extracted = llm.invoke(prompt)
        state["extracted_filters"] = extracted
    except ValidationError as e:
        print(f"❌ Pydantic validation error in Apollo filter extraction: {e}")
        state["extracted_filters"] = ExtractedApolloFilters()

    return state

def build_apollo_query_params(state: State) -> str:
    extracted: ExtractedApolloFilters = state.get("extracted_filters") or ExtractedApolloFilters()
    params = []

    valid_keys = {
        "person_titles",
        "include_similar_titles",
        "person_locations",
        "person_seniorities",
        "organization_locations",
        "q_organization_domains_list",
        "contact_email_status",
        "organization_ids",
        "organization_num_employees_ranges",
        "q_keywords",
        "q_organization_keywords",
        "q_organization_job_titles",
        "organization_job_locations",
        "organization_num_jobs_range[min]",
        "organization_num_jobs_range[max]",
        "organization_job_posted_at_range[min]",
        "organization_job_posted_at_range[max]"
    }

    def add_param(key: str, values: Any):
        if not values or key not in valid_keys:
            return
        if isinstance(values, list):
            for v in values:
                if not v:
                    continue
                v = str(v).strip()
                if key == "organization_num_employees_ranges":
                    v = v.replace("-", ",").replace(" ", "")
                params.append((f"{key}[]", v))
        else:
            v = str(values).strip()
            if v:
                params.append((key, v))

    add_param("person_titles", extracted.person_titles)
    add_param("person_locations", extracted.person_locations)
    add_param("q_organization_keywords", extracted.q_organization_keywords)
    add_param("organization_num_employees_ranges", extracted.organization_num_employees_ranges)
    add_param("q_keywords", extracted.q_keywords)

    add_param("include_similar_titles", True)
    add_param("person_seniorities", getattr(extracted, "person_seniorities", []))
    add_param("organization_locations", getattr(extracted, "organization_locations", []))
    add_param("contact_email_status", ["verified"])

    params.append(("page", "1"))
    params.append(("per_page", "25"))

    query_str = urlencode(params, doseq=True, quote_via=quote)
    return query_str

def apollo_people_search(state: State) -> State:
    apollo_api_key = os.getenv("APOLLO_API_KEY")
    if not apollo_api_key:
        print("⚠️ Apollo API key not found.")
        state["apollo_results"] = []
        return state

    headers = {
        "x-api-key": apollo_api_key,
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "accept": "application/json"
    }

    all_people = []
    query_plan = state.get("apollo_query_plan") or {}

    VALID_APOLLO_KEYS = {
        "person_titles",
        "person_locations",
        "q_organization_keywords",
        "organization_num_employees_ranges",
        "q_keywords",
    }

    def build_query(filters: Dict[str, Any]) -> str:
        params = []
        for key, values in filters.items():
            if key not in VALID_APOLLO_KEYS:
                print(f"⚠️ Skipping invalid Apollo field: {key}")
                continue
            if not values:
                continue
            if isinstance(values, list):
                for v in values:
                    params.append((f"{key}[]", v))
            else:
                params.append((key, str(values)))
        params.append(("page", "1"))
        params.append(("per_page", "10"))
        return urlencode(params, doseq=True, quote_via=quote)

    for tier_name in ["tier_1", "tier_2", "tier_3"]:
        tier_data = query_plan.get(tier_name)
        if not tier_data:
            continue
        filters = tier_data.get("filters", tier_data)
        query_str = build_query(filters)
        url = f"{APOLLO_API_URL}?{query_str}"

        print(f"\n📡 Trying Apollo {tier_name.upper()} Query:\n{url}\n")

        try:
            response = requests.post(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            people = data.get("people") or data.get("results") or []

            if people:
                print(f"✅ {len(people)} results found in {tier_name}.")
                all_people = people[:MAX_APOLLO_RESULTS]
                state["apollo_query_url"] = url
                break
            else:
                print(f"⚠️ No results in {tier_name}, moving to next tier...")

        except Exception as e:
            print(f"❌ Apollo {tier_name} failed: {e}")
            continue

    if not all_people:
        print("⚠️ All tiers failed to return results.")

    state["apollo_results"] = all_people
    return state

def apollo_search_type_router(state: State) -> str:
    intent = state.get("intent")
    entity_type = getattr(intent, "entity_type", None)

    if not entity_type:
        print("⚠️ No entity type detected — defaulting to SERP fallback.")
        return "fallback_serp_node"

    entity_type = entity_type.lower().strip()

    if entity_type in ["person", "individual", "talent"]:
        print("🧭 Routing → Apollo PEOPLE search flow")
        return "apollo_people_search"

    elif entity_type in ["company", "organization", "fund", "startup", "business"]:
        print("🧭 Routing → Apollo COMPANY search flow")
        return "apollo_company_search"

    else:
        print(f"⚠️ Entity type '{entity_type}' not recognized → fallback to SERP")
        return "fallback_serp_node"

def normalize_employee_ranges_llm(values: List[str]) -> List[str]:
    if not values:
        return []

    llm = ChatOpenAI(model=LLM_MINI).with_structured_output(NormalizedEmployeeRanges)

    print(json.dumps(values, indent=2),'json.dumps(values, indent=2)')

    prompt = f"""
    You are a normalization engine for Apollo.io filters.

    Convert each phrase describing company size or employee count into a numeric range string.
    Use the Apollo.io format 'min,max'.

    Rules:
    - "1-10 employees" → "1,10"
    - "11 to 50 people" → "11,50"
    - "less than 100" or "under 100" → "1,100"
    - "more than 500" or "500+" → "500,10000"
    - "about 200" → "200,200"
    - "mid-sized company" → "51,200"
    - "large enterprise" → "1000,10000"
    - Always output JSON following this schema:
      {{
        "organization_num_employees_ranges": ["min,max", ...]
      }}

    Input employee descriptions:
    {json.dumps(values, indent=2)}
    """

    try:
        result = llm.invoke(prompt)
        print(result,'result')
        print(f"✅ LLM Normalized Employee Ranges → {result.organization_num_employees_ranges}")
        return result.organization_num_employees_ranges
    except Exception as e:
        print(f"⚠️ LLM normalization failed: {e}")
        return values

def apollo_company_search(state: State) -> State:
    apollo_api_key = os.getenv("APOLLO_API_KEY")
    if not apollo_api_key:
        print("⚠️ Apollo API key not found.")
        state["apollo_results"] = []
        return state

    headers = {
        "x-api-key": apollo_api_key,
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "accept": "application/json"
    }

    all_companies = []
    query_plan = state.get("apollo_query_plan") or {}

    print(query_plan,'query_plan')

    VALID_COMPANY_KEYS = {
        "organization_num_employees_ranges",
        "organization_locations",
        "organization_not_locations",
        "organization_funding_stages",
        "organization_ids",
        "q_organization_keywords",
        "q_organization_keyword_tags",
        "q_organization_name",
        "revenue_range[min]",
        "revenue_range[max]",
        "latest_funding_amount_range[min]",
        "latest_funding_amount_range[max]",
        "total_funding_range[min]",
        "total_funding_range[max]",
        "latest_funding_date_range[min]",
        "latest_funding_date_range[max]",
        "q_organization_job_titles",
        "organization_job_locations",
        "organization_num_jobs_range[min]",
        "organization_num_jobs_range[max]",
        "organization_job_posted_at_range[min]",
        "organization_job_posted_at_range[max]",
        "currently_using_any_of_technology_uids",
        "page",
        "per_page",
    }

    def build_query(filters: Dict[str, Any]) -> str:
        params = []
        for key, values in (filters or {}).items():
            if key not in VALID_COMPANY_KEYS:
                print(f"⚠️ Skipping invalid field: {key}")
                continue
            if not values:
                continue

            if isinstance(values, list):
                if key == "organization_num_employees_ranges":
                    values = normalize_employee_ranges_llm(values)
                for v in values:
                    params.append((f"{key}[]", str(v).strip()))
            else:
                params.append((key, str(values).strip()))

        params.append(("page", "1"))
        params.append(("per_page", "10"))
        return urlencode(params, doseq=True, quote_via=quote)

    for tier_name in ["tier_1", "tier_2", "tier_3"]:
        tier_data = query_plan.get(tier_name)
        if not tier_data:
            continue
        filters = tier_data.get("filters", tier_data)
        query_str = build_query(filters)
        url = f"{APOLLO_COMPANY_API_URL}?{query_str}"

        print(f"\n📡 Trying Apollo COMPANY {tier_name.upper()} Query:\n{url}\n")

        try:
            response = requests.post(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            companies = data.get("organizations") or data.get("results") or []
            if companies:
                print(f"✅ {len(companies)} companies found in {tier_name}.")
                all_companies = companies[:MAX_APOLLO_RESULTS]
                state["apollo_query_url"] = url
                break
            else:
                print(f"⚠️ No companies in {tier_name}, moving to next tier...")
        except Exception as e:
            print(f"❌ Apollo COMPANY {tier_name} failed: {e}")
            continue

    if not all_companies:
        print("⚠️ All company tiers failed to return results.")
    state["apollo_results"] = all_companies
    return state

def normalize_apollo_locations(state: State) -> State:
    extracted: ExtractedApolloFilters = state.get("extracted_filters") or ExtractedApolloFilters()

    if not extracted.person_locations:
        return state

    llm = ChatOpenAI(model=LLM_MINI).with_structured_output(NormalizedLocations)

    prompt = f"""
    You are a location normalization expert for Apollo.io People Search API.

    Apollo only supports real countries or cities — not regions like "Europe" or "APAC".
    Expand or replace any vague region names with valid countries.

    Guidelines:
    - Return a JSON object matching this schema: {{ "person_locations": [list of valid names] }}
    - Do not include regions like "Europe", "APAC", "DACH" etc.
    - Examples:
        Input: ["Europe", "APAC", "London"]
        Output:
        {{
          "person_locations": [
            "United Kingdom", "Germany", "France", "Netherlands", "Spain", "Italy",
            "India", "Singapore", "Australia", "Japan",
            "London"
          ]
        }}

    Input locations: {json.dumps(extracted.person_locations, indent=2)}
    """

    try:
        result = llm.invoke(prompt)
        extracted.person_locations = result.person_locations
        state["extracted_filters"] = extracted
        print(f"✅ Normalized Locations → {extracted.person_locations}")
    except Exception as e:
        print(f"⚠️ LLM normalization failed ({e}) — keeping originals.")
        state["extracted_filters"] = extracted

    return state

# =======================================================
# 8️⃣ SUMMARIZE APOLLO RESULTS
# =======================================================

def summarize_apollo_results(state: State) -> State:
    people = state.get("apollo_results", []) or []
    if not people:
        state["apollo_summary"] = None
        return state

    llm = ChatOpenAI(model=LLM_MINI)
    pruned_data = [
        {
            "name": p.get("name"),
            "title": p.get("title"),
            "company": p.get("organization_name"),
            "location": p.get("city")
        } for p in people[:25]
    ]

    prompt = f"""
    Summarize these Apollo search results as short insights. Provide:
    - Top locations (by count)
    - Top titles (by count)
    - Top organizations
    - Quick one-line actionable summary

    Data (first 25 entries):
    {json.dumps(pruned_data, indent=2)}
    """
    summary = safe_invoke(llm, prompt).strip()
    state["apollo_summary"] = summary
    return state

def apollo_planner_router(state: State) -> str:
    intent = state.get("intent")
    entity_type = getattr(intent, "entity_type", None)
    if not entity_type:
        return "apollo_people_query_planner_llm"

    entity_type = entity_type.lower().strip()
    if entity_type in ["company", "organization", "fund", "startup", "business"]:
        print("🧭 Routing → Apollo COMPANY Query Planner")
        return "apollo_company_query_planner_llm"
    else:
        print("🧭 Routing → Apollo PEOPLE Query Planner")
        return "apollo_people_query_planner_llm"

# =======================================================
# 9️⃣ FALLBACK/ADDITIONAL SERP NODE
# =======================================================

def fallback_serp_node(state: State) -> State:
    plan = state.get("discovery_plan", {})
    state["serp_queries"] = generate_serp_queries(plan)
    return state

# =======================================================
# 10️⃣ PLANNER PIPELINE (Combined decision and query building)
# =======================================================

def planner_pipeline(state: State) -> State:
    use_apollo = should_use_apollo_rule(state)

    if use_apollo:
        apollo_q = build_apollo_query_llm(state["intent"], state.get("enriched_query"))
        state["apollo_query"] = apollo_q
    else:
        state["apollo_query"] = None

    return state

def apollo_router(state: State) -> str:
    if should_use_apollo_rule(state):
        return "apollo_filter_extractor"
    return "fallback_serp_node"

def apollo_post_process_router(state: State) -> str:
    people = state.get("apollo_results") or []
    if len(people) > 0:
        return "summarize_apollo_results"
    return "fallback_serp_node"

def apollo_enrich_by_id(person_id: str,
                        reveal_personal_emails: bool = False,
                        reveal_phone_number: bool = False,
                        webhook_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
    apollo_api_key = os.getenv("APOLLO_API_KEY")
    if not apollo_api_key:
        print("⚠️ Apollo API key not found.")
        return None

    base_url = "https://api.apollo.io/api/v1/people/match"

    params = {
        "id": person_id,
        "reveal_personal_emails": str(reveal_personal_emails).lower(),
        "reveal_phone_number": str(reveal_phone_number).lower(),
    }

    if reveal_phone_number and webhook_url:
        params["webhook_url"] = webhook_url

    params = {k: v for k, v in params.items() if v}

    url = f"{base_url}?{urlencode(params, quote_via=quote)}"

    headers = {
        "x-api-key": apollo_api_key,
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "accept": "application/json"
    }

    print(f"\n🔍 Enriching Apollo Person ID: {person_id}\n{url}\n")

    try:
        response = requests.post(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        person = data.get("person")
        if person:
            print(f"✅ Enriched: {person.get('name')} — {person.get('organization_name')}")
            return person
        else:
            print("⚠️ No enrichment match found.")
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ Apollo enrichment failed for ID {person_id}: {e}")
        return None

def apollo_enrich_company(domain: str) -> Optional[Dict[str, Any]]:
    import urllib.parse
    import requests
    import os
    import json

    apollo_api_key = os.getenv("APOLLO_API_KEY")
    if not apollo_api_key:
        print("⚠️ Apollo API key not found.")
        return None

    if not domain:
        print("⚠️ Domain is required for company enrichment.")
        return None

    domain = (
        domain.replace("http://", "")
        .replace("https://", "")
        .replace("www.", "")
        .strip()
        .split("/")[0]
    )

    base_url = "https://api.apollo.io/api/v1/organizations/enrich"
    url = f"{base_url}?domain={urllib.parse.quote(domain)}"

    headers = {
        "x-api-key": apollo_api_key,
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "accept": "application/json"
    }

    print(f"\n🏢 Enriching company domain: {domain}\n{url}\n")

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        company = data.get("organization")

        if company:
            print(f"✅ Enriched company: {company.get('name')} ({company.get('website_url')})")
            return company
        else:
            print("⚠️ No enrichment data found for this company.")
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ Apollo company enrichment failed for {domain}: {e}")
        return None

def enrich_all_apollo_people(state: State) -> State:
    people = state.get("apollo_results") or []
    if not people:
        print("⚠️ No Apollo people to enrich.")
        state["apollo_enriched_results"] = []
        return state

    enriched = []
    print(f"\n⚙️ Starting enrichment for {len(people)} people...")

    for i, person in enumerate(people[:5]):
        person_id = person.get("id") or person.get("person_id")
        if not person_id:
            print(f"⚠️ Skipping person {i+1}: no Apollo ID found.")
            continue

        enriched_person = apollo_enrich_by_id(
            person_id,
            reveal_personal_emails=True,
            reveal_phone_number=False
        )
        if enriched_person:
            enriched.append(enriched_person)

    print(f"✅ Enriched {len(enriched)} out of {len(people)} people.")
    state["apollo_enriched_results"] = enriched
    return state

def enrich_all_apollo_companies(state: State) -> State:
    companies = state.get("apollo_results") or []
    if not companies:
        print("⚠️ No companies to enrich.")
        state["apollo_enriched_companies"] = []
        return state

    enriched = []
    print(f"\n⚙️ Starting enrichment for {len(companies)} companies...")

    for i, company in enumerate(companies[:5]):
        domain = None

        if company.get("primary_domain"):
            domain = company["primary_domain"].replace("http://", "").replace("https://", "").replace("www.", "")
        elif company.get("website_url"):
            domain = urllib.parse.urlparse(company["website_url"]).netloc.replace("www.", "")

        if not domain:
            print(f"⚠️ Skipping {company.get('name')} — no valid domain found.")
            continue

        enriched_company = apollo_enrich_company(domain)
        if enriched_company:
            enriched.append(enriched_company)
        else:
            print(f"⚠️ No enrichment data found for {domain}.")

    print(f"✅ Enriched {len(enriched)} out of {len(companies)} companies.")
    state["apollo_enriched_companies"] = enriched
    return state

def normalize_apollo_locations(state: State) -> State:
    extracted: ExtractedApolloFilters = state.get("extracted_filters") or ExtractedApolloFilters()

    if not extracted.person_locations:
        return state

    llm = ChatOpenAI(model=LLM_MINI).with_structured_output(NormalizedLocations)

    prompt = f"""
    You are a location normalization expert for Apollo.io People Search API.

    Apollo only supports real countries or cities — not regions like "Europe" or "APAC".
    Expand or replace any vague region names with valid countries.

    Guidelines:
    - Return a JSON object matching this schema: {{ "person_locations": [list of valid names] }}
    - Do not include regions like "Europe", "APAC", "DACH" etc.
    - Examples:
        Input: ["Europe", "APAC", "London"]
        Output:
        {{
          "person_locations": [
            "United Kingdom", "Germany", "France", "Netherlands", "Spain", "Italy",
            "India", "Singapore", "Australia", "Japan",
            "London"
          ]
        }}

    Input locations: {json.dumps(extracted.person_locations, indent=2)}
    """

    try:
        result = llm.invoke(prompt)
        extracted.person_locations = result.person_locations
        state["extracted_filters"] = extracted
        print(f"✅ Normalized Locations → {extracted.person_locations}")
    except Exception as e:
        print(f"⚠️ LLM normalization failed ({e}) — keeping originals.")
        state["extracted_filters"] = extracted

    return state

# # =======================================================
# # 11️⃣ GRAPH CONSTRUCTION (optimized wiring)
# # =======================================================

# def build_graph():
#     graph = StateGraph(State)

#     graph.add_node("analyze_intent", analyze_intent)
#     graph.add_node("query_enricher", query_enricher)
#     graph.add_node("discovery_planner", autonomous_discovery_planner)
#     graph.add_node("planner_pipeline", planner_pipeline)
#     graph.add_node("apollo_filter_extractor", apollo_filter_extractor)
#     graph.add_node("apollo_people_query_planner_llm", apollo_people_query_planner_llm)
#     graph.add_node("apollo_company_query_planner_llm", apollo_company_query_planner_llm)
#     graph.add_node("normalize_apollo_locations", normalize_apollo_locations)
#     graph.add_node("apollo_people_search", apollo_people_search)
#     graph.add_node("apollo_company_search", apollo_company_search)
#     graph.add_node("enrich_all_apollo_people", enrich_all_apollo_people)
#     graph.add_node("enrich_all_apollo_companies", enrich_all_apollo_companies)
#     graph.add_node("summarize_apollo_results", summarize_apollo_results)
#     graph.add_node("fallback_serp_node", fallback_serp_node)

#     graph.set_entry_point("analyze_intent")
#     graph.add_edge("analyze_intent", "query_enricher")
#     graph.add_edge("query_enricher", "discovery_planner")
#     graph.add_edge("discovery_planner", "planner_pipeline")

#     graph.add_conditional_edges(
#         "planner_pipeline",
#         apollo_router,
#         {
#             "apollo_filter_extractor": "apollo_filter_extractor",
#             "fallback_serp_node": "fallback_serp_node"
#         }
#     )

#     graph.add_conditional_edges(
#         "apollo_filter_extractor",
#         apollo_planner_router,
#         {
#             "apollo_people_query_planner_llm": "apollo_people_query_planner_llm",
#             "apollo_company_query_planner_llm": "apollo_company_query_planner_llm"
#         }
#     )

#     graph.add_edge("apollo_people_query_planner_llm", "normalize_apollo_locations")
#     graph.add_edge("apollo_company_query_planner_llm", "normalize_apollo_locations")

#     graph.add_conditional_edges(
#         "normalize_apollo_locations",
#         apollo_search_type_router,
#         {
#             "apollo_people_search": "apollo_people_search",
#             "apollo_company_search": "apollo_company_search",
#             "fallback_serp_node": "fallback_serp_node"
#         }
#     )

#     graph.add_edge("apollo_people_search", "enrich_all_apollo_people")
#     graph.add_edge("enrich_all_apollo_people", "summarize_apollo_results")

#     graph.add_edge("apollo_company_search", "enrich_all_apollo_companies")
#     graph.add_edge("enrich_all_apollo_companies", "summarize_apollo_results")

#     graph.add_edge("summarize_apollo_results", END)
#     graph.add_edge("fallback_serp_node", END)

#     return graph.compile()

# # =======================================================
# # 12️⃣ RUNNER
# # =======================================================

# def run(query: str):
#     app = build_graph()

#     seed_state = {
#         "query": query,
#         "enriched_query": None,
#         "intent": Intent(query="", intent_type="general_search", entity_type="unknown"),
#         "discovery_plan": {},
#         "apollo_query": None,
#         "serp_queries": [],
#         "apollo_results": [],
#         "apollo_summary": None,
#         "extracted_filters": ExtractedApolloFilters(),
#     }

#     print(f"\n🚀 Starting Apollo Discovery Pipeline")
#     print(f"🔎 Query: {query}")
#     print("=" * 100)

#     result = app.invoke(seed_state)

#     print("\n🎯 INTENT DETECTED:")
#     print(json.dumps(result["intent"].dict(exclude_none=True), indent=2))

#     print("\n🗺️ DISCOVERY PLAN:")
#     print(json.dumps(result.get("discovery_plan", {}), indent=2))

#     if result.get("apollo_query"):
#         print(f"\n🧩 Apollo DSL Query:\n{result['apollo_query']}")
#         if result.get("apollo_query_url"):
#             print(f"🔗 Apollo Query URL:\n{result['apollo_query_url']}")
#     else:
#         print("\n⚙️ Apollo not triggered (fallback to SERP).")

#     if result.get("apollo_enriched_results"):
#         enriched_people = result["apollo_enriched_results"]
#         print(f"\n👥 ENRICHED PEOPLE PROFILES ({len(enriched_people)}):")
#         print("-" * 100)
#         for i, person in enumerate(enriched_people):
#             print(f"\n{i+1}. {person.get('name')} — {person.get('organization_name')}")
#             print(f"   🧠 Title: {person.get('title') or 'N/A'}")
#             print(f"   💼 Headline: {person.get('headline') or 'N/A'}")
#             print(f"   ✉️  Email: {person.get('email') or 'N/A'}")
#             print(f"   🔗 LinkedIn: {person.get('linkedin_url') or 'N/A'}")
#             print(f"   📍 Location: {', '.join(filter(None, [person.get('city'), person.get('state'), person.get('country')])) or 'N/A'}")

#     elif result.get("apollo_results") and result["intent"].entity_type in ["person", "individual", "talent"]:
#         people = result["apollo_results"]
#         print(f"\n👥 Apollo People Results ({len(people)} found):")
#         for i, person in enumerate(people):
#             print(f"\n{i+1}. {person.get('name')} — {person.get('organization_name')}")
#             print(f"   • Title: {person.get('title')}")
#             print(f"   • Email: {person.get('email')}")
#             print(f"   • LinkedIn: {person.get('linkedin_url')}")

#     if result.get("apollo_enriched_companies"):
#         enriched_companies = result["apollo_enriched_companies"]
#         print(f"\n🏢 ENRICHED COMPANY PROFILES ({len(enriched_companies)}):")
#         print("-" * 100)

#         for i, c in enumerate(enriched_companies):
#             print(f"\n{i+1}. {c.get('name')} — {c.get('website_url') or 'N/A'}")
#             print(f"   🏷️  Industry: {', '.join(c.get('industries', [])) or c.get('industry') or 'N/A'}")
#             print(f"   👥 Employees: {c.get('estimated_num_employees') or 'N/A'}")
#             print(f"   💰 Revenue: {c.get('organization_revenue_printed') or 'N/A'}")
#             print(f"   📅 Founded: {c.get('founded_year') or 'N/A'}")

#             phone = (
#                 c.get("phone")
#                 or (c.get("primary_phone", {}) or {}).get("number")
#                 or "N/A"
#             )
#             print(f"   ☎️  Phone: {phone}")

#             print(f"   🌍 Domain: {c.get('primary_domain') or 'N/A'}")
#             print(f"   🔗 LinkedIn: {c.get('linkedin_url') or 'N/A'}")
#             print(f"   🐦 Twitter: {c.get('twitter_url') or 'N/A'}")
#             print(f"   📘 Facebook: {c.get('facebook_url') or 'N/A'}")

#             print(f"   📍 Location: {', '.join(filter(None, [c.get('city'), c.get('state'), c.get('country')])) or 'N/A'}")

#             techs = c.get("technology_names", [])
#             if techs:
#                 tech_display = ", ".join(techs[:10]) + ("..." if len(techs) > 10 else "")
#                 print(f"   💻 Tech Stack: {tech_display}")
#             else:
#                 print("   💻 Tech Stack: N/A")

#             desc = c.get("short_description") or ""
#             if desc:
#                 short_desc = desc.strip().split("\n")[0][:300]
#                 print(f"   📝 Summary: {short_desc}...")

#     elif result.get("apollo_results") and result["intent"].entity_type in ["company", "organization", "fund", "startup", "business"]:
#         companies = result["apollo_results"]
#         print(f"\n🏢 Apollo Company Results ({len(companies)} found):")
#         for i, c in enumerate(companies):
#             print(f"\n{i+1}. {c.get('name')} — {c.get('website_url')}")
#             print(f"   • Domain: {c.get('primary_domain')}")
#             print(f"   • Industry: {c.get('industry')}")
#             print(f"   • Employees: {c.get('estimated_num_employees')}")

#     if result.get("apollo_summary"):
#         print("\n📊 Apollo Summary:")
#         print(result["apollo_summary"])

#     serp_queries = result.get("serp_queries", [])
#     if serp_queries:
#         print("\n🌐 SERP / Fallback Queries:")
#         for sq in serp_queries:
#             print(f" • {sq}")

#     print("\n✅ Pipeline Complete.")
#     print("=" * 100)
#     return result

# if __name__ == "__main__":
#     if not os.getenv("APOLLO_API_KEY"):
#         print("\n--- ATTENTION ---")
#         print("⚠️ APOLLO_API_KEY environment variable not set.")
#         print("   The Apollo search steps will be skipped/fail.")
#         print("   Only LLM processing and SERP query generation will run.")
#         print("-----------------\n")

#     run("Find Distributors of High End Cosmetics & Skin care products in UAE")
