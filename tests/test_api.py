import os
import tempfile

fd, db_path = tempfile.mkstemp(suffix='.sqlite3')
os.close(fd)
os.unlink(db_path)
os.environ['FLEETOPS_DB'] = db_path
from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)

def setup_function():
    assert client.post('/api/reset').status_code == 200

def test_initial_fleet():
    s = client.get('/api/state').json()
    assert len(s['nodes']) == 4
    assert all(n['status'] == 'HEALTHY' for n in s['nodes'])
    assert client.get('/api/health-check').json()['healthy']

def test_all_faults_and_recovery():
    for index, fault in enumerate(('disk', 'network', 'resource', 'service')):
        name = client.get('/api/state').json()['nodes'][index]['id']
        response = client.post('/api/faults', json={'node_id': name, 'fault_type':fault})
        assert response.status_code == 201
        inc = response.json()
        assert inc['status'] == 'Open'
        assert client.post('/api/faults', json={'node_id':name, 'fault_type':fault}).status_code == 409
        assert not client.get('/api/health-check').json()['healthy']
        resolution = client.post(f"/api/incidents/{inc['id']}/resolve")
        assert resolution.status_code == 200
        assert resolution.json()['status'] == 'Resolved'
    assert client.get('/api/health-check').json()['healthy']
    assert 'fleetops_incidents_open 0' in client.get('/metrics').text

def test_validation_and_safe_terminal():
    assert client.post('/api/faults', json={'node_id':'missing', 'fault_type':'disk'}).status_code == 404
    assert client.post('/api/faults', json={'node_id':'node-hetzner-01', 'fault_type':'invalid'}).status_code == 422
    assert client.post('/api/diagnostics', json={'node_id':'node-hetzner-01','command':'rm -rf /'}).status_code == 400
    assert client.post('/api/diagnostics', json={'node_id':'node-hetzner-01','command':'top'}).json()['mode'] == 'simulation'
    assert client.post('/api/incidents/missing/resolve').status_code == 404

def test_reset_clears_incidents():
    client.post('/api/faults', json={'node_id':'node-hetzner-01','fault_type':'disk'})
    client.post('/api/reset')
    assert client.get('/api/state').json()['incidents'] == []
