from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import sys

# Application imports
from app.database import init_db
from app.config.settings import get_settings
from app.api.v1.endpoints import auth as auth_endpoints, research_agents, search_agents, websocket, finder_agent, finder_sessions, entities
from app.api.v1.endpoints import protected as protected_endpoints
from app.api.v1.endpoints import router as example_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

settings = get_settings()

# Try to import Celery, but make it optional
try:
    from .tasks.example_tasks import example_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    logging.warning("Celery not available. Background tasks will be disabled.")

def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        description="A clean FastAPI base project ready for development",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS middleware - configure as needed
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Update this in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    init_db()

    # Include API routers
    app.include_router(example_router, prefix="/api/v1")
    app.include_router(auth_endpoints.router, prefix="/api/v1/auth", tags=["Authentication"])
    app.include_router(protected_endpoints.router, prefix="/api/v1", tags=["Protected"])
    app.include_router(search_agents.router, prefix="/api/v1", tags=["Search Agents"])
    app.include_router(websocket.router, prefix="/api/v1", tags=["Websocket"])
    app.include_router(research_agents.router, prefix="/api/v1/research", tags=["Research Agents"])
    app.include_router(finder_agent.router, prefix="/api/v1/finder", tags=["Finder Agents"])
    app.include_router(finder_sessions.router, prefix="/api/v1/finder_agents", tags=["Finder Agents Sessions"])
    app.include_router(entities.router, prefix="/api/v1/entities", tags=["Entities"])
    @app.get("/health")
    async def health_check():
        """Health check endpoint""" 
        return {
            "status": "healthy",
            "app_name": settings.APP_NAME,
            "environment": settings.APP_ENV,
            "celery_available": CELERY_AVAILABLE
        }

    @app.post("/task/example")
    async def run_example_task(data: dict = Body(...)):
        """
        Example endpoint that triggers a Celery background task.
        Only works if Celery is properly configured and available.
        """
        if not CELERY_AVAILABLE:
            return JSONResponse({
                "message": "Background tasks not available. Install Celery and Redis to enable this feature.",
                "task_id": None,
                "status": "unavailable"
            }, status_code=503)

        x = data.get("x", 0)
        y = data.get("y", 0)

        # Queue the task asynchronously
        task = example_task.delay(x, y)

        return JSONResponse({
            "message": "Task queued successfully",
            "task_id": str(task.id),
            "status": "pending"
        })

    return app

app = create_application()
