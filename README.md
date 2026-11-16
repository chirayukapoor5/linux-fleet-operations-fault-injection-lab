# FleetOps Core — Linux Fleet Operations & Fault Injection SRE Lab

A functional, API-backed **isolated SRE training simulator** built from the original five-tab HTML prototype. It models four virtual nodes labelled after example Hetzner and Verda infrastructure; **it does not connect to those companies' infrastructure**, provision Proxmox/KVM VMs, open SSH connections, or manipulate production systems.

## Capabilities

- Fleet status cards with CPU, RAM, disk, temperature, packet loss, service health, 5-second polling.
- Four repeatable fault scenarios: storage failure, packet loss/MTU mismatch, resource exhaustion/OOM, and application service crash.
- Incident ticket creation, severity, diagnosis, corrective guidance, recovery verification and persistent history.
- Read-only *emulated* terminal diagnostics, explicitly allowlisted; never executes user-supplied shell commands.
- JSON fleet health sweeps, Prometheus metrics endpoint, SQLite data persistence, pytest integration tests, GitHub Actions CI.
- Local-only port binding and unprivileged Docker container with dropped Linux capabilities.

## Quick start

```bash
docker compose up --build
```

Open http://localhost:8000 for the dashboard, http://localhost:8000/docs for API documentation and http://localhost:9090 for Prometheus. The Docker image installs Python dependencies and runs as an unprivileged user; no Docker socket is mounted.

Without Docker:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
pytest -q
```

## Reproducible incident demo

```bash
curl -s -X POST http://localhost:8000/api/faults -H 'Content-Type: application/json' \
 -d '{"node_id":"node-hetzner-01","fault_type":"disk"}'
curl -s http://localhost:8000/api/health-check
curl -s http://localhost:8000/metrics
```

Resolve the returned incident with `POST /api/incidents/{id}/resolve`, or use the UI. This returns simulated telemetry to baseline and verifies the simulated recovery. Only one active fault per node is allowed; duplicates return 409.

## API

| Endpoint | Description |
| --- | --- |
| `GET /api/state` | Nodes, tickets, logs |
| `POST /api/faults` | Inject an isolated fault |
| `POST /api/incidents/{id}/resolve` | Recover and verify incident |
| `POST /api/reset` | Clear incidents and reset fleet |
| `POST /api/diagnostics` | Allowlisted simulated diagnostics |
| `GET /api/health-check` | JSON health sweep |
| `GET /metrics` | Prometheus exposition |

## Scope and honest limitations

**Simulation, not hardware chaos:** disk SMART, kernel logs, service states, CPU pressure and network drops are modeled in SQLite, not sampled from Linux hosts. The original HTML health-check code block remains as a historical visual example; pressing Run now requests live application state from the backend. Prometheus *actually scrapes* the application's simulated-state metrics, but Grafana, real Linux exporters, hypervisor API connectors, container fault drivers and privileged host-level chaos tooling are **not implemented**. The labels Hetzner / Verda are illustrative, not claims of access or affiliation.

For a future real infrastructure mode: use explicit node enrollment, mTLS, least-privilege agents, authorization for destructive operations, execution audit trails and strict resource guardrails. Never inject faults into third-party hosts.
