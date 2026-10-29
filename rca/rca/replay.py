"""Read-only frozen telemetry for reproducible evaluations; never contacts K8s."""
import copy
import hashlib

from .common import compact, epoch
from .telemetry import TOOLS


def query_key(name, args):
    schemas = {t['function']['name']: t['function']['parameters']['properties'] for t in TOOLS}
    if name not in schemas or not isinstance(args, dict) or set(args) - set(schemas[name]):
        raise ValueError('invalid frozen telemetry query')
    args = dict(args)
    if name in ('get_metrics', 'get_ebpf_summary'):
        args.setdefault('window_seconds', 300)
        if type(args['window_seconds']) is not int or not 30 <= args['window_seconds'] <= 300:
            raise ValueError('invalid window')
    if name == 'get_metrics':
        args.setdefault('metric', 'memory')
        if args['metric'] not in ('memory', 'cpu'):
            raise ValueError('invalid metric')
    return (name, args.get('metric'), args.get('window_seconds'))


class FrozenTelemetry:
    def __init__(self, incident, evidence):
        self.incident = copy.deepcopy(incident)
        self.records = {}
        for item in evidence:
            target = item.get('target')
            if target and any(target.get(k) != incident.get(k) for k in
                              ('pod_uid', 'container_id', 'time')):
                raise ValueError('fixture evidence belongs to a different incident')
            name, args = item['tool'], {}
            if name in ('get_metrics', 'get_ebpf_summary'):
                if not all(k in item for k in ('window_start', 'window_end')):
                    continue
                duration = epoch(item['window_end']) - epoch(item['window_start'])
                if not duration.is_integer():
                    continue
                args['window_seconds'] = int(duration)
            if name == 'get_metrics':
                keys = set(item.get('series', {}))
                if keys & {'working_set_bytes', 'rss_bytes'}:
                    args['metric'] = 'memory'
                elif keys & {'usage_cores', 'throttled_period_ratio'}:
                    args['metric'] = 'cpu'
                else:
                    continue
            self.records[query_key(name, args)] = copy.deepcopy(item)

    def call(self, iid, name, args):
        key = query_key(name, args)
        if key in self.records:
            return copy.deepcopy(self.records[key])
        digest = hashlib.sha256(compact([self.incident, key]).encode()).hexdigest()[:12]
        return {'evidence_id': 'ev-missing-' + digest, 'tool': name, 'availability': 'unavailable',
                'source': 'frozen replay', 'error': 'Exact query window/source was not captured; no live fallback.'}
