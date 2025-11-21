# Initialize the CRUD module
from .search import (
    create_search,
    get_search,
    get_user_searches,
    get_recent_searches,
    create_search_result,
    get_search_with_results,
    get_unique_entities_from_searches,
    get_unique_entities_count,
)

__all__ = [
    'create_search',
    'get_search',
    'get_user_searches',
    'get_recent_searches',
    'create_search_result',
    'get_search_with_results',
    'get_unique_entities_from_searches',
    'get_unique_entities_count',
]
