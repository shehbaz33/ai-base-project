from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID

class SearchBase(BaseModel):
    query: str
    filters: Optional[Dict[str, Any]] = None

class SearchCreate(SearchBase):
    pass

class Search(SearchBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True

class SearchResultEntity(BaseModel):
    id: UUID
    name: str
    title: Optional[str] = None
    company_name: Optional[str] = None
    company_domain: Optional[str] = None
    email: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    website_url: Optional[str] = None
    phone: Optional[str] = None
    
    class Config:
        orm_mode = True

class SearchResultBase(BaseModel):
    search_id: UUID
    entity_id: UUID
    rank: Optional[int] = None
    score: Optional[float] = None
    raw_payload: Optional[Dict[str, Any]] = None

class SearchResultCreate(SearchResultBase):
    pass

class SearchResult(SearchResultBase):
    id: UUID
    created_at: datetime
    entity: Optional[SearchResultEntity] = None
    
    class Config:
        orm_mode = True

class SearchWithResults(Search):
    results: List[SearchResult] = []
    
    class Config:
        orm_mode = True