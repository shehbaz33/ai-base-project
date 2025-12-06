"""Centralized task definitions to avoid circular imports."""
from typing import Optional
from celery import shared_task

@shared_task(bind=True, name="run_apollo_agent")
def run_apollo_agent_task(self, query: str, user_id: str):
    """Wrapper task to avoid circular imports."""
    # Lazy import to prevent circular imports
    from app.agents.apollo.task import run_apollo_agent
    return run_apollo_agent(query, user_id)


@shared_task(bind=True, name="run_finder_agent")
def run_finder_agent(self, input_text: str, user_id: Optional[str] = None):
    """Celery task wrapper"""
    # Lazy import to prevent circular imports
    from app.agents.finder.task import run_finder_agent_impl
    return run_finder_agent_impl(self.request.id, input_text, user_id)


@shared_task(bind=True, name="continue_finder_session")
def continue_finder_session(self, session_id: str, page: int = 1, per_page: int = 10):
    """Celery task wrapper for pagination"""
    # Lazy import to prevent circular imports
    from app.agents.finder.task import continue_finder_session_impl
    return continue_finder_session_impl(session_id, page, per_page)
