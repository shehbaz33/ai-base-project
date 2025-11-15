import json
import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.utils.redis_client import redis_client
from anyio import to_thread

router = APIRouter()
logger = logging.getLogger(__name__)

# Async Redis client

async def redis_listener(websocket: WebSocket, task_id: str):
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("agent_updates")

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1)

            if not message:
                await asyncio.sleep(0.1)
                continue

            data = json.loads(message["data"])

            # Only forward events for this client’s task id
            if data["task_id"] == task_id:
                await websocket.send_json(data)

    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe("agent_updates")
        await pubsub.close()

@router.websocket("/ws/agent/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await websocket.accept()

    key = f"agent_stream:{task_id}"

    try:
        while True:
            # BLPOP is blocking → offload to thread
            result = await to_thread.run_sync(
                redis_client.blpop,
                key
            )

            if not result:
                await asyncio.sleep(0.1)
                continue

            _, message = result
            data = json.loads(message)

            await websocket.send_json(data)

    except WebSocketDisconnect:
        print(f"Disconnected {task_id}")

    finally:
        pass



@router.get("/test_redis")
async def test_redis():
    await redis_client.publish(
        "agent_updates",
        json.dumps({
            "task_id": "test123",
            "agent": "test_agent",
            "type": "test",
            "stage": "test",
            "message": "Test message from Redis",
            "payload": {"test": True},
            "timestamp": 1234567890
        })
    )
    return {"status": "ok"}
