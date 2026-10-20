import asyncio
from collections.abc import Awaitable, Callable
async def with_backoff(operation: Callable[[], Awaitable], *, attempts: int = 3, base_delay: float = 0.5):
    last=None
    for attempt in range(attempts):
        try: return await operation()
        except Exception as exc:
            last=exc
            if attempt == attempts-1: raise
            await asyncio.sleep(base_delay * (2 ** attempt))
    raise last
