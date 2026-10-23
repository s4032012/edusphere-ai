import unittest
from datetime import date, timedelta
from apps.attendance.rules import leave_range_valid,next_leave_state,effective_presence,can_edit_attendance

class AttendanceRulesTest(unittest.TestCase):
    def test_leave_policy_edges(self):
        today=date(2026,10,21)
        self.assertTrue(leave_range_valid(today,today+timedelta(days=13),today))
        self.assertFalse(leave_range_valid(today,today+timedelta(days=14),today))
        self.assertFalse(leave_range_valid(today+timedelta(days=1),today,today))
        self.assertFalse(leave_range_valid(today-timedelta(days=8),today,today))
    def test_state_machine_does_not_allow_repeated_review(self):
        self.assertEqual(next_leave_state('PENDING','approve','reviewer'),'APPROVED')
        self.assertEqual(next_leave_state('PENDING','withdraw','guardian'),'WITHDRAWN')
        for args in [('APPROVED','reject','reviewer'),('PENDING','approve','guardian'),('WITHDRAWN','approve','reviewer')]:
            with self.assertRaises(ValueError):next_leave_state(*args)
    def test_effective_attendance_does_not_override_roll_call(self):
        self.assertEqual(effective_presence('ABSENT',True),'EXCUSED_ABSENCE')
        self.assertEqual(effective_presence('PRESENT',True),'PRESENT')
        self.assertFalse(can_edit_attendance('SUBMITTED'))
        self.assertTrue(can_edit_attendance('DRAFT'))
