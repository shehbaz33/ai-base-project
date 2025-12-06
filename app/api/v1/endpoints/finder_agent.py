from fastapi import APIRouter, HTTPException,Depends, status
from celery.result import AsyncResult
from typing import Dict, Any

from app.agents.tasks import run_finder_agent
from app.celery_config import celery_app
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.post("/run_finder_agent", response_model=Dict[str, str])
async def trigger_finder_agent(
    payload: Dict[str, str],
    current_user: User = Depends(get_current_user)
):
    """
    Trigger the Finder agent with a query.
    Returns the Celery task ID for tracking.
    """
    if not payload.get("query"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter is required"
        )
        
    try:
        # Start the Finder agent task
        task = run_finder_agent.delay(payload["query"],current_user.id)
        return {
            "task_id": str(task.id),
            "status": "started",
            "message": "Finder agent started. Use the task_id to track progress via WebSocket."
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start search agent: {str(e)}"
        )


@router.get("/finder_agent/task/{task_id}", response_model=Dict[str, Any])
async def get_task_status(task_id: str,current_user: User = Depends(get_current_user)):
    """
    Get the status and result of a Celery task.
    """
    # task_result = AsyncResult(task_id, app=celery_app)
    
    response = {
        "task_id": task_id,
        "status": "completed",
        "ready": True
    }
    
    if task_result.ready():
        if task_result.failed():
            response["result"] = str(task_result.result)
            response["error"] = True
        else:
            response["result"] = task_result.result
            response["error"] = False
    
    return response