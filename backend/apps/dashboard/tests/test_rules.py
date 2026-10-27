"""Runs with unittest even when Django dependencies are unavailable."""
import unittest
from datetime import datetime, timedelta, timezone
from apps.dashboard.rules import (can_open_dashboard, attendance_summary,
                                  homework_display, digest_sentences)


class DashboardRulesTests(unittest.TestCase):
    def test_parent_student_only(self):
        self.assertTrue(can_open_dashboard({'PARENT'}))
        self.assertTrue(can_open_dashboard({'STUDENT'}))
        self.assertFalse(can_open_dashboard({'SCHOOL_ADMIN'}))
        self.assertFalse(can_open_dashboard(set()))

    def test_attendance_does_not_assume_missing_days_present(self):
        self.assertEqual(attendance_summary(['ABSENT', 'PRESENT', 'LATE']), {
            'PRESENT': 1, 'ABSENT': 1, 'LATE': 1, 'recorded_days': 3})
        self.assertEqual(attendance_summary([])['recorded_days'], 0)

    def test_due_date_and_submissions(self):
        today = datetime(2026,10,27,10,tzinfo=timezone.utc)
        self.assertEqual(homework_display(None, due_at=today-timedelta(days=1), now=today), 'OVERDUE')
        self.assertEqual(homework_display(None, due_at=today, now=today), 'NOT_SUBMITTED')
        self.assertEqual(homework_display(None, due_at=today-timedelta(seconds=1), now=today), 'OVERDUE')
        self.assertEqual(homework_display('DRAFT', due_at=today+timedelta(hours=1), now=today), 'IN_PROGRESS')
        self.assertEqual(homework_display('DRAFT', due_at=today-timedelta(days=1), now=today), 'OVERDUE')
        self.assertEqual(homework_display('SUBMITTED', due_at=today-timedelta(days=1), now=today), 'SUBMITTED')

    def test_digest_evidence_and_no_diagnosis(self):
        lines = digest_sentences(attendance=attendance_summary([]),
            homework={'total':0, 'overdue':0, 'submitted_or_returned':0},published_grade_count=0)
        self.assertEqual({x['kind'] for x in lines}, {'attendance','homework','grades'})
        self.assertTrue(all(x['source'] for x in lines))
        self.assertFalse(any('bỏ học' in x['text'] or 'nguy cơ' in x['text'] for x in lines))


if __name__ == '__main__':
    unittest.main()
