# app/services/search.py

from app.utils.normaliser import normalize_revenue
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from app.models.searches import Search
from app.models.search_results import SearchResult
from app.models.entities import Entity, EntityType
from app.models.entity_profiles import EntityProfile
from app.models.entity_sources import EntitySource
from app.models.providers import Provider


# -------------------------
# PROVIDER
# -------------------------

def get_or_create_provider(db: Session, name: str) -> Provider:
    provider = db.query(Provider).filter(Provider.name == name).first()
    if provider:
        return provider
    
    provider = Provider(
        id=uuid.uuid4(),
        name=name,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


# -------------------------
# SEARCH SESSION
# -------------------------

def create_search_session(db: Session, user_id: str, query: str) -> Search:
    search = Search(
        id=uuid.uuid4(),
        user_id=user_id,
        query=query,
        created_at=datetime.utcnow(),
    )
    db.add(search)
    db.commit()
    db.refresh(search)
    return search


# -------------------------
# ENTITY UPSERT (canonical)
# -------------------------

def upsert_entity(db: Session, entity_type: str, name: str) -> Entity:
    # Dedupe rule: we use name only (can improve later)
    entity = (
        db.query(Entity)
        .filter(Entity.name == name)
        .filter(Entity.entity_type == EntityType(entity_type))
        .first()
    )

    if entity:
        return entity

    entity = Entity(
        id=uuid.uuid4(),
        name=name,
        entity_type=EntityType(entity_type),
        created_at=datetime.utcnow(),
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


# -------------------------
# ENTITY SOURCE (provider raw data)
# -------------------------

def create_entity_source(db: Session, provider: Provider, entity: Entity, raw_data: dict):
    source = EntitySource(
        id=uuid.uuid4(),
        entity_id=entity.id,
        provider=provider.name,
        provider_entity_id=raw_data.get("id"),
        raw_data=raw_data,
        confidence_score=1.0,
    )
    db.add(source)
    db.commit()
    return source


# -------------------------
# ENTITY PROFILE (normalized)
# -------------------------

def create_entity_profile(db: Session, entity: Entity, raw: dict, entity_type: str):
    """
    Normalizes entity attributes for both PERSON + COMPANY.
    """
    print(entity_type,'entity_type')
    if entity_type == "person":
        profile = EntityProfile(
            id=uuid.uuid4(),
            entity_id=entity.id,
            name=raw.get("name"),
            title=raw.get("title"),
            email=raw.get("email"),
            phone = raw.get("phone"),
            company_name=(raw.get("organization") or {}).get("name") if raw.get("organization") else None,
            company_domain=(raw.get("organization") or {}).get("primary_domain") if raw.get("organization") else None,
            location=raw.get("city") or raw.get("formatted_address"),
            industry=(raw.get("organization") or {}).get("industry"),
            employee_count=(raw.get("organization") or {}).get("estimated_num_employees"),
            revenue=(raw.get("organization") or {}).get("organization_revenue"),
            linkedin_url=raw.get("linkedin_url"),
            website_url=raw.get("website_url"),
            data=raw,
        )

        db.add(profile)
        db.commit()
        return profile


    # -----------------------
    # COMPANY PROFILE MAPPING
    # -----------------------

    if entity_type == "company":
        profile = EntityProfile(
            id=uuid.uuid4(),
            entity_id=entity.id,
            name=raw.get("name"),
            title=None,     # companies don't have job titles
            email=None,     # companies don't have email fields
            phone = raw.get("phone"),
            company_name=raw.get("name"),
            company_domain=raw.get("primary_domain") or raw.get("website_url"),
            location=None,  # Apollo doesn't give HQ address for all companies
            industry=(raw.get("industry") 
                      or raw.get("primary_industry") 
                      or raw.get("keyword")),
            
            employee_count=raw.get("estimated_num_employees")
                            or raw.get("organization_headcount"),
            
            revenue=normalize_revenue(raw.get("organization_revenue_printed")),
            
            linkedin_url=raw.get("linkedin_url"),
            website_url=raw.get("website_url"),

            data=raw,   # store full Apollo company record
        )

        db.add(profile)
        db.commit()
        return profile



# -------------------------
# SEARCH RESULT LINKING
# -------------------------

def add_search_result(db: Session, search: Search, entity: Entity, rank: int, raw_payload: dict):
    result = SearchResult(
        id=uuid.uuid4(),
        search_id=search.id,
        entity_id=entity.id,
        rank=rank,
        raw_payload=raw_payload,
    )
    db.add(result)
    db.commit()
    return result
