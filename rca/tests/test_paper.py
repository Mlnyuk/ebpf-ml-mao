import copy
import json
import unittest
from research.evidence import summarize, verify_chain, mismatch_baseline
from research.engine import run_case, source_key
from research.spec import protocol, ARMS


INC={'namespace':'rca-lab','pod_uid':'pod-1','container_id':'containerd://one','time':'2026-10-29T00:01:00Z'}
START=1793232000.0


def event(second=10,cid='containerd://one',args=None):
    return json.dumps({'time':f'2026-10-29T00:00:{second:02d}Z','process_kprobe':{'function_name':'tcp_connect',
        'process':{'pod':{'namespace':'rca-lab','uid':'pod-1','container':{'id':cid}}},
        'args':args if args is not None else [{'sock_arg':{'daddr':'10.0.0.2','dport':9099}}]}})+'\n'


def answer(eid='ev-one',confirmed=''):
    return {'status':'inconclusive','affected_target':'pod-1','cause_type':'unknown','confirmed_cause':confirmed,
            'hypotheses':[],'unknowns':['origin unknown'],
            'claims':[{'text':'Observed evidence','kind':'observation','evidence_ids':[eid]}], 'recommendation':'Inspect.'}


def reply(name,value):
    return {'choices':[{'finish_reason':'tool_calls','message':{'tool_calls':[{'id':'x','type':'function','function':{'name':name,'arguments':json.dumps(value)}}]}}],
            'usage':{'prompt_tokens':100,'completion_tokens':40,'cost':0.0001}}


class Fake:
    def __init__(self,answers): self.answers=iter(answers); self.payloads=[]
    def payload(self,messages,tools): return {'messages':messages,'tools':tools,'model':'fake'}
    def complete(self,messages,tools,timeout):
        self.payloads.append(self.payload(messages,tools)); return next(self.answers)


class PaperTests(unittest.TestCase):
    def test_raw_exact_window_and_container(self):
        lines=[event(10),event(20,cid='old'),event(30),event(9)]
        e,p=summarize(lines,INC,START+10,START+30)
        self.assertEqual(e['network']['tcp_connect_attempts'][0]['attempts'],1)
        self.assertEqual(p['rejected'],{'different_container':1,'outside_interval':2})
        self.assertTrue(verify_chain(e,p,lines,INC))

    def test_hash_tamper_detected(self):
        e,p=summarize([event()],INC,START,START+30)
        with self.assertRaises(ValueError): verify_chain(e,p,[event(11)],INC)

    def test_duplicate_socket_arguments_do_not_double_count(self):
        args=[{'sock_arg':{'daddr':'10.0.0.2','dport':9099}}]*2
        e,_=summarize([event(args=args)],INC,START,START+30)
        self.assertEqual(e['network']['tcp_connect_attempts'][0]['attempts'],1)

    def test_ambiguous_socket_excluded_not_invented(self):
        args=[{'sock_arg':{'daddr':'10.0.0.2','dport':9099}},{'sock_arg':{'daddr':'10.0.0.3','dport':9099}}]
        e,p=summarize([event(args=args)],INC,START,START+30)
        self.assertEqual(p['rejected']['ambiguous_or_missing_socket'],1)
        self.assertEqual(e['observation_state'],'observed_zero')

    def test_zero_and_failed_are_distinct(self):
        zero,_=summarize([],INC,START,START+30)
        failed,_=summarize([],INC,START,START+30,False)
        self.assertEqual(zero['observation_state'],'observed_zero')
        self.assertEqual(failed['observation_state'],'collection_failed')
        self.assertNotEqual(zero['availability'],failed['availability'])

    def case(self):
        return {'case_id':'case','incident':INC,'evidence':[{'tool':'get_logs','availability':'available','evidence_id':'ev-one','lines':['failure']}]}

    def test_common_contract_and_one_repair_every_arm(self):
        for name,config in ARMS.items():
            records=[]
            replies=([reply('inspect',{'sources':['get_logs']})] if config['selective'] else [])
            replies += [reply('submit_rca',answer(confirmed='null')),reply('submit_rca',answer())]
            result=run_case(self.case(),config,Fake(replies),protocol()['limits'],records.append)
            self.assertEqual(result['state'],'accepted',name)
            self.assertEqual(result['repairs'],1)
            self.assertEqual(result['format_outcome'],'after_model_repair')
            self.assertEqual(len([r for r in records if r['type']=='response']),len(replies))

    def test_failed_repair_retained(self):
        f=Fake([reply('submit_rca',{}),reply('submit_rca',{})]); records=[]
        r=run_case(self.case(),ARMS['batch-ebpf'],f,protocol()['limits'],records.append)
        self.assertEqual(r['state'],'error'); self.assertEqual(r['calls'],2)
        self.assertEqual(len([x for x in records if x['type']=='validation_error']),2)
        self.assertIsNone(r['answer'])

    def test_truth_rejected_not_serialized(self):
        case=self.case(); case['truth']={'cause':'secret_label'}
        with self.assertRaises(ValueError): run_case(case,ARMS['batch-ebpf'],Fake([]),protocol()['limits'],lambda x:None)

    def test_unretrieved_is_not_zero(self):
        no_claims=answer(); no_claims['claims']=[]
        r=run_case(self.case(),ARMS['selective-ebpf'],Fake([reply('submit_rca',no_claims)]),protocol()['limits'],lambda x:None)
        self.assertEqual(r['source_states']['get_logs'],'not_retrieved')

    def test_wrong_citation_cannot_pass(self):
        r=run_case(self.case(),ARMS['batch-ebpf'],Fake([reply('submit_rca',answer('invented'))]*2),protocol()['limits'],lambda x:None)
        self.assertEqual(r['state'],'error')

    def test_ablation_off_has_identical_final_contract(self):
        baseline=Fake([reply('submit_rca',answer())]); other=Fake([reply('submit_rca',answer())])
        for p,c in [(baseline,ARMS['batch-ebpf']),(other,{**ARMS['batch-ebpf'],'compression':False,'dedup':False,'stop_guidance':False})]:
            run_case(self.case(),c,p,protocol()['limits'],lambda x:None)
        self.assertEqual(baseline.payloads[0]['tools'],other.payloads[0]['tools'])

    def test_no_ebpf_is_actually_hidden(self):
        case=self.case(); e,_=summarize([event()],INC,START,START+30); case['evidence'].append(e)
        p=Fake([reply('submit_rca',answer())])
        run_case(case,ARMS['batch-no-ebpf'],p,protocol()['limits'],lambda x:None)
        self.assertNotIn('tcp_connect_attempts',json.dumps(p.payloads))

    def test_missing_metric_identity_preserved(self):
        self.assertEqual(source_key({'tool':'get_metrics','source_key':'metrics_memory'}),'metrics_memory')

    def test_baseline_zero_is_unassessable(self):
        e,_=summarize([],INC,START,START+30)
        c={'evidence':[e,{'tool':'get_workload_status','evidence_id':'status','data':{'declared_dependency':{'expected_ip':'10.0.0.2','expected_port':8080}}}]}
        self.assertEqual(mismatch_baseline(c)['status'],'unassessable')

    def test_transport_is_global_stop_no_retry(self):
        class Broken(Fake):
            def complete(self,*args): raise OSError('down')
        r=run_case(self.case(),ARMS['batch-ebpf'],Broken([]),protocol()['limits'],lambda x:None)
        self.assertTrue(r['global_stop']); self.assertEqual(r['calls'],1)


if __name__=='__main__': unittest.main()
