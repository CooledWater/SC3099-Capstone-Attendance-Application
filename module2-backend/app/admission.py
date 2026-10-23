"""Queue database requests before they occupy synchronous worker threads.

Otherwise connection-pool waiters can fill the worker pool, preventing the
requests holding connections from running and returning those connections.
"""
import asyncio


class DatabaseAdmission:
    def __init__(self, app, concurrency=8):
        self.app = app
        self.slots = asyncio.Semaphore(concurrency)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('path') in ('/health', '/metrics'):
            return await self.app(scope, receive, send)
        async with self.slots:
            await self.app(scope, receive, send)
