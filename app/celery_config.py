import os
from celery import Celery
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Initialize Celery
celery_app = Celery(
    "worker",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0"),
)

celery_app.autodiscover_tasks(packages=['app.agents','app.agents.apollo'],
    force=True)

# Optional: Update config for serialization & timezone
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)
