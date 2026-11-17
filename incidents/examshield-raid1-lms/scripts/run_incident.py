#!/usr/bin/env python3
"""Measured integration: live LMS traffic, injected replica fault, alert and repair."""
import argparse,json,sys,threading,time
from pathlib import Path
from datetime import datetime,timezone
import requests
p=argparse.ArgumentParser()
p.add_argument('--url',default='http://127.0.0.1:8765')
p.add_argument('--students',type=int,default=80)
p.add_argument('--seconds',type=float,default=10)
p.add_argument('--out',default='evidence')
args=p.parse_args()
out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
stop=threading.Event();lock=threading.Lock();responses=[];probes=[];timeline=[]
start=time.monotonic();counter=0
def api(path,method='GET',data=None):return requests.request(method,args.url+path,json=data,timeout=10)
def event(name):timeline.append({'name':name,'elapsed_s':round(time.monotonic()-start,3),'utc':datetime.now(timezone.utc).isoformat()})
def worker():
    global counter
    while not stop.is_set():
        with lock:i=counter;counter+=1
        payload={'student':f'STUDENT-{i%args.students:04d}','exam':'DATA-STRUCTURES-FINAL','answer':f'Autosave {i}','request_id':f'autosave-{i:08d}','kind':'autosave'}
        try:
            r=api('/api/submit','POST',payload);code=r.status_code
        except requests.RequestException:code=0
        with lock:responses.append(code)
        time.sleep(.02)
def health():
    while not stop.is_set():
        try:code=api('/health').status_code
        except requests.RequestException:code=0
        with lock:probes.append({'elapsed_s':round(time.monotonic()-start,3),'status':code})
        time.sleep(.075)
def monitor():
    while not stop.is_set():
        try:api('/admin/poll','POST')
        except requests.RequestException:pass
        time.sleep(.15)
threads=[threading.Thread(target=worker,daemon=True) for _ in range(5)]+[threading.Thread(target=health,daemon=True),threading.Thread(target=monitor,daemon=True)]
event('workload_started')
for t in threads:t.start()
time.sleep(max(1,args.seconds*.22))
event('disk_failure_requested');api('/admin/fail','POST',{'disk':1}).raise_for_status()
time.sleep(max(1,args.seconds*.20))
payload={'student':'STUDENT-0001','exam':'DATA-STRUCTURES-FINAL','answer':'Final answer A=42','request_id':'network-timeout-retry','kind':'final'}
event('retry_test')
first=api('/api/submit','POST',payload);second=api('/api/submit','POST',payload)
idempotent=first.ok and second.ok and first.json()['receipt']==second.json()['receipt'] and second.json()['duplicate']
event('rebuild_requested');api('/admin/rebuild','POST',{'disk':1}).raise_for_status()
deadline=time.monotonic()+max(90,args.seconds*10)
while time.monotonic()<deadline:
    state=api('/api/status').json()
    if state['raid_state']=='healthy' and state['rebuild_duration_s'] is not None:break
    time.sleep(.06)
else:raise RuntimeError('rebuild timeout')
event('rebuild_finished')
time.sleep(max(.5,args.seconds*.15));stop.set()
for t in threads:t.join(timeout=3)
state=api('/api/status').json();check=api('/api/verify').json()
read=api('/api/read/STUDENT-0001/DATA-STRUCTURES-FINAL/network-timeout-retry')
read_ok=first.ok and read.ok and first.json()['digest']==read.json()['digest']
ok=sum(x==200 for x in responses);up=sum(x['status']==200 for x in probes)
metrics={'scenario':'University LMS exam with autosaves and idempotent retries','execution_mode':'filesystem mirror simulation, NOT mdadm','students':args.students,
'duration_s':round(time.monotonic()-start,3),'workload_requests':len(responses),'successful_workload_requests':ok,
'failed_workload_requests':len(responses)-ok,'workload_success_rate_pct':round(ok*100/len(responses),3) if responses else None,
'health_probes':len(probes),'successful_health_probes':up,
'sampled_health_availability_pct':round(up*100/len(probes),3) if probes else None,
'detection_latency_s':state['detection_latency_s'],'rebuild_duration_s':state['rebuild_duration_s'],
'acknowledged_writes':state['acknowledged'],'duplicate_retries':state['duplicate_requests'],
'idempotent_retry_verified':bool(idempotent),'receipt_readback_verified':bool(read_ok),
'checksum_replicas_match':check['matches'],'checksum_mismatch_count':check['mismatch_count'],
'replica_a_objects':check['disk_a_objects'],'replica_b_objects':check['disk_b_objects'],
'p95_write_latency_ms':state['p95_write_latency_ms'],'final_state':state['raid_state']}
for name,data in [('metrics.json',metrics),('timeline.json',timeline),('health_probes.json',probes),('checksum_results.json',check)]:
    (out/name).write_text(json.dumps(data,indent=2)+'\n')
report='# ExamShield incident report\n\nFilesystem mirror simulation (not mdadm).\n\n'+ '\n'.join(f'- **{k}:** {v}' for k,v in metrics.items())+'\n'
(out/'incident_report.md').write_text(report)
print(json.dumps(metrics,indent=2))
if not (check['matches'] and idempotent and read_ok and state['raid_state']=='healthy'):sys.exit(2)
