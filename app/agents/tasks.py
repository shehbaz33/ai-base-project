"""Centralized task definitions to avoid circular imports."""
from celery import shared_task

@shared_task(bind=True, name="run_apollo_agent")
def run_apollo_agent_task(self, query: str, user_id: str):
    """Wrapper task to avoid circular imports."""
    # Lazy import to prevent circular imports
    from app.agents.apollo.task import run_apollo_agent
    return run_apollo_agent(query, user_id)


@shared_task(bind=True, name="run_finder_agent")
def run_finder_agent_task(self, query: str, user_id: str):
    """Wrapper task to avoid circular imports."""
    # Lazy import to prevent circular imports
    from app.agents.finder.task import run_finder_agent_impl
    return run_finder_agent_impl(self.request.id, query, user_id)
