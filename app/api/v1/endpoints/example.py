from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any, List
from pydantic import BaseModel
import logging

# Set up logging
logger = logging.getLogger(__name__)

from app.utils.api_response import create_api_response

router = APIRouter(prefix="/example", tags=["example"])

# Example Pydantic models
class ExampleRequest(BaseModel):
    """Example request model"""
    name: str
    value: int

class ExampleResponse(BaseModel):
    """Example response model"""
    message: str
    data: Dict[str, Any]

@router.get(
    "/",
    summary="Get all items",
    description="Example GET endpoint that returns a list of items"
)
async def get_items() -> dict:
    """
    Example GET endpoint.
    Replace this with your own logic.
    """
    try:
        # Your logic here
        items = [
            {"id": 1, "name": "Item 1", "value": 100},
            {"id": 2, "name": "Item 2", "value": 200},
        ]
        return create_api_response(data=items, message="Items retrieved")
    except Exception as e:
        logger.error(f"Error in get_items: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving items: {str(e)}"
        )

@router.get(
    "/{item_id}",
    summary="Get item by ID",
    description="Example GET endpoint that returns a single item by ID"
)
async def get_item(item_id: int) -> dict:
    """
    Example GET endpoint with path parameter.
    Replace this with your own logic.
    """
    try:
        # Your logic here
        item = {"id": item_id, "name": f"Item {item_id}", "value": item_id * 100}
        return create_api_response(data=item, message="Item retrieved")
    except Exception as e:
        logger.error(f"Error in get_item: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving item: {str(e)}"
        )

@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new item",
    response_model=dict,
    description="Example POST endpoint that creates a new item"
)
async def create_item(request: ExampleRequest) -> dict:
    """
    Example POST endpoint.
    Replace this with your own logic.
    """
    try:
        # Your logic here
        logger.info(f"Creating item: {request.name}")
        
        return create_api_response(
            message="Item created successfully",
            data={"name": request.name, "value": request.value}
        )
    except Exception as e:
        logger.error(f"Error in create_item: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating item: {str(e)}"
        )
