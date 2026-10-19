"""Unit tests run with stdlib unittest without Django packages installed."""
import unittest
from datetime import date, timedelta
from apps.access.policy import Relation, can_read_student, currently_valid

TODAY = date(2026, 10, 18)
BASE = {'actor_id':'teacher-a','tenant_id':'school-a','student_id':'pupil-a','today':TODAY}

class AuthorizationRulesTest(unittest.TestCase):
    def relation(self, kind, **kwargs):
        return Relation(tenant_id='school-a', actor_id='teacher-a', student_id='pupil-a', kind=kind, **kwargs)

    def check(self, roles, relations):
        return can_read_student(roles=set(roles), relations=relations, **BASE)

    def test_default_deny(self):
        self.assertFalse(self.check({'SUBJECT_TEACHER'}, []))

    def test_school_admin_scope(self):
        self.assertTrue(self.check({'SCHOOL_ADMIN'}, []))

    def test_teacher_assignment(self):
        self.assertTrue(self.check({'SUBJECT_TEACHER'}, [self.relation('SUBJECT')]))
        self.assertFalse(self.check({'SUBJECT_TEACHER'}, [self.relation('HOMEROOM')]))

    def test_expired_assignment(self):
        self.assertFalse(self.check({'SUBJECT_TEACHER'}, [self.relation('SUBJECT', ends_on=TODAY-timedelta(days=1))]))

    def test_future_assignment(self):
        self.assertFalse(self.check({'HOMEROOM_TEACHER'}, [self.relation('HOMEROOM', starts_on=TODAY+timedelta(days=1))]))

    def test_cross_tenant_relation_denied(self):
        outsider = Relation(tenant_id='school-b', actor_id='teacher-a', student_id='pupil-a', kind='SUBJECT')
        self.assertFalse(self.check({'SUBJECT_TEACHER'}, [outsider]))

    def test_guardian_requires_verified_relation(self):
        self.assertFalse(self.check({'PARENT'}, [self.relation('GUARDIAN', verified=False)]))
        self.assertTrue(self.check({'PARENT'}, [self.relation('GUARDIAN', verified=True)]))
        self.assertFalse(self.check({'PARENT'}, [self.relation('GUARDIAN', verified=True, can_view_academic=False)]))

    def test_student_self_relation(self):
        self.assertTrue(self.check({'STUDENT'}, [self.relation('SELF')]))
        self.assertFalse(self.check({'STUDENT'}, [self.relation('SUBJECT')]))

    def test_membership_role_required(self):
        self.assertFalse(self.check({'SUPPORT_STAFF'}, [self.relation('SUBJECT'), self.relation('GUARDIAN', verified=True)]))

    def test_boundaries_are_inclusive(self):
        self.assertTrue(currently_valid(TODAY, TODAY, today=TODAY))

if __name__ == '__main__':
    unittest.main()
