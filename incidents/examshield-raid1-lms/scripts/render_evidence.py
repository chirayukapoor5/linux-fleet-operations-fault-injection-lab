#!/usr/bin/env python3
"""Render charts from recorded measurements, not fabricated screenshots."""
import json,sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path(sys.argv[1] if len(sys.argv)>1 else 'evidence')
probes=json.loads((p/'health_probes.json').read_text())
timeline=json.loads((p/'timeline.json').read_text())
metrics=json.loads((p/'metrics.json').read_text())
fig,ax=plt.subplots(figsize=(12,4))
ax.scatter([r['elapsed_s'] for r in probes],[int(r['status']==200) for r in probes],s=14,label='HTTP health check')
for name,color in [('disk_failure_requested','red'),('rebuild_requested','orange'),('rebuild_finished','green')]:
    for r in timeline:
        if r.get('name',r.get('event'))==name:
            ax.axvline(r['elapsed_s'],color=color,ls='--',label=name)
ax.set(ylim=(-.1,1.2),yticks=[0,1],xlabel='Elapsed seconds',ylabel='Healthy',title='Observed LMS availability')
ax.legend();fig.tight_layout();fig.savefig(p/'availability_timeline.png',dpi=150);plt.close(fig)
fig,ax=plt.subplots(figsize=(8,4))
ax.bar(['Alert detection','Rebuild'],[metrics['detection_latency_s'],metrics['rebuild_duration_s']])
ax.set(ylabel='Seconds',title='Recorded simulation latencies')
fig.tight_layout();fig.savefig(p/'recovery_metrics.png',dpi=150);plt.close(fig)
