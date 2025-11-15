# app/utils/redis_client.py
import redis

redis_client = redis.Redis(
    host="redis",
    port=6379,
    db=0,
    decode_responses=True  # Make sure messages come as strings
)
