import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from prometheus_client import CollectorRegistry, Gauge, generate_latest, CONTENT_TYPE_LATEST
from .core import MirrorLab
lab=MirrorLab(os.environ.get('EXAMSHIELD_DATA','./runtime'))
app=FastAPI(title='ExamShield LMS Incident Lab',version='1.0.0')
class Submission(BaseModel):
    student:str=Field(min_length=1,max_length=100)
    exam:str=Field(min_length=1,max_length=100)
    answer:str=Field(min_length=1,max_length=20000)
    request_id:str=Field(min_length=1,max_length=100)
    kind:str='final'
class Fail(BaseModel):disk:int=1
@app.get('/health')
def health():
    s=lab.status()
    if s['healthy_disks']==0:raise HTTPException(503,'storage unavailable')
    return {'ok':True,'storage_state':s['raid_state']}
@app.post('/api/submit')
def submit(p:Submission):
    try:return lab.submit(**p.model_dump())
    except OSError as e:raise HTTPException(503,str(e))
@app.get('/api/read/{student}/{exam}/{request_id}')
def read(student:str,exam:str,request_id:str):
    try:return lab.read(student,exam,request_id)
    except FileNotFoundError:raise HTTPException(404,'record not found')
@app.get('/api/status')
def status():return lab.status()
@app.get('/api/verify')
def verify():return lab.verify()
@app.post('/admin/fail')
def fail(body:Fail):
    try:return {'changed':lab.fail(body.disk),'status':lab.status()}
    except ValueError as e:raise HTTPException(400,str(e))
@app.post('/admin/rebuild')
def rebuild(body:Fail):
    try:lab.recover(body.disk);return {'started':True}
    except (ValueError,RuntimeError) as e:raise HTTPException(400,str(e))
@app.post('/admin/poll')
def poll():lab.poll();return lab.status()
@app.get('/metrics')
def metrics():
    s=lab.status();r=CollectorRegistry()
    for n,h,v in [('examshield_raid_healthy_disks','Healthy simulated replicas',s['healthy_disks']),
      ('examshield_raid_degraded','Mirrored storage is degraded',int(s['healthy_disks']<2)),
      ('examshield_submissions_acknowledged_total','Accepted submissions',s['acknowledged']),
      ('examshield_submission_errors_total','Submission errors',s['write_errors']),
      ('examshield_duplicate_requests_total','Idempotent retries',s['duplicate_requests']),
      ('examshield_rebuild_progress_percent','Rebuild progress',s['rebuild_progress_pct']),
      ('examshield_rebuild_duration_seconds','Rebuild duration',s['rebuild_duration_s'] or 0),
      ('examshield_detection_latency_seconds','Detection latency',s['detection_latency_s'] or 0)]:
        Gauge(n,h,registry=r).set(v)
    return Response(generate_latest(r),media_type=CONTENT_TYPE_LATEST)
@app.get('/',response_class=HTMLResponse)
def dashboard():
    from pathlib import Path
    return Path(__file__).with_name('dashboard.html').read_text()
