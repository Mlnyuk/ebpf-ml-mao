import contextlib
import io
import json
import unittest
from research_v4.engine import citation_registry,validate_answer,validate_schema
from research_v4.baseline import compare
from research_v4.lab import work
from research_v4.analyze import type_violations
from research.spec import SCHEMA


class NextResearchTests(unittest.TestCase):
    def answer(self):
        return {'status':'inconclusive','affected_target':'app','cause_type':'unknown','confirmed_cause':'',
                'hypotheses':[],'unknowns':['why'],'claims':[],'recommendation':'inspect'}
    def test_nested_citation_keeps_old_identity(self):
        old={'evidence_id':'old','tool':'get_logs','availability':'available','target':{'pod_uid':'old-pod'}}
        shown=[{'evidence_id':'now','tool':'get_k8s_events','availability':'available','historical_context':{'evidence':[old]}}]
        a=self.answer();a['claims']=[{'text':'Earlier pod logged an error','kind':'observation','evidence_ids':['old']}]
        self.assertEqual(validate_answer(a,shown),a)
        self.assertEqual(citation_registry(shown)['old']['target']['pod_uid'],'old-pod')
    def test_unshown_citation_rejected(self):
        a=self.answer();a['claims']=[{'text':'fake','kind':'observation','evidence_ids':['unknown']}]
        with self.assertRaises(ValueError):validate_answer(a,[])
    def test_ambiguous_id_rejected(self):
        with self.assertRaises(ValueError):citation_registry([{'tool':'get_logs','evidence_id':'x','lines':[]},{'tool':'get_logs','evidence_id':'x','lines':['other']}])
    def test_string_array_error_has_path(self):
        a=self.answer();a['hypotheses']=[{'text':'guess'}]
        with self.assertRaisesRegex(ValueError,r'\$\.hypotheses\[0\]'):validate_schema(a,SCHEMA)
        self.assertEqual(type_violations(a)[0]['actual'],'dict')
    def test_application_error_has_normal_destination(self):
        seen=[]
        with contextlib.redirect_stdout(io.StringIO()):result=work('application_error','endpoint','http://backend:8080','http://aux:8080',lambda url:seen.append(url))
        self.assertEqual(result,503);self.assertEqual(seen,['http://backend:8080/healthz'])
    def test_mixed_traffic_and_noncritical_failure(self):
        def fetch(url):
            if ':9099' in url:raise ConnectionRefusedError()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(work('mixed_route_error','opaque','http://backend:8080','http://aux:8080',fetch),503)
            self.assertEqual(work('auxiliary_error','opaque','http://backend:8080','http://aux:8080',fetch),200)
    def test_allowlist_not_health_detector(self):
        inc={'pod_uid':'p'}
        c={'incident':inc,'evidence':[{'tool':'get_workload_status','target':inc,'evidence_id':'s','data':{'declared_dependency':json.dumps({'expected_ip':'1.2.3.4','expected_port':80,'allowed_auxiliary_destinations':[{'expected_ip':'1.2.3.5','expected_port':80}]})}},
            {'tool':'get_ebpf_summary','target':inc,'evidence_id':'e','observation_state':'observed_nonzero','network':{'tcp_connect_attempts':[{'destination_ip':'1.2.3.5','destination_port':80,'attempts':3}]}}]}
        self.assertEqual(compare(c)['state'],'no_mismatch_observed')
        c['evidence'][1]['observation_state']='collection_failed'
        self.assertEqual(compare(c)['state'],'unassessable')


if __name__=='__main__':unittest.main()
