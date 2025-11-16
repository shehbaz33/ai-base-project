# app/utils/publisher.py
import json
import time
from app.utils.redis_client import redis_client

def publish_event(task_id, agent, event_type, stage, message, payload=None):
    event = {
        "task_id": task_id,
        "agent": agent,
        "type": event_type,
        "stage": stage,
        "message": message,
        "payload": payload or {},
        "timestamp": time.time(),
    }

    redis_client.publish(f"task:{task_id}", json.dumps(event))
