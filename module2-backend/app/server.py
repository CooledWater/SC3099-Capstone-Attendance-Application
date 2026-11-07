"""Backend entry point with explicit proxy trust (none unless configured)."""
import os

import uvicorn


def run(application='app.main:app', **options):
    # Uvicorn's loopback-trusting default is inappropriate for a directly
    # reachable backend. Operators may configure the exact sanitizing upstream
    # IPs/CIDRs, but should never use '*' with a publicly reachable API.
    options.setdefault('proxy_headers', True)
    options.setdefault('forwarded_allow_ips', os.getenv('FORWARDED_ALLOW_IPS', ''))
    uvicorn.run(application, **options)


if __name__ == '__main__':
    run(host='0.0.0.0', port=8000)
