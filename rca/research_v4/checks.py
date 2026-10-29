"""Preflight checks against immutable old artifacts and actual smoke outcomes."""
import json
from pathlib import Path
from research.evidence import digest
from research.capture import write_new
from research_v4.protocol import ROOT
from rca.common import now


def preflight(study):
    smoke=json.loads((study/'development/observability-smoke.json').read_text())
    native=json.loads((study/'development/k8sgpt-positive-control.json').read_text())
    if len(smoke['results'])!=5 or not all(x['effect_observed'] for x in smoke['results']):raise ValueError('observability smoke incomplete')
    if not native['native_positive_control_detected'] or not native['mock_transport_requests'] or native['mock_transport_exit']:
        raise ValueError('native comparison preflight failed')
    old=ROOT/'artifacts/paper-clock-v3-20261029'
    for name,h in json.loads((old/'bundle-sha256.json').read_text())['sha256'].items():
        if digest((old/name).read_bytes())!=h:raise ValueError('prior artifact changed')
    write_new(study/'development/preflight.json',{'at':now(),'old_bundle_intact':True,'observability_smoke':True,
        'native_positive_control':True,'native_mock_transport_only':True,'independent_quality':'NOT_EVALUATED',
        'native_sources':[
            'https://github.com/k8sgpt-ai/k8sgpt/releases/tag/v0.4.41',
            'https://github.com/k8sgpt-ai/k8sgpt/blob/v0.4.41/pkg/analyzer/log.go',
            'https://github.com/k8sgpt-ai/k8sgpt/blob/v0.4.41/pkg/analyzer/pod.go',
            'https://github.com/k8sgpt-ai/k8sgpt/blob/v0.4.41/pkg/integration/prometheus/prometheus.go'],
        'stage':'development smoke completed; evaluation not started'})


def overhead_scope(study):
    write_new(study/'overhead-scope.json',{'at':now(),'status':'NOT_MEASURED_ONLINE',
        'environment_observation':{'ready_workers':['worker-1','worker-3'],'both_workers_have_unrelated_workloads':True,
            'gpu_nodes':'NotReady/Unknown; user placed on hold, not used','local_docker':'available but shares host kernel, not independent eBPF test environment','local_kvm':'not present'},
        'separate_kernel_environment':'not verified/provided as of this record',
        'components':{k:{'status':'NOT_MEASURED','reason':'No confirmed isolated kernel; no shared collector/policy interruption'} for k in ['tetragon_base','observation_policy','summary_incremental_online','service_cpu_memory_latency_throughput_impact']},
        'future_design':{'states':['service only','service + Tetragon without custom observation policy','service + Tetragon + observation policy','service + Tetragon + observation policy + summary'],
            'randomization':'randomized block order over matched offered loads after warmup','units':'independent load blocks, not per-request pseudo-replicates',
            'measures':['node and collector CPU/RSS','service achieved throughput','latency distribution','export/drop counters','summary CPU/RSS'],
            'scope':'Design only; none of these measurements claimed executed'}})
