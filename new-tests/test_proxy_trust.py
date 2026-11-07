"""Real Uvicorn trust paths plus the backend entry-point default."""
import os
from pathlib import Path
import socket
import sys
import threading
import time

import httpx
import pytest
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'module2-backend'))
from app.server import run


@pytest.mark.parametrize('allowed,expected', [('', '127.0.0.1'), ('127.0.0.1', '198.51.100.12')])
def test_real_proxy_headers_are_used_only_for_configured_upstream(allowed, expected):
    async def app(scope, receive, send):
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': scope['client'][0].encode()})
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, lifespan='off',
                                         forwarded_allow_ips=allowed, proxy_headers=True, log_level='error'))
    worker = threading.Thread(target=server.run)
    worker.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and worker.is_alive() and time.monotonic() < deadline:
            time.sleep(.01)
        assert server.started
        response = httpx.get(f'http://127.0.0.1:{port}', headers={'X-Forwarded-For': '198.51.100.12'}, trust_env=False)
        assert response.text == expected
    finally:
        server.should_exit = True
        worker.join(timeout=10)
    assert not worker.is_alive()


def test_backend_entry_point_defaults_to_no_trusted_proxies(monkeypatch):
    monkeypatch.delenv('FORWARDED_ALLOW_IPS', raising=False)
    options = []
    monkeypatch.setattr(uvicorn, 'run', lambda app, **kwargs: options.append(kwargs))
    run()
    assert options[0]['forwarded_allow_ips'] == ''
    monkeypatch.setenv('FORWARDED_ALLOW_IPS', '192.0.2.8')
    run()
    assert options[1]['forwarded_allow_ips'] == '192.0.2.8'
