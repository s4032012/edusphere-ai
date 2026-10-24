from decimal import Decimal
import unittest
from apps.grades.rules import parse_score, semester_average, qualitative_semester, can_transition

class GradeRulesTests(unittest.TestCase):
    def test_score_valid(self): self.assertEqual(parse_score('8.5'),Decimal('8.5'))
    def test_score_zero(self): self.assertEqual(parse_score('0'),Decimal('0'))
    def test_score_ten(self): self.assertEqual(parse_score('10'),Decimal('10'))
    def test_negative(self):
        with self.assertRaises(ValueError): parse_score('-0.1')
    def test_over_max(self):
        with self.assertRaises(ValueError): parse_score('10.1')
    def test_over_precision(self):
        with self.assertRaises(ValueError): parse_score('7.55')
    def test_nan(self):
        with self.assertRaises(ValueError): parse_score('NaN')
    def test_bool(self):
        with self.assertRaises(ValueError): parse_score(True)
    def test_semester_average(self): self.assertEqual(semester_average([7,8],8,9,2),Decimal('8.3'))
    def test_incomplete(self): self.assertIsNone(semester_average([8],8,8,2))
    def test_round_half_up(self): self.assertEqual(semester_average([0,0,0],1,'1.6',3),Decimal('0.9'))
    def test_qualitative_pass(self): self.assertEqual(qualitative_semester(['PASS']*4,2),'PASS')
    def test_qualitative_fail(self): self.assertEqual(qualitative_semester(['PASS']*3+['FAIL'],2),'FAIL')
    def test_qualitative_incomplete(self): self.assertIsNone(qualitative_semester(['PASS'],2))
    def test_state_transitions(self):
        self.assertTrue(can_transition('DRAFT','LOCKED'))
        self.assertTrue(can_transition('LOCKED','PUBLISHED'))
        self.assertFalse(can_transition('PUBLISHED','DRAFT'))
        self.assertFalse(can_transition('DRAFT','PUBLISHED'))

if __name__ == '__main__': unittest.main()
