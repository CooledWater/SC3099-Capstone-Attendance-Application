"""Bound native inference before it occupies worker threads/model instances."""
import asyncio


class InferenceAdmission:
    def __init__(self, app, concurrency=4):
        self.app = app
        self.concurrency = concurrency
        self.slots = asyncio.Semaphore(concurrency)

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'lifespan':
            # A new server/TestClient lifespan may use a different event loop.
            self.slots = asyncio.Semaphore(self.concurrency)
        if (scope['type'] != 'http' or scope.get('method') != 'POST'
                or not scope.get('path', '').startswith(('/face/', '/liveness/'))):
            return await self.app(scope, receive, send)
        async with self.slots:
            await self.app(scope, receive, send)
