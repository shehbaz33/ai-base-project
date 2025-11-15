# app/utils/async_redis.py

import redis.asyncio as aioredis

async_redis = aioredis.Redis(
    host="redis",
    port=6379,
    db=0,
    decode_responses=True  # important so messages come as strings
)
