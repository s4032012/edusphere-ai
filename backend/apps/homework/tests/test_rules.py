"""Offline tests: python -m unittest discover -s backend/apps/homework/tests -p test_rules.py"""
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from apps.homework.rules import (assignment_transition,can_submit,can_mark,
    parse_feedback_score,submission_status)

class HomeworkRuleTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,24,13,0,tzinfo=timezone.utc)
        self.future=self.now+timedelta(hours=2)
        self.past=self.now-timedelta(hours=2)

    def test_valid_transitions(self):
        self.assertTrue(assignment_transition('DRAFT','PUBLISHED'))
        self.assertTrue(assignment_transition('PUBLISHED','CLOSED'))

    def test_invalid_transitions(self):
        for src,dst in [('DRAFT','CLOSED'),('CLOSED','PUBLISHED'),('PUBLISHED','DRAFT'),('DRAFT','DRAFT')]:
            with self.subTest(src=src,dst=dst):self.assertFalse(assignment_transition(src,dst))

    def test_submit_before_due(self):
        self.assertTrue(can_submit(assignment_state='PUBLISHED',deadline=self.future,now=self.now,allow_late=False))

    def test_deadline_boundary(self):
        self.assertTrue(can_submit(assignment_state='PUBLISHED',deadline=self.now,now=self.now,allow_late=False))

    def test_late_rejected_unless_enabled(self):
        self.assertFalse(can_submit(assignment_state='PUBLISHED',deadline=self.past,now=self.now,allow_late=False))
        self.assertTrue(can_submit(assignment_state='PUBLISHED',deadline=self.past,now=self.now,allow_late=True))

    def test_draft_and_closed_cannot_submit(self):
        for state in ['DRAFT','CLOSED']:
            self.assertFalse(can_submit(assignment_state=state,deadline=self.future,now=self.now,allow_late=True))

    def test_returned_cannot_resubmit(self):
        self.assertFalse(can_submit(assignment_state='PUBLISHED',deadline=self.future,
                                    now=self.now,allow_late=True,submission_state='RETURNED'))

    def test_naive_datetime_rejected(self):
        with self.assertRaises(ValueError):can_submit(assignment_state='PUBLISHED',deadline=self.future.replace(tzinfo=None),
                                                      now=self.now,allow_late=False)

    def test_only_submitted_can_be_marked(self):
        self.assertTrue(can_mark('SUBMITTED'))
        self.assertFalse(can_mark('DRAFT'));self.assertFalse(can_mark('RETURNED'))

    def test_score_valid(self):
        for raw,expected in [('0',Decimal('0.0')),('10',Decimal('10.0')),('7.5',Decimal('7.5')),('7',Decimal('7.0'))]:
            self.assertEqual(parse_feedback_score(raw),expected)
        self.assertIsNone(parse_feedback_score(None))

    def test_score_invalid(self):
        for raw in ['-1','10.1','7.55','NaN','infinity','not-a-number',True]:
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):parse_feedback_score(raw)

    def test_submission_status(self):
        self.assertEqual(submission_status(state=None,due_at=self.past,now=self.now),'OVERDUE')
        self.assertEqual(submission_status(state=None,due_at=self.future,now=self.now),'NOT_SUBMITTED')
        self.assertEqual(submission_status(state='SUBMITTED',due_at=self.past,now=self.now),'SUBMITTED')
        self.assertEqual(submission_status(state='RETURNED',due_at=self.past,now=self.now),'RETURNED')

if __name__=='__main__':unittest.main()
