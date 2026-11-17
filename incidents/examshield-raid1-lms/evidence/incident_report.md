# Incident report — university LMS exam storage fault

**Execution date:** 2026-11-17 UTC
**Mode:** filesystem mirror simulation; true Linux mdadm RAID1 was not executed.

An LMS was under a synthetic workload of 80 student identities. During autosaves one of two filesystem replicas was disabled; the simulated mirror reported degradation. The replica was restored while HTTP traffic continued.

| Observed metric | Value |
|---|---|
| HTTP write requests | 1,715 |
| Successful writes | 1,715 |
| Sampled /health probes | 105/105 |
| Detection latency | 0.020 s |
| Rebuild duration | 3.069 s |
| Replica objects | 1,716 each |
| SHA-256 replica match | yes |
| Idempotent retry receipt | matched |
| Final status | healthy |

This is not a production SLA. It does not validate host power failure, true mdadm block I/O behavior, disk cache durability, or a live Grafana instance. Use `scripts/real_mdadm_ubuntu.sh` for separate Ubuntu kernel RAID testing.
