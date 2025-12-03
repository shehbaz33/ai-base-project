# app/agents/finder/models.py

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# ---------------------------
# PRODUCT UNDERSTANDING MODELS
# ---------------------------

class ProductContext(BaseModel):
    product_name: Optional[str] = None
    product_summary: str = ""
    features: List[str] = Field(default_factory=list)
    use_cases: List[str] = Field(default_factory=list)
    pricing_model: Optional[str] = None
    target_segments_mentioned: List[str] = Field(default_factory=list)

class ProductUnderstanding(BaseModel):
    core_value_prop: Optional[str] = None
    pain_points_solved: List[str] = Field(default_factory=list)
    job_to_be_done: List[str] = Field(default_factory=list)
    beneficiaries: List[str] = Field(default_factory=list)
    competitive_positioning: Optional[str] = None
    ideal_industries: List[str] = Field(default_factory=list)
    entity_name: Optional[str] = None

class ICPProfile(BaseModel):
    industry: Optional[str] = None
    company_size: Optional[str] = None
    regions: List[str] = Field(default_factory=list)
    tech_stack_indicators: List[str] = Field(default_factory=list)
    budget_signals: Optional[str] = None
    value_drivers: List[str] = Field(default_factory=list)

class Persona(BaseModel):
    persona_name: str
    titles: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    pain_points: List[str] = Field(default_factory=list)
    kpis: List[str] = Field(default_factory=list)
    where_they_live_online: List[str] = Field(default_factory=list)
    apollo_search_keywords: List[str] = Field(default_factory=list)

