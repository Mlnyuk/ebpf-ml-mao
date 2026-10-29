import unittest
from scripts.paper_score import validate


class ScoringTests(unittest.TestCase):
    def rating(self):
        return {'review_id':'a','reviewer_id':'human1','independent_of_implementation':True,
                'timestamp':'2026-10-29T00:00:00Z','scores':{'destination':None,'affected_target':None,'cause_type':None,
                'time_confusion':None,'container_confusion':None,'abstention':'unassessable'},'claim_ratings':[], 'rationale':'No accepted output.'}

    def test_missing_ratings_are_not_zero(self):
        with self.assertRaisesRegex(ValueError,'NOT_PERFORMED'): validate([],[])

    def test_nonindependent_refused(self):
        r=self.rating();r['independent_of_implementation']=False
        with self.assertRaisesRegex(ValueError,'non-independent'):validate([r],[{'review_id':'a'}])

    def test_duplicate_does_not_replace(self):
        r=self.rating()
        with self.assertRaisesRegex(ValueError,'duplicate'):validate([r,r],[{'review_id':'a'}])

    def test_partial_unassessable_is_retained(self):
        self.assertIn('a',validate([self.rating()],[{'review_id':'a'}]))


if __name__=='__main__':unittest.main()
