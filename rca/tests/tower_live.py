#!/usr/bin/env python3
"""One bounded read-only check on actual project workloads; never creates load."""
import json
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research_v4.tower_source import KubeSource
from research_v4.control_tower import Tower
from research_v4.terminal import frame

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=False)
calls = []
def runner(cmd, **kwargs):
    calls.append(cmd)
    return subprocess.run(cmd, **kwargs)

result = {'mode': 'actual read-only cluster check', 'observations': {}, 'new_api_calls': 0}
try:
    source = KubeSource(runner=runner)
    inventory = source.refresh()
    assert all(v['state'] == 'available' for v in inventory['sources'].values()), inventory['sources']
    pod = next(p for p in inventory['pods'] if p['namespace'] == 'rca-lab' and p['app'] == 'sample-service')
    container = pod['containers'][0]
    for kind in ('logs', 'events', 'ebpf'):
        value = source.inspect(kind, pod, container, inventory)
        # Record availability honestly; no expectation that the system is faulty or generates traffic.
        result['observations'][kind] = {'availability': value['availability'],
            'items': len(value.get('lines', value.get('events', value.get('tcp_connect_attempts', [])))),
            'scope': value['scope']}
    tower = Tower({'studies': []}); tower.set_inventory(inventory)
    tower.selected = inventory['pods'].index(pod)
    (out/'live-screen.txt').write_text(frame(tower.screen(120, 34), False)+'\n', encoding='utf-8')
    result['system'] = inventory['system']; result['result'] = 'PASS'
except BaseException as e:
    result['result'] = 'FAIL'; result['error'] = type(e).__name__ + ': ' + str(e); raise
finally:
    result['commands'] = calls
    (out/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(result, ensure_ascii=False, indent=2))
