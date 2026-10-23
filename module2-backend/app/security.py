"""Opt-in safeguards that preserve the published classroom API by default."""
import hashlib
import json
import os
import time
from functools import lru_cache
from urllib.parse import urlsplit

import redis
from fastapi import HTTPException


def strict_mode():
    return os.getenv('STRICT_SECURITY_MODE', 'false').lower() in ('1', 'true', 'yes')


def validate_settings():
    if strict_mode():
        secret = os.getenv('JWT_SECRET', '')
        if len(secret) < 32 or 'your-secret' in secret.lower():
            raise RuntimeError('Strict security requires a non-placeholder JWT_SECRET of at least 32 characters')
        if not os.getenv('REDIS_URL'):
            raise RuntimeError('Strict security requires REDIS_URL')


def cors_origins():
    raw = os.getenv('CORS_ORIGINS')
    values = (json.loads(raw) if raw.lstrip().startswith('[') else raw.split(',')) if raw else ['http://localhost:3000', 'http://localhost:8501']
    if not isinstance(values, list):
        raise RuntimeError('CORS_ORIGINS must be a list of exact origins')
    for value in values:
        parsed = urlsplit(value.strip())
        if '*' in value or parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.path not in ('', '/') or parsed.query or parsed.fragment or parsed.username:
            raise RuntimeError('CORS_ORIGINS must contain exact HTTP(S) origins without wildcards')
    return [value.strip().rstrip('/') for value in values]


@lru_cache(maxsize=4)
def _client(url):
    return redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)


def redis_client():
    return _client(os.environ['REDIS_URL'])


def enforce_rate_limit(category, identity, limit, seconds):
    if not strict_mode():
        return
    key = 'saiv:limit:' + category + ':' + hashlib.sha256(identity.encode()).hexdigest()
    try:
        count = redis_client().eval("local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n", 1, key, seconds)
    except redis.RedisError:
        raise HTTPException(503, 'Security service unavailable; retry later')
    if count > limit:
        raise HTTPException(429, 'Too many requests; retry later', headers={'Retry-After': str(seconds)})


def _refresh_key(token):
    return 'saiv:refresh-used:' + hashlib.sha256(token.encode()).hexdigest()


def check_refresh(token):
    if not strict_mode():
        return
    try:
        used = redis_client().exists(_refresh_key(token))
    except redis.RedisError:
        raise HTTPException(503, 'Security service unavailable; retry later')
    if used:
        raise HTTPException(401, 'Refresh token already used or revoked')


def consume_refresh(token, payload, reject_reuse=True):
    if not strict_mode():
        return
    ttl = max(1, int(payload['exp'] - time.time()) + 1)
    try:
        fresh = redis_client().set(_refresh_key(token), '1', nx=True, ex=ttl)
    except redis.RedisError:
        raise HTTPException(503, 'Security service unavailable; retry later')
    if reject_reuse and not fresh:
        raise HTTPException(401, 'Refresh token already used or revoked')
