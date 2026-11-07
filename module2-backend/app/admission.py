"""Queue database requests before they occupy synchronous worker threads.

Otherwise connection-pool waiters can fill the worker pool, preventing the
requests holding connections from running and returning those connections.
"""
import asyncio


def database_admission_capacity(engine):
    """Keep HTTP admission within the retained database pool's capacity.

    Otherwise handlers that commit during dependency setup can starve while
    reacquiring a connection, behind requests already occupying worker threads.
    Leave the database's own shared pool to arbitrate short scheduler work.
    """
    size = getattr(engine.pool, 'size', None)
    return max(1, size()) if callable(size) else 8


class DatabaseAdmission:
    def __init__(self, app, concurrency=8):
        self.app = app
        self.concurrency = concurrency
        self.slots = asyncio.Semaphore(concurrency)

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'lifespan':
            self.slots = asyncio.Semaphore(self.concurrency)
        if scope['type'] != 'http' or scope.get('path') in ('/health', '/metrics'):
            return await self.app(scope, receive, send)
        async with self.slots:
            await self.app(scope, receive, send)
