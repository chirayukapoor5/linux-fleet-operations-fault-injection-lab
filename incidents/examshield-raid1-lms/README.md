# ExamShield — RAID1 Failure During a Live University LMS Examination

**Measured fault-injection lab | FastAPI · Python · Prometheus · Grafana · Linux mdadm (separate Ubuntu VM path)**

During a campus-wide final exam, students continuously autosave answers, submit finals, and retry responses after network timeouts. At the worst moment, one storage replica fails. This lab measures the availability, durability, alert delay, and recovery behaviour of a simplified educational LMS.

## Critical honesty about execution modes

1. **Safe, portable simulation (tested here):** Two directories represent mirrored storage devices. One can be disabled while FastAPI receives real HTTP requests. Mirror recovery copies files and reconciles concurrent writes. These are *not* Linux RAID1 block devices, and the logs do *not* establish `mdadm` resiliency.
2. **Actual Linux RAID1 (Ubuntu VM, not executed in this environment):** `scripts/real_mdadm_ubuntu.sh` creates an mdadm RAID1 with two scratch loop files, runs a background read/write process, marks one disk failed, replaces it with a third, monitors `/proc/mdstat`, and captures kernel and checksum logs. Run **only on an isolated disposable Ubuntu VM**; `mdadm` and loop devices and privileges are required.

## Scenario: finals-week autosave + ambiguous acknowledgments

A network timeout during exam submission is not equivalent to data loss. If a student retries the same request ID, the LMS should return the **original receipt** rather than create an inconsistent duplicate. Our test deliberately retries one final submission during the degraded state and verifies both identity and readback after rebuilding.

## Run the simulated incident

```bash
python -m pip install -r requirements.txt
uvicorn examshield.server:app --host 127.0.0.1 --port 8765
# In another shell:
python scripts/run_incident.py --students 80 --seconds 10 --out evidence
pytest -q
```

Dashboard: http://localhost:8765 · Prometheus endpoint: http://localhost:8765/metrics.

To run Grafana + Prometheus (requires Docker):

```bash
docker compose up --build -d
# LMS http://localhost:8765 · Prometheus http://localhost:9090 · Grafana http://localhost:3000
```

The simulator's `/admin/fail` and `/admin/rebuild` endpoints are **deliberately unauthenticated** for localhost lab use; do not expose this service on public networks.

## Generate actual mdadm evidence on Ubuntu (separate run)

```bash
sudo apt-get update && sudo apt-get install -y mdadm e2fsprogs util-linux
sudo I_ACCEPT_SCRATCH_RAID=YES bash scripts/real_mdadm_ubuntu.sh
```

This Linux script manipulates virtual block devices and requires privileges. Verify the `/dev/md/examshield-lab` array is unused before running. It is not integrated with the HTTP LMS workload; for real service-over-RAID evidence, mount your application's data directory on the mdadm array and configure a dedicated deployment.

## Evidence directories

`evidence/metrics.json` — measured outcomes; `timeline.json` — phase timeline; `health_probes.json` — all HTTP probes; `checksum_results.json` — post-rebuild SHA-256 check; `incident_report.md` — incident write-up; `events.jsonl` — failure, alert and recovery audit events; `availability_timeline.png` and `recovery_metrics.png` — charts generated from observed run data. Live dashboard screenshot was not available because the browser environment blocked localhost; this is not a Grafana screenshot.

## Investigation runbook

On a real Ubuntu VM: `cat /proc/mdstat`, `sudo mdadm --detail /dev/md/examshield-lab`, `sudo dmesg --ctime | tail -100`, `systemctl status <your-lms-service>`, `sha256sum <sample-files>`. Correlate RAID degraded state with Prometheus alerts, client probe results, recovery duration, and final checksum verification.

## Known boundaries

- Failover in a directory mirror is not a faithful emulation of Linux RAID1 scheduling, disk I/O, or filesystem semantics.
- The sample checksum comparison is of two *simulation replicas* and does not verify physical disks or silent preexisting corruption.
- Sampled health availability is not end-user availability nor proof of a production service SLA.
- The real mdadm path does not yet integrate an LMS service; it independently validates block-layer rebuilds.
- Docker/Grafana configurations are supplied but not necessarily executed in environments without Docker.

**Safe for a portfolio when represented as a measured simulation + optional Ubuntu RAID integration exercise, not a production incident.**