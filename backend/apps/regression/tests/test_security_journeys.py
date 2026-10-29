"""Sprint 7 database-backed regression journeys.

Expected to run using Django test runner + disposable PostgreSQL database.
Executed by the same PostgreSQL CI suite as all domain tests.
"""
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.identity.models import Account
from apps.schools.models import Tenant, Membership
from apps.academics.models import (AcademicYear, Classroom, Subject, Student,
                                  Enrollment, TeacherAssignment, GuardianLink, StudentAccount)


class TenantAndRoleRegressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        today = timezone.localdate()
        cls.a = Tenant.objects.create(code='reg-tenant-a', name='Synthetic School A')
        cls.b = Tenant.objects.create(code='reg-tenant-b', name='Synthetic School B')

        def user(name, school, role):
            account = Account.objects.create_user(username=name, password='synthetic-test-only')
            Membership.objects.create(tenant=school, account=account, role=role,
                                      valid_from=today-timedelta(days=30))
            return account

        cls.admin_a = user('s7_admin_a', cls.a, 'SCHOOL_ADMIN')
        cls.admin_b = user('s7_admin_b', cls.b, 'SCHOOL_ADMIN')
        cls.parent_a = user('s7_parent_a', cls.a, 'PARENT')
        cls.parent_unverified = user('s7_parent_unverified', cls.a, 'PARENT')
        cls.student_actor = user('s7_student_a', cls.a, 'STUDENT')
        cls.teacher_a = user('s7_teacher_a', cls.a, 'SUBJECT_TEACHER')
        cls.teacher_unassigned = user('s7_teacher_unassigned', cls.a, 'SUBJECT_TEACHER')
        cls.expired = user('s7_expired_a', cls.a, 'PARENT')
        cls.year = AcademicYear.objects.create(tenant=cls.a, label='synthetic-2026',
            starts_on=today-timedelta(days=30), ends_on=today+timedelta(days=300))
        cls.clazz = Classroom.objects.create(tenant=cls.a, year=cls.year, code='8A1', grade_level=8)
        cls.subject = Subject.objects.create(tenant=cls.a, code='MATH', name='Toán')
        cls.child = Student.objects.create(tenant=cls.a, student_code='S7-001', full_name='Synthetic A')
        cls.other = Student.objects.create(tenant=cls.a, student_code='S7-002', full_name='Synthetic B')
        for s in (cls.child, cls.other):
            Enrollment.objects.create(tenant=cls.a, student=s, classroom=cls.clazz,
                                      starts_on=today-timedelta(days=20))
        TeacherAssignment.objects.create(tenant=cls.a, teacher=cls.teacher_a, classroom=cls.clazz,
            subject=cls.subject, kind='SUBJECT', starts_on=today-timedelta(days=20))
        GuardianLink.objects.create(tenant=cls.a, guardian=cls.parent_a, student=cls.child,
            relation='MOTHER', is_verified=True, valid_from=today-timedelta(days=20))
        GuardianLink.objects.create(tenant=cls.a, guardian=cls.parent_unverified, student=cls.other,
            relation='FATHER', is_verified=False, valid_from=today-timedelta(days=20))
        StudentAccount.objects.create(tenant=cls.a, account=cls.student_actor, student=cls.child)
        Membership.objects.filter(tenant=cls.a, account=cls.expired).update(
            valid_to=today-timedelta(days=1))

    def client_as(self, actor, tenant=None):
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION='Bearer '+str(RefreshToken.for_user(actor).access_token),
            HTTP_X_TENANT_ID=str((tenant or self.a).id))
        return client

    def test_cross_tenant_admin_cannot_read_student_by_known_uuid(self):
        c = self.client_as(self.admin_b, self.b)
        self.assertEqual(c.get(f'/api/v1/students/{self.child.id}/').status_code, 404)

    def test_cross_tenant_dashboard_denied(self):
        c = self.client_as(self.parent_a, self.b)
        self.assertEqual(c.get(f'/api/v1/dashboard/students/{self.child.id}/').status_code, 404)

    def test_verified_parent_sees_only_own_child(self):
        c = self.client_as(self.parent_a)
        self.assertEqual(c.get(f'/api/v1/dashboard/students/{self.child.id}/').status_code, 200)
        self.assertEqual(c.get(f'/api/v1/dashboard/students/{self.other.id}/').status_code, 404)

    def test_unverified_guardian_cannot_read_student(self):
        self.assertEqual(self.client_as(self.parent_unverified).get(
            f'/api/v1/dashboard/students/{self.other.id}/').status_code, 404)

    def test_revoking_guardian_access_immediately_revokes_dashboard(self):
        c = self.client_as(self.parent_a)
        self.assertEqual(c.get(f'/api/v1/dashboard/students/{self.child.id}/').status_code, 200)
        GuardianLink.objects.filter(tenant=self.a, guardian=self.parent_a).update(is_active=False)
        self.assertEqual(c.get(f'/api/v1/dashboard/students/{self.child.id}/').status_code, 404)

    def test_teacher_scope_removed_on_assignment_revocation(self):
        c = self.client_as(self.teacher_a)
        self.assertEqual(c.get(f'/api/v1/students/{self.child.id}/').status_code, 200)
        TeacherAssignment.objects.filter(tenant=self.a,teacher=self.teacher_a).update(is_active=False)
        self.assertEqual(c.get(f'/api/v1/students/{self.child.id}/').status_code, 404)

    def test_unassigned_teacher_cannot_read_student(self):
        self.assertEqual(self.client_as(self.teacher_unassigned).get(
            f'/api/v1/students/{self.child.id}/').status_code, 404)

    def test_admin_cannot_use_parent_dashboard(self):
        self.assertEqual(self.client_as(self.admin_a).get(
            f'/api/v1/dashboard/students/{self.child.id}/').status_code, 403)

    def test_expired_membership_denied(self):
        self.assertEqual(self.client_as(self.expired).get('/api/v1/students/').status_code, 404)

    def test_anonymous_denied(self):
        self.assertEqual(APIClient().get('/api/v1/students/', HTTP_X_TENANT_ID=str(self.a.id)).status_code, 401)

    def test_missing_tenant_header_denied(self):
        c = self.client_as(self.admin_a)
        c.credentials(HTTP_AUTHORIZATION='Bearer '+str(RefreshToken.for_user(self.admin_a).access_token))
        self.assertEqual(c.get('/api/v1/students/').status_code, 400)

    def test_student_can_only_see_self_dashboard(self):
        c = self.client_as(self.student_actor)
        self.assertEqual(c.get(f'/api/v1/dashboard/students/{self.child.id}/').status_code, 200)
        self.assertEqual(c.get(f'/api/v1/dashboard/students/{self.other.id}/').status_code, 404)
