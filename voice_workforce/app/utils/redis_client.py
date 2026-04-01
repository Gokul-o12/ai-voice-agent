import redis.asyncio as redis
import os
import json # ADD THIS

class RedisManager:
    def __init__(self):
        self.client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

    async def set_call_state(self, call_sid: str, state: dict, expire: int = 3600):
        # FIX: Use json.dumps instead of str()
        await self.client.set(f"call_state:{call_sid}", json.dumps(state), ex=expire)

    async def get_call_state(self, call_sid: str):
        data = await self.client.get(f"call_state:{call_sid}")
        # FIX: Use json.loads instead of eval()
        return json.loads(data) if data else {}

    async def track_retry(self, phone_number: str):
        key = f"retry_count:{phone_number}"
        return await self.client.incr(key)

redis_manager = RedisManager()