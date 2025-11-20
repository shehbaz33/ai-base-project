from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session, joinedload, contains_eager
from sqlalchemy import desc, or_, func
from sqlalchemy.orm.attributes import flag_modified

from app.models.searches import Search as SearchModel
from app.models.search_results import SearchResult as SearchResultModel
from app.models.entities import Entity, EntityType
from app.models.entity_profiles import EntityProfile
from app.schemas.search import Search, SearchCreate, SearchResultCreate, SearchWithResults, SearchResult

def create_search(db: Session, search: SearchCreate, user_id: UUID) -> SearchModel:
    """
    Create a new search record.
    
    Args:
        db: Database session
        search: Search create schema
        user_id: ID of the user creating the search
        
    Returns:
        The created Search model instance
    """
    try:
        db_search = SearchModel(
            user_id=user_id,
            query=search.query,
            filters=search.filters or {}
        )
        db.add(db_search)
        db.commit()
        db.refresh(db_search)
        return db_search
    except Exception as e:
        db.rollback()
        raise e

def get_search(db: Session, search_id: UUID, user_id: UUID) -> Optional[SearchModel]:
    """
    Get a search by ID for a specific user.
    
    Args:
        db: Database session
        search_id: ID of the search to retrieve
        user_id: ID of the user who owns the search
        
    Returns:
        The Search model instance if found, None otherwise
    """
    return db.query(SearchModel)\
        .filter(
            SearchModel.id == search_id,
            SearchModel.user_id == user_id
        )\
        .first()

def get_user_searches(
    db: Session, 
    user_id: UUID, 
    skip: int = 0, 
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Get all searches for a user with basic information and result counts.
    
    Args:
        db: Database session
        user_id: ID of the user
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return (pagination)
        
    Returns:
        List of dictionaries containing search information
    """
    # Get searches with result counts
    searches = db.query(
        SearchModel,
        func.count(SearchResultModel.id).label('result_count')
    )\
    .outerjoin(SearchResultModel, SearchModel.id == SearchResultModel.search_id)\
    .filter(SearchModel.user_id == user_id)\
    .group_by(SearchModel.id)\
    .order_by(desc(SearchModel.created_at))\
    .offset(skip)\
    .limit(limit)\
    .all()
    
    # Convert to list of dictionaries
    return [
        {
            'id': search.id,
            'user_id': search.user_id,
            'query': search.query,
            'filters': search.filters or {},
            'created_at': search.created_at,
            'updated_at': search.created_at,
            'result_count': result_count
        }
        for search, result_count in searches
    ]

def get_recent_searches(
    db: Session, 
    user_id: UUID, 
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Get recent searches for a user with basic information.
    
    Args:
        db: Database session
        user_id: ID of the user
        limit: Maximum number of recent searches to return
        
    Returns:
        List of dictionaries containing recent search information
    """
    # Get recent searches with result counts
    searches = db.query(
        SearchModel,
        func.count(SearchResultModel.id).label('result_count')
    )\
    .outerjoin(SearchResultModel, SearchModel.id == SearchResultModel.search_id)\
    .filter(SearchModel.user_id == user_id)\
    .group_by(SearchModel.id)\
    .order_by(desc(SearchModel.created_at))\
    .limit(limit)\
    .all()
    
    # Convert to list of dictionaries
    return [
        {
            'id': search.id,
            'user_id': search.user_id,
            'query': search.query,
            'filters': search.filters or {},
            'created_at': search.created_at,
            'updated_at': search.created_at,  # Using created_at as fallback
            'result_count': result_count
        }
        for search, result_count in searches
    ]

def create_search_result(
    db: Session, 
    search_result: SearchResultCreate
) -> SearchResultModel:
    """
    Create a new search result.
    
    Args:
        db: Database session
        search_result: Search result data
        
    Returns:
        The created SearchResult model instance
    """
    try:
        db_search_result = SearchResultModel(**search_result.dict())
        db.add(db_search_result)
        db.commit()
        db.refresh(db_search_result)
        return db_search_result
    except Exception as e:
        db.rollback()
        raise e

def get_search_with_results(
    db: Session, 
    search_id: UUID, 
    user_id: UUID
) -> Optional[Dict[str, Any]]:
    """
    Get a search with all its results and entity details.
    
    Args:
        db: Database session
        search_id: ID of the search to retrieve
        user_id: ID of the user who owns the search
        
    Returns:
        Dictionary containing search and its results, or None if not found
    """
    # Get the search with basic info
    search = db.query(SearchModel)\
        .filter(
            SearchModel.id == search_id,
            SearchModel.user_id == user_id
        )\
        .first()
    
    if not search:
        return None
    
    # Get all results with entity and profile information
    results = db.query(
        SearchResultModel,
        Entity,
        EntityProfile
    )\
    .join(Entity, SearchResultModel.entity_id == Entity.id)\
    .outerjoin(EntityProfile, Entity.id == EntityProfile.entity_id)\
    .filter(SearchResultModel.search_id == search_id)\
    .order_by(SearchResultModel.rank.asc())\
    .all()
    
    # Prepare the response
    search_data = {
        'id': search.id,
        'query': search.query,
        'filters': search.filters or {},
        'created_at': search.created_at,
        'updated_at': search.updated_at,
        'results': []
    }
    
    # Process results
    for result, entity, profile in results:
        result_data = {
            'id': result.id,
            'search_id': result.search_id,
            'entity_id': result.entity_id,
            'rank': result.rank,
            'score': result.score,
            'created_at': result.created_at,
            'entity': {
                'id': entity.id,
                'name': entity.name,
                'entity_type': entity.entity_type.value if entity.entity_type else None,
                'title': profile.title if profile else None,
                'company_name': profile.company_name if profile else None,
                'company_domain': profile.company_domain if profile else None,
                'email': profile.email if profile else None,
                'location': profile.location if profile else None,
                'linkedin_url': profile.linkedin_url if profile else None,
                'website_url': profile.website_url if profile else None,
                'phone': profile.phone if profile else None
            }
        }
        search_data['results'].append(result_data)
    
    return search_data
