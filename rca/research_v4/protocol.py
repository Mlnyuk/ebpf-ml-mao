"""New collection plan; freeze before collecting any evaluation incident."""
import copy
import json
import random
from pathlib import Path
from research.capture import write_new
from research.evidence import digest
from research.spec import RUBRIC, SCHEMA
from rca.common import now

ROOT=Path(__file__).resolve().parents[1]
SCENARIOS=['normal','application_error','route_error','mixed_route_error','auxiliary_error']
ARMS={'batch':{'selective':False,'ebpf':True},'selective':{'selective':True,'ebpf':True}}


def protocol():
    cases=[{'scenario':s,'logging':l,'load_interval_seconds':i,'duration_seconds':20} for s in SCENARIOS for l in ['opaque','endpoint'] for i in [1.0,0.25]]
    random.Random(2910294).shuffle(cases)
    return {'version':'paper-next-v1','registered_at':now(),'status':'exploratory_followup_not_confirmatory',
        'model':'z-ai/glm-5.3-flash','provider_tag':'z-ai/fp8','fallback':False,'seed':2910294,
        'independent_captures':20,'capture_schedule':cases,'llm_repeats':1,
        'breadth_views':['target_only','surrounding_3_workloads'],'breadth_unit':'paired views of one occurrence, not independent incidents',
        'robustness_views':['historical_contamination','collection_missing'],
        'robustness_parent':'last application_error capture; older route_error capture used for history; two breadth views each',
        'arms':copy.deepcopy(ARMS),'baseline':'allowlist destination comparison; no anomaly is NOT proof of health; offline only',
        'planned_primary_llm_runs':80,'planned_robustness_llm_runs':8,
        'global_budget':{'api_calls':480,'usd_guard':2.0,'includes':'main experiment, explicit live demonstrations and native K8sGPT explanation calls; independent of all prior budgets'},
        'limits':{'calls_per_run':4,'retrieval_rounds':2,'tool_calls':64,'output_tokens':2048,
                  'model_repairs':1,'request_chars':180000,'cumulative_chars':500000,'seconds_per_run':240},
        'rubric':copy.deepcopy(RUBRIC),'output_schema':SCHEMA,
        'quality':'NOT_EVALUATED until actual independent humans rate; no model or author grades presented as independent',
        'analysis':'New physical occurrence per capture with fresh Pod UID. One LLM run per method/view. Paired differences over incidents, factors logging/load/scenario reported. Normal and robustness separately. No significance claim from single occurrence per factorial cell.',
        'shared_policy':'Both arms use same source catalog, bounded captured snapshots, lossless compact-v4 encoding, identity/time filters, output contract and one repair. Batch reads all catalog entries, selection chooses entries. No semantic source pruning for one arm.',
        'changes_since_clock_v3':['Nested actually shown evidence IDs are registered with original time/identity.',
            'Precise type/path validation errors in the shared repair message; no semantic coercion.',
            'Source keys identify target vs surrounding workload and telemetry type; no truth labels.',
            'Same new prompt/limits and schema apply to batch and selective; no cross-version causal claim from changed policy.'],
        'truth':'Private occurrence assignment and held-out HTTP outcomes. Never serialize into Agent catalog or requests.',
        'observability':{
            'normal':'Successful workload requests and matching destinations; not universal health proof.',
            'application_error':'TCP attempts reach expected destination; detailed logs expose local application exception; opaque logs may require abstention about mechanism.',
            'route_error':'Primary destination port mismatch; entry probe does not establish connect failure.',
            'mixed_route_error':'Wrong primary connection plus legitimate auxiliary connection; allowlist source and noncritical role declared.',
            'auxiliary_error':'Primary requests succeed while noncritical auxiliary port is wrong; mismatch alone is insufficient to diagnose primary service failure.',
            'historical_contamination':'Actual earlier logs/events retain original UID/time and are nested context.',
            'collection_missing':'Target logs/eBPF unavailable; all remaining captured evidence retained; absence is not zero.'},
        'k8sgpt':{'version':'v0.4.41','mode':'native defaults plus Log retained without explain; Pod,Service,Deployment,ReplicaSet,Log full-namespace explain using same provider, fresh config and no-cache. No truth inputs or custom fault analyzer.',
            'fairness':'Do not compare a live analyzer snapshot as if it received the same frozen data as our controller. Record raw output, analyzer list, all flags and cache configuration. Positive Kubernetes-visible control checked separately.',
            'categories':['out_of_scope','in_scope_not_detected','incorrect_diagnosis_after_human_review','appropriate_abstention_after_human_review','finding_ungraded'],
            'llm':'Same external model/provider if explain requests occur, via transparent recorded bounded proxy; unsupported compatibility is reported, not silently switched.',
            'prometheus_integration':'Source-verified v0.4.41 integration validates scrape configuration/relabeling; it is not a runtime metric RCA query tool. Not activated to manufacture unrelated configuration findings.',
            'native_log_scope':'Optional Log analyzer enabled; upstream implementation scans last 100 lines/current+previous container and returns first error/exception/fail matching line. Native behavior is retained, not restricted to our 60-line bound.'},
        'overhead':{'tetragon_base':'NOT_MEASURED until separate-kernel isolated environment verified',
                    'policy':'NOT_MEASURED on shared cluster','summary_incremental':'offline replay microbenchmark only unless isolated randomized ON/OFF exists','service_impact':'NOT_MEASURED on shared kernel'},
        'stop_rules':'No repeated failed investigation. Provider/network/global-budget error stops suite. Capture failure retained; no replacing an occurrence. Failed smoke data never become evaluation data.',
        'ui':'Replay never sends API requests. Explicit live mode uses same shared budget but separate exploratory outputs, never overwrites registered results.'}


def freeze(study):
    write_new(study/'protocol.json',protocol())
    paths=list((ROOT/'research_v4').rglob('*.py'))+list((ROOT/'research_v4').rglob('*.html'))
    paths+=list((ROOT/'research').glob('*.py'))+list((ROOT/'rca').glob('*.py'))
    paths+=[ROOT/'scripts/research_next.py',ROOT/'scripts/evaluate_frozen.py',ROOT/'scripts/rcactl.py',ROOT/'scripts/capture_network_study.py',ROOT/'scripts/paper_capture_v2.py']
    paths+=list((ROOT/'tests').glob('test_research_next*'))+[study/'protocol.json',study/'endpoint-metadata.json']
    paths+=[p for p in (ROOT/'vendor/k8sgpt-v0.4.41').rglob('*') if p.is_file()]
    write_new(study/'freeze.json',{'frozen_at':now(),'sha256':{str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in sorted(set(paths))}})
    old=ROOT/'artifacts/paper-clock-v3-20261029'
    write_new(study/'legacy-sha256.json',{'sha256':{str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in old.rglob('*') if p.is_file()}})


def check(study):
    for file in ['freeze.json','legacy-sha256.json']:
        for rel,h in json.loads((study/file).read_text())['sha256'].items():
            if digest((ROOT/rel).read_bytes())!=h:raise ValueError('frozen source changed: '+rel)
