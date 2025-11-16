# app/models/search/schemas.py
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime

class SearchEntityBase(BaseModel):
    id: str
    name: str
    type: str
    data: Dict[str, Any]

class SearchEntityCreate(SearchEntityBase):
    pass

class SearchEntity(SearchEntityBase):
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class SearchResultBase(BaseModel):
    query: str

class SearchResultCreate(SearchResultBase):
    pass

class SearchResult(SearchResultBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    entities: List[SearchEntity] = []

    class Config:
        orm_mode = True