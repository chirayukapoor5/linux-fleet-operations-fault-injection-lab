"""Filesystem mirror SIMULATION; never confuse with actual mdadm RAID1."""
import hashlib, json, os, shutil, threading, time, uuid
from pathlib import Path
from datetime import datetime, timezone
def utc(): return datetime.now(timezone.utc).isoformat()
def sha(data): return hashlib.sha256(data).hexdigest()
class MirrorLab:
    def __init__(self, root):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
        self.disks=[self.root/'disk_a',self.root/'disk_b']
        for d in self.disks:(d/'objects').mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.failed=set();self.events=[]
        self.started=time.monotonic();self.failure_at=None;self.detected_at=None
        self.rebuild_duration=None;self.rebuild_progress=0.;self.rebuilding=False
        self.attempts=0;self.acks=0;self.errors=0;self.duplicates=0
        self.reads=0;self.read_errors=0;self.latencies=[];self.rebuild_thread=None
        self.log_path=self.root/'events.jsonl';self.emit('lab_started',mode='filesystem_mirror_simulation')
    def emit(self,event,**fields):
        row={'timestamp':utc(),'elapsed_s':round(time.monotonic()-self.started,3),'event':event,**fields}
        self.events.append(row)
        with self.log_path.open('a') as f:f.write(json.dumps(row)+'\n')
        return row
    def _object(self,disk,key):return self.disks[disk]/'objects'/(key+'.json')
    def _put(self,disk,key,data):
        dest=self._object(disk,key);tmp=dest.with_name(dest.name+'.'+uuid.uuid4().hex+'.tmp')
        with tmp.open('wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,dest)
    def submit(self,student,exam,answer,request_id,kind='final'):
        t=time.monotonic()
        with self.lock:
            self.attempts+=1
            key=sha(f'{student}|{exam}|{request_id}'.encode())
            for i in range(2):
                if i not in self.failed and self._object(i,key).exists():
                    obj=json.loads(self._object(i,key).read_bytes());self.duplicates+=1
                    self.latencies.append(time.monotonic()-t)
                    return {'receipt':obj['receipt'],'digest':obj['digest'],'duplicate':True}
            payload={'student':student,'exam':exam,'answer':answer,'request_id':request_id,'kind':kind}
            digest=sha(json.dumps(payload,sort_keys=True).encode())
            doc={'payload':payload,'digest':digest,'receipt':uuid.uuid4().hex,'time':utc()}
            raw=json.dumps(doc,sort_keys=True).encode();successes=0
            for i in range(2):
                if i not in self.failed:
                    try:self._put(i,key,raw);successes+=1
                    except OSError as exc:self.emit('write_error',disk=i,error=str(exc))
            if not successes:
                self.errors+=1;self.latencies.append(time.monotonic()-t)
                raise OSError('both simulated storage replicas unavailable')
            self.acks+=1;self.latencies.append(time.monotonic()-t)
            return {'receipt':doc['receipt'],'digest':digest,'duplicate':False}
    def read(self,student,exam,request_id):
        with self.lock:
            self.reads+=1;key=sha(f'{student}|{exam}|{request_id}'.encode())
            for i in range(2):
                if i in self.failed:continue
                p=self._object(i,key)
                if p.exists():
                    obj=json.loads(p.read_bytes())
                    if sha(json.dumps(obj['payload'],sort_keys=True).encode())!=obj['digest']:
                        self.emit('integrity_error',disk=i,key=key);continue
                    return obj
            self.read_errors+=1;raise FileNotFoundError(key)
    def fail(self,disk=1):
        with self.lock:
            if disk not in (0,1):raise ValueError('disk must be 0 or 1')
            if disk in self.failed:return False
            self.failed.add(disk);self.failure_at=time.monotonic();self.detected_at=None
            self.emit('disk_failure_injected',disk='disk_'+str(disk));return True
    def poll(self):
        with self.lock:
            if self.failed and self.detected_at is None:
                self.detected_at=time.monotonic()
                self.emit('alert_RAID_DEGRADED',detection_latency_s=round(self.detected_at-self.failure_at,3))
    def recover(self,disk=1,copy_delay=.003):
        with self.lock:
            if disk not in self.failed:raise ValueError('disk not failed')
            if len(self.failed)>1:raise RuntimeError('no healthy source')
            if self.rebuilding:raise RuntimeError('rebuild already in progress')
            self.rebuilding=True;self.rebuild_progress=0;self.emit('rebuild_started',disk=disk)
        def job():
            start=time.monotonic();src=1-disk;target=self.disks[disk]/'objects'
            objects=list((self.disks[src]/'objects').glob('*.json'))
            for idx,p in enumerate(objects):
                with self.lock:
                    if p.exists():shutil.copy2(p,target/p.name)
                    self.rebuild_progress=(idx+1)/max(len(objects),1)*95
                time.sleep(copy_delay)
            with self.lock:
                for p in (self.disks[src]/'objects').glob('*.json'):
                    dest=target/p.name
                    if not dest.exists() or sha(dest.read_bytes())!=sha(p.read_bytes()):shutil.copy2(p,dest)
                self.failed.remove(disk);self.rebuilding=False;self.rebuild_progress=100
                self.rebuild_duration=time.monotonic()-start
                self.emit('rebuild_complete',duration_s=round(self.rebuild_duration,3),verified=self.verify()['matches'])
        self.rebuild_thread=threading.Thread(target=job,daemon=True);self.rebuild_thread.start()
    def verify(self):
        with self.lock:
            a={p.name:sha(p.read_bytes()) for p in (self.disks[0]/'objects').glob('*.json')}
            b={p.name:sha(p.read_bytes()) for p in (self.disks[1]/'objects').glob('*.json')}
            active=[i for i in range(2) if i not in self.failed]
            mismatches=[] if len(active)<2 else sorted(k for k in (a.keys()|b.keys()) if a.get(k)!=b.get(k))
            return {'matches':len(active)==2 and not mismatches,'disk_a_objects':len(a),'disk_b_objects':len(b),'mismatch_count':len(mismatches),'mismatch_ids':mismatches[:20]}
    def status(self):
        with self.lock:
            return {'mode':'filesystem_mirror_simulation','raid_state':'rebuilding' if self.rebuilding else ('degraded' if self.failed else 'healthy'),
                'healthy_disks':2-len(self.failed),'failed_disks':sorted(self.failed),'rebuild_progress_pct':round(self.rebuild_progress,2),
                'detection_latency_s':round(self.detected_at-self.failure_at,3) if self.detected_at and self.failure_at else None,
                'rebuild_duration_s':round(self.rebuild_duration,3) if self.rebuild_duration is not None else None,
                'attempts':self.attempts,'acknowledged':self.acks,'write_errors':self.errors,'duplicate_requests':self.duplicates,
                'reads':self.reads,'read_errors':self.read_errors,
                'p95_write_latency_ms':round(sorted(self.latencies)[int((len(self.latencies)-1)*.95)]*1000,3) if self.latencies else 0,'events':self.events[-40:]}
