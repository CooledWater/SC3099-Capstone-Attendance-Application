import asyncio
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('admission',Path(__file__).resolve().parents[1]/'module2-backend/app/admission.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def test_admission_bounds_100_concurrent_requests():
    async def run():
        active=0;peak=0;completed=0
        async def app(scope,receive,send):
            nonlocal active,peak,completed
            active+=1;peak=max(peak,active)
            await asyncio.sleep(.001)
            completed+=1;active-=1
        middleware=module.DatabaseAdmission(app,8)
        await asyncio.gather(*(middleware({'type':'http','path':'/api/v1/users/me'},None,None) for _ in range(100)))
        assert peak==8 and completed==100
    asyncio.run(run())

def test_cancellation_releases_slot_and_health_bypasses_queue():
    async def run():
        entered=asyncio.Event();release=asyncio.Event();health=asyncio.Event()
        async def app(scope,receive,send):
            if scope['path']=='/health':health.set();return
            entered.set();await release.wait()
        middleware=module.DatabaseAdmission(app,1)
        first=asyncio.create_task(middleware({'type':'http','path':'/api/v1/users/me'},None,None))
        await entered.wait()
        await asyncio.wait_for(middleware({'type':'http','path':'/health'},None,None),.1)
        assert health.is_set()
        first.cancel()
        try:await first
        except asyncio.CancelledError:pass
        release.set()
        await asyncio.wait_for(middleware({'type':'http','path':'/api/v1/users/me'},None,None),.1)
    asyncio.run(run())
