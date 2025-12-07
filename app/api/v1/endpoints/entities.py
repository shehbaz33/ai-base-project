from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.entities import Entity
from app.models.entity_profiles import EntityProfile
from app.models.finder_sessions import FinderSession
from app.models.finder_session_results import FinderSessionResult
from app.utils.api_response import create_api_response

router = APIRouter()

@router.get("", response_model=dict)
async def get_user_entities(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 50
):
    """
    Get all unique entities (leads) found for the current user across all sessions.
    Returns the most recent occurrence for each entity.
    """
    
    # Query to fetch unique entities joined with their profile and session info
    # We use DISTINCT ON (Entity.id) to ensure uniqueness
    # We order by Entity.id and FinderSession.created_at DESC to get the most recent finding
    
    query = db.query(
        Entity,
        EntityProfile,
        FinderSession
    ).join(
        FinderSessionResult, Entity.id == FinderSessionResult.entity_id
    ).join(
        FinderSession, FinderSessionResult.session_id == FinderSession.id
    ).join(
        EntityProfile, Entity.id == EntityProfile.entity_id
    ).filter(
        FinderSession.user_id == current_user.id
    ).distinct(
        Entity.id
    ).order_by(
        Entity.id,
        FinderSession.created_at.desc()
    )
    
    # Apply pagination (Note: distinct on requires the order by to start with the distinct column)
    # So we fetch all distinct first then slice? 
    # SQLAlchemy's limit/offset with distinct on can be tricky.
    # Ideally we subquery or just fetch and slice if dataset is small.
    # For scalable pagination with DISTINCT ON, we usually need a subquery.
    
    # Let's try direct limit/offset. Postgres handles DISTINCT ON + LIMIT correctly (applies distinct then limit).
    results = query.offset(skip).limit(limit).all()
    
    entities = []
    for entity, profile, session in results:
        entities.append({
            "entity_id": str(entity.id),
            "name": entity.name,
            "type": entity.entity_type.value,
            "email": profile.email,
            "title": profile.title,
            "linkedin_url": profile.linkedin_url,
            "company_name": profile.company_name,
            "location": profile.location,
            "industry": profile.industry,
            "website_url": profile.website_url,
            "source_agent": "Finder Agent", # Currently only Finder Agent exists
            "source_session_id": str(session.id),
            "found_at": session.created_at.isoformat() if session.created_at else None,
            "raw_input": session.raw_input
        })
        
    return create_api_response(data=entities, message="found entities")


@router.get("/{entity_id}", response_model=dict)
async def get_entity_details(
    entity_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed information for a specific entity, including raw data from sources (Apollo, etc.).
    """
    from app.models.entity_sources import EntitySource
    
    # Verify entity exists and is linked to user (via sessions)
    # Security check: Ensure the user has access to this entity
    # We check if this entity is linked to any session owned by the user
    is_linked = db.query(FinderSessionResult).join(
        FinderSession, FinderSessionResult.session_id == FinderSession.id
    ).filter(
        FinderSessionResult.entity_id == entity_id,
        FinderSession.user_id == current_user.id
    ).first()
    
    if not is_linked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found or access denied"
        )
        
    # Fetch Entity, Profile, and Sources
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    profile = db.query(EntityProfile).filter(EntityProfile.entity_id == entity_id).first()
    sources = db.query(EntitySource).filter(EntitySource.entity_id == entity_id).all()
    
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
        
    response = {
        "id": str(entity.id),
        "name": entity.name,
        "type": entity.entity_type.value,
        "created_at": entity.created_at.isoformat(),
        "profile": {
            "title": profile.title,
            "email": profile.email,
            "linkedin_url": profile.linkedin_url,
            "company_name": profile.company_name,
            "company_domain": profile.company_domain,
            "location": profile.location,
            "industry": profile.industry,
            "employee_count": profile.employee_count,
            "website_url": profile.website_url,
            "phone": profile.phone,
            "revenue": profile.revenue,
            "data": profile.data # Any extra flexible data
        } if profile else None,
        "sources": [
            {
                "provider": source.provider,
                "provider_id": source.provider_entity_id,
                "confidence": source.confidence_score,
                "fetched_at": source.created_at.isoformat(),
                "raw_data": source.raw_data # The full raw JSON from Apollo
            } for source in sources
        ]
    }
    
    return create_api_response(data=response, message="found entity details")
