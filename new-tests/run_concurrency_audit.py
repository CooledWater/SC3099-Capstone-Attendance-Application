"""Run only in a disposable backend database; creates 100 test accounts."""
import asyncio,uuid,json,time,statistics,os
from pathlib import Path
from datetime import datetime,timedelta
from sqlalchemy import inspect,text
from app.database import SessionLocal,engine
from app.models import User,Course,Session,Enrollment,CheckIn
from app.auth import create_access_token
import httpx
if os.getenv('SAIV_AUDIT_DISPOSABLE_DATABASE') != '1':
 raise SystemExit('Set SAIV_AUDIT_DISPOSABLE_DATABASE=1 only for an isolated disposable database')
if not os.getenv('SAIV_AUDIT_BACKEND_URL'):
 raise SystemExit('Set SAIV_AUDIT_BACKEND_URL explicitly to the isolated backend')
if 'supabase' in os.getenv('DATABASE_URL','').lower():
 raise SystemExit('Refusing to load-test Supabase')
suffix=uuid.uuid4().hex[:8]
with SessionLocal() as db:
 teacher=User(email=f'audit-teacher-{suffix}@example.test',full_name='Audit Teacher',role='instructor',hashed_password='not-used');db.add(teacher);db.flush()
 course=Course(code='AUD'+suffix,name='Disposable stress audit',semester='audit',instructor_id=teacher.id,venue_latitude=1.3483,venue_longitude=103.6831,geofence_radius_meters=100)
 db.add(course);db.flush();now=datetime.utcnow()
 session=Session(course_id=course.id,instructor_id=teacher.id,name='100-user stress audit',status='active',scheduled_start=now-timedelta(minutes=1),scheduled_end=now+timedelta(hours=1),checkin_opens_at=now-timedelta(minutes=1),checkin_closes_at=now+timedelta(hours=1),require_liveness_check=False,require_face_match=False)
 db.add(session);db.flush();users=[]
 for i in range(100):
  u=User(email=f'audit-{suffix}-{i}@example.test',full_name='Audit Student',role='student',hashed_password='not-used',camera_consent=True,geolocation_consent=True);db.add(u);db.flush();db.add(Enrollment(student_id=u.id,course_id=course.id));users.append((u.id,create_access_token(u.id,'student')))
 sid=session.id;db.commit()
async def run():
 async with httpx.AsyncClient(base_url=os.environ['SAIV_AUDIT_BACKEND_URL'],timeout=60,limits=httpx.Limits(max_connections=110,max_keepalive_connections=110)) as c:
  async def request(i,method,path,payload=None):
   start=time.monotonic()
   try:
    r=await c.request(method,path,headers={'Authorization':'Bearer '+users[i%100][1]},json=payload)
    return {'status':r.status_code,'seconds':time.monotonic()-start,'detail':r.text[:150] if r.status_code>=400 else ''}
   except Exception as e:return {'status':'error','seconds':time.monotonic()-start,'detail':str(e)}
  def summary(rows):
   values=sorted(x['seconds'] for x in rows);return {'requests':len(rows),'statuses':{str(code):sum(x['status']==code for x in rows) for code in set(x['status'] for x in rows)},'p95_seconds':round(values[int(.95*(len(values)-1))],3),'max_seconds':round(max(values),3),'errors':[x for x in rows if x['status'] not in [200,201]][:3]}
  out={}
  out['100_concurrent_reads']=summary(await asyncio.gather(*(request(i,'GET','/api/v1/users/me') for i in range(100))))
  payload={'session_id':sid,'latitude':1.3483,'longitude':103.6831,'device_fingerprint':'audit'}
  out['100_concurrent_checkins']=summary(await asyncio.gather(*(request(i,'POST','/api/v1/checkins/',payload) for i in range(100))))
  out['duplicate_replay']=summary(await asyncio.gather(*(request(0,'POST','/api/v1/checkins/',payload) for i in range(10))))
  # Probe invalid numeric data without touching shared application data.
  for field,value in [('location_accuracy_meters',-1),('latitude',float('nan'))]:
   p={**payload,field:value}
   raw=json.dumps(p)
   r=await c.post('/api/v1/checkins/',content=raw,headers={'Authorization':'Bearer '+users[0][1],'Content-Type':'application/json'})
   out[field+'_invalid_status']=r.status_code
  print(json.dumps(out,indent=2));open(Path(os.getenv('AUDIT_RESULTS_DIR','/tmp'))/'stress-results.json','w').write(json.dumps(out,indent=2))
asyncio.run(run())
