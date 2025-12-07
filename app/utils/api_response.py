from typing import Any, Optional

def create_api_response(
    data: Any = [],
    message: str = "Success",
    status: bool = True,
) -> dict:
    """
    Standardized API response format.
    
    Args:
        data: The payload to return (list, dict, etc.)
        message: A descriptive message about the response
        status: Boolean indicating success or failure
        
    Returns:
        dict: A dictionary with keys 'status', 'message', and 'data'
    """
    return {
        "status": status,
        "message": message,
        "data": data
    }
