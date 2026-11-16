"""FleetOps SRE training lab: persistent, isolated fault simulation API."""
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

DB = os.environ.get('FLEETOPS_DB', '/tmp/fleetops.sqlite3')
app = FastAPI(title='FleetOps SRE Lab', version='1.0.0', description='Isolated simulation: no production hosts or privileged commands are accessed.')
lock = threading.RLock()
BASE = [
    ('node-hetzner-01', 'Hetzner Dedicated (AX101)', 'Proxmox VE 8.1', 18, 42, 65, 44),
    ('node-hetzner-02', 'Hetzner Dedicated (EX44)', 'KVM / QEMU', 24, 58, 78, 48),
    ('node-verda-store', 'Verda Cloud NVMe Store', 'Proxmox VE 8.1', 31, 70, 89, 52),
    ('node-verda-edge', 'Verda Cloud Edge Proxy', 'KVM / QEMU', 15, 34, 42, 41),
]
FAULTS = {
    'disk': ('NVMe Sector Reallocation Failure', 'SEV-1', 'Storage / Hardware', 'SMART predictive failure; simulated block I/O errors', ['Inspect smartctl output', 'Review dmesg I/O errors', 'Plan storage replacement'], ['SMART check passes', 'No new disk I/O errors']),
    'network': ('Interface Flapping & MTU Packet Drop', 'SEV-2', 'Network', 'Simulated packet loss due to MTU mismatch', ['Inspect ip link and route', 'Verify MTU settings', 'Check connectivity'], ['Packet loss is zero', 'Link state is healthy']),
    'resource': ('OOM Killer Invoked & Inode Exhaustion', 'SEV-1', 'Resource Exhaustion', 'Simulated memory and inode exhaustion', ['Inspect top and df -i', 'Locate pressure source', 'Limit failing workload'], ['CPU and memory return to safe values', 'Inodes are available']),
    'service': ('PostgreSQL & Nginx Service Crash', 'SEV-2', 'Application Services', 'Simulated systemd service failures', ['Inspect journalctl', 'Check service configuration', 'Restart affected services'], ['Services are active', 'Health endpoint passes']),
}

@contextmanager
def db():
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()

def now():
    return datetime.now(timezone.utc).isoformat()

def seed(c):
    c.execute('CREATE TABLE IF NOT EXISTS nodes (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS incidents (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, node TEXT, level TEXT, msg TEXT)')
    if not c.execute('SELECT 1 FROM nodes LIMIT 1').fetchone():
        for name, provider, hypervisor, cpu, ram, disk, temp in BASE:
            n = dict(id=name, name=name, provider=provider, hypervisor=hypervisor, cpu=cpu, ram=ram, disk=disk, temp=temp, packetLoss=0, status='HEALTHY', activeFault=None, services={k: 'active' for k in ('postgresql', 'nginx', 'prometheus', 'sshd')})
            c.execute('INSERT INTO nodes VALUES (?,?)', (name, json.dumps(n)))

def init():
    Path(DB).parent.mkdir(parents=True, exist_ok=True)
    with lock, db() as c: seed(c)

init()
app.mount('/static', StaticFiles(directory=Path(__file__).parent), name='static')

def get_node(c, name):
    row = c.execute('SELECT data FROM nodes WHERE id=?', (name,)).fetchone()
    if row is None: raise HTTPException(404, 'Node not found')
    return json.loads(row['data'])

def save_node(c, node):
    c.execute('UPDATE nodes SET data=? WHERE id=?', (json.dumps(node), node['id']))

def log(c, node, level, message):
    c.execute('INSERT INTO logs(time,node,level,msg) VALUES (?,?,?,?)', (now(), node, level, message))

class FaultRequest(BaseModel):
    node_id: str
    fault_type: str

class DiagnosticRequest(BaseModel):
    node_id: str
    command: str = Field(min_length=1, max_length=180)

@app.get('/', response_class=HTMLResponse)
def home():
    return Path(__file__).with_name('index.html').read_text(encoding='utf8')

@app.get('/api/state')
def state():
    with lock, db() as c:
        return dict(nodes=[json.loads(r['data']) for r in c.execute('SELECT data FROM nodes ORDER BY rowid')], incidents=[json.loads(r['data']) for r in c.execute('SELECT data FROM incidents ORDER BY rowid DESC')], logs=[dict(time=r['time'], node=r['node'], level=r['level'], msg=r['msg']) for r in c.execute('SELECT time,node,level,msg FROM logs ORDER BY id DESC LIMIT 50')])

@app.post('/api/faults', status_code=201)
def fault(body: FaultRequest):
    if body.fault_type not in FAULTS: raise HTTPException(422, 'Unknown fault type')
    with lock, db() as c:
        node = get_node(c, body.node_id)
        if node['activeFault']: raise HTTPException(409, 'Node already has an active fault; recover it first')
        title, sev, category, diagnosis, actions, verification = FAULTS[body.fault_type]
        node['activeFault'] = dict(type=body.fault_type, name=title)
        node['status'] = 'CRITICAL' if sev == 'SEV-1' else 'DEGRADED'
        if body.fault_type == 'disk': node.update(disk=98, temp=69)
        if body.fault_type == 'network': node['packetLoss'] = 45.5
        if body.fault_type == 'resource': node.update(cpu=99, ram=96, disk=100)
        if body.fault_type == 'service': node['services'].update(postgresql='failed', nginx='failed')
        save_node(c, node)
        incident = dict(id='INC-' + uuid4().hex[:10].upper(), title=title, node=body.node_id, severity=sev, category=category, status='Open', time=now(), diagnosis=diagnosis, actions=actions, verification=verification)
        c.execute('INSERT INTO incidents VALUES (?,?)', (incident['id'], json.dumps(incident)))
        log(c, body.node_id, 'ERROR', 'Injected simulated fault: ' + title)
        return incident

@app.post('/api/incidents/{incident_id}/resolve')
def resolve(incident_id: str):
    with lock, db() as c:
        row = c.execute('SELECT data FROM incidents WHERE id=?', (incident_id,)).fetchone()
        if row is None: raise HTTPException(404, 'Incident not found')
        inc = json.loads(row['data'])
        if inc['status'] == 'Resolved': return inc
        node = get_node(c, inc['node'])
        if not node['activeFault']: raise HTTPException(409, 'Active fault no longer matches incident')
        # Recovery explicitly clears the *simulated* fault before checking simulated service health.
        node['activeFault'] = None
        original = next(b for b in BASE if b[0] == node['id'])
        node.update(cpu=original[3], ram=original[4], disk=original[5], temp=original[6], packetLoss=0, status='HEALTHY', services={k: 'active' for k in node['services']})
        if any(s != 'active' for s in node['services'].values()) or node['packetLoss'] > 0:
            raise HTTPException(409, 'Recovery verification failed')
        save_node(c, node)
        inc['status'] = 'Resolved'
        inc['resolved_at'] = now()
        c.execute('UPDATE incidents SET data=? WHERE id=?', (json.dumps(inc), inc['id']))
        log(c, node['id'], 'INFO', 'Simulation recovery verified; incident ' + inc['id'] + ' resolved')
        return inc

@app.post('/api/reset')
def reset():
    with lock, db() as c:
        c.execute('DELETE FROM nodes')
        c.execute('DELETE FROM incidents')
        seed(c)
        log(c, 'SYSTEM', 'INFO', 'Simulation fleet reset')
    return {'ok': True}

@app.get('/api/health-check')
def health_check():
    s = state()
    results = [dict(node=n['id'], status=n['status'], cpu=n['cpu'], ram=n['ram'], disk=n['disk'], smart_status='WARNING' if n['activeFault'] and n['activeFault']['type'] == 'disk' else 'PASSED', services=n['services']) for n in s['nodes']]
    return {'time': now(), 'mode': 'simulation', 'healthy': all(r['status'] == 'HEALTHY' for r in results), 'results': results}

@app.post('/api/diagnostics')
def diagnostics(body: DiagnosticRequest):
    with lock, db() as c: n = get_node(c, body.node_id)
    cmd = ' '.join(body.command.strip().split())
    fault_type = n['activeFault']['type'] if n['activeFault'] else None
    # Intentionally an allowlisted, read-only diagnostic emulator; NO shell execution.
    if cmd in ('help',): out = 'Allowed: help, top, htop, df -h, df -i, smartctl -a /dev/sda, journalctl -u nginx, journalctl -u postgresql, dmesg -T, ss -tulpn, ip route, ip link, ethtool eth0, ping -c 4 8.8.8.8, traceroute 8.8.8.8'
    elif cmd in ('top', 'htop'): out = f"top (simulated) | CPU {n['cpu']}% | RAM {n['ram']}%" + (' | OOM killer invoked' if fault_type == 'resource' else '')
    elif cmd in ('df -h', 'df -i'): out = f"Filesystem /dev/nvme0n1p2 | Usage {n['disk']}%" + (' | inode exhaustion' if fault_type == 'resource' else '')
    elif cmd == 'smartctl -a /dev/sda': out = 'SMART overall-health: ' + ('WARNING: sector reallocation and I/O errors' if fault_type == 'disk' else 'PASSED')
    elif cmd in ('journalctl -u nginx', 'journalctl -u postgresql'): out = ('systemd: service failed (simulated)' if fault_type == 'service' else 'systemd: service active (simulated)')
    elif cmd == 'dmesg -T': out = 'kernel: ' + ('I/O errors' if fault_type == 'disk' else 'OOM killer invoked' if fault_type == 'resource' else 'no critical events')
    elif cmd == 'ss -tulpn': out = 'LISTEN tcp 0.0.0.0:22 sshd\nLISTEN tcp 0.0.0.0:80 nginx' if n['services']['nginx'] == 'active' else 'LISTEN tcp 0.0.0.0:22 sshd'
    elif cmd == 'ip route': out = 'default via 10.0.0.1 dev eth0'
    elif cmd == 'ip link': out = 'eth0: UP mtu ' + ('9000 (mismatch)' if fault_type == 'network' else '1500')
    elif cmd == 'ethtool eth0': out = 'Link detected: yes\nRX packet loss: ' + str(n['packetLoss']) + '%'
    elif cmd == 'ping -c 4 8.8.8.8': out = f"4 packets transmitted; loss {n['packetLoss']}% (simulated)"
    elif cmd == 'traceroute 8.8.8.8': out = '1 10.0.0.1\n2 8.8.8.8 (simulated)'
    else: raise HTTPException(400, 'Command not allowed. Type help to see supported read-only commands.')
    return {'node': n['id'], 'command': cmd, 'mode': 'simulation', 'output': out}

@app.get('/metrics', response_class=PlainTextResponse)
def metrics():
    s = state()
    rows = ['# HELP fleetops_node_up Node has no active simulated fault', '# TYPE fleetops_node_up gauge']
    for n in s['nodes']:
        label = '{node="' + n['id'] + '"}'
        rows.extend((f"fleetops_node_up{label} {int(n['status'] == 'HEALTHY')}", f"fleetops_node_cpu_percent{label} {n['cpu']}", f"fleetops_node_ram_percent{label} {n['ram']}", f"fleetops_node_disk_percent{label} {n['disk']}"))
    rows.append(f"fleetops_incidents_open {sum(i['status'] == 'Open' for i in s['incidents'])}")
    return '\n'.join(rows) + '\n'
