"""Django integration tests. Run once dependencies are installed."""
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.identity.models import Account
from apps.schools.models import Tenant, Membership
from apps.academics.models import (AcademicYear, Classroom, Student, Enrollment,
    TeacherAssignment, GuardianLink, Subject)

class TenantAuthorizationAPITest(TestCase):
    def setUp(self):
        self.a = Tenant.objects.create(code='a', name='School A')
        self.b = Tenant.objects.create(code='b', name='School B')
        today = timezone.localdate()
        self.today = today
        self.y = AcademicYear.objects.create(tenant=self.a, label='2026', starts_on=today-timedelta(days=90), ends_on=today+timedelta(days=270))
        self.clazz = Classroom.objects.create(tenant=self.a, year=self.y, code='8A1', grade_level=8)
        self.math = Subject.objects.create(tenant=self.a, code='MATH', name='Toán')
        self.pupil = Student.objects.create(tenant=self.a, student_code='A001', full_name='Test Pupil', date_of_birth=today-timedelta(days=5000))
        Enrollment.objects.create(tenant=self.a, classroom=self.clazz, student=self.pupil, starts_on=today-timedelta(days=90))
        self.admin = self.actor('admin','SCHOOL_ADMIN')
        self.teacher = self.actor('teacher','SUBJECT_TEACHER')
        self.parent = self.actor('parent','PARENT')
        self.stranger = Account.objects.create_user(username='stranger', password='test-password')
        Membership.objects.create(tenant=self.b, account=self.stranger, role='SCHOOL_ADMIN', valid_from=today)

    def actor(self, username, role):
        actor = Account.objects.create_user(username=username, password='test-password')
        Membership.objects.create(tenant=self.a, account=actor, role=role, valid_from=self.today)
        return actor

    def client_for(self, actor, tenant=None):
        api = APIClient()
        token = RefreshToken.for_user(actor)
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}',
                        HTTP_X_TENANT_ID=str((tenant or self.a).id))
        return api

    def test_school_admin_can_read_own_school_roster(self):
        response = self.client_for(self.admin).get('/api/v1/students/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_cross_school_member_cannot_read_a(self):
        response = self.client_for(self.stranger, self.a).get('/api/v1/students/')
        self.assertEqual(response.status_code, 404)

    def test_school_a_member_cannot_read_b(self):
        response = self.client_for(self.admin, self.b).get('/api/v1/students/')
        self.assertEqual(response.status_code, 404)

    def test_teacher_requires_assignment(self):
        api = self.client_for(self.teacher)
        self.assertEqual(api.get('/api/v1/students/').json(), [])
        TeacherAssignment.objects.create(tenant=self.a, teacher=self.teacher, classroom=self.clazz,
            subject=self.math, kind='SUBJECT', starts_on=self.today)
        resp = api.get('/api/v1/students/')
        self.assertEqual(len(resp.json()), 1)
        self.assertNotIn('date_of_birth', resp.json()[0])

    def test_teacher_assignment_expiry_revokes_access(self):
        TeacherAssignment.objects.create(tenant=self.a, teacher=self.teacher, classroom=self.clazz,
            subject=self.math, kind='SUBJECT', starts_on=self.today-timedelta(days=30),
            ends_on=self.today-timedelta(days=1))
        self.assertEqual(self.client_for(self.teacher).get('/api/v1/students/').json(), [])

    def test_guardian_requires_verification(self):
        link = GuardianLink.objects.create(tenant=self.a, student=self.pupil, guardian=self.parent,
            relation='FATHER', valid_from=self.today)
        api = self.client_for(self.parent)
        self.assertEqual(api.get('/api/v1/students/').json(), [])
        link.is_verified = True
        link.save()
        self.assertEqual(len(api.get('/api/v1/students/').json()), 1)

    def test_non_admin_cannot_create_student(self):
        response = self.client_for(self.parent).post('/api/v1/students/',
                  {'student_code':'NEW', 'full_name':'Child'}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_tenant_header_is_mandatory(self):
        api = self.client_for(self.admin)
        api.credentials(HTTP_AUTHORIZATION=api._credentials['HTTP_AUTHORIZATION'])
        self.assertEqual(api.get('/api/v1/students/').status_code, 400)

    def test_guardian_link_does_not_autoverify(self):
        data = {'student_id':str(self.pupil.id), 'guardian_id':str(self.parent.id),
                'relation':'FATHER', 'is_verified': True}
        response = self.client_for(self.admin).post('/api/v1/guardian-links/', data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()['is_verified'])

    def test_other_tenant_year_rejected(self):
        y_other = AcademicYear.objects.create(tenant=self.b, label='2026',
                      starts_on=self.today, ends_on=self.today+timedelta(days=270))
        response = self.client_for(self.admin).post('/api/v1/classrooms/',
            {'year':str(y_other.id), 'code':'7A1', 'grade_level':7}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_invalid_tenant_header_is_404(self):
        api = self.client_for(self.admin)
        api._credentials['HTTP_X_TENANT_ID'] = 'not-a-uuid'
        self.assertEqual(api.get('/api/v1/students/').status_code, 404)

    def test_invalid_relationship_ids_are_400(self):
        api = self.client_for(self.admin)
        for endpoint in ['enrollments', 'teacher-assignments', 'guardian-links']:
            with self.subTest(endpoint=endpoint):
                self.assertEqual(api.post(f'/api/v1/{endpoint}/', {}, format='json').status_code, 400)

    def test_duplicate_student_is_400_and_not_audited(self):
        from apps.schools.models import AuditEvent
        response = self.client_for(self.admin).post('/api/v1/students/',
            {'student_code': self.pupil.student_code, 'full_name': 'Duplicate'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_successful_write_creates_audit(self):
        from apps.schools.models import AuditEvent
        response = self.client_for(self.admin).post('/api/v1/students/',
            {'student_code': 'NEW', 'full_name': 'Synthetic child'}, format='json')
        self.assertEqual(response.status_code, 201)
        event = AuditEvent.objects.get()
        self.assertEqual(event.tenant, self.a)
        self.assertEqual(str(event.target_id), response.json()['id'])

    def test_membership_revocation_applies_to_existing_token(self):
        api = self.client_for(self.admin)
        Membership.objects.filter(account=self.admin).update(is_active=False)
        self.assertEqual(api.get('/api/v1/students/').status_code, 404)

    def test_student_only_sees_self(self):
        from apps.academics.models import StudentAccount
        child = self.actor('child', 'STUDENT')
        StudentAccount.objects.create(tenant=self.a, student=self.pupil, account=child)
        other = Student.objects.create(tenant=self.a, student_code='OTHER', full_name='Other')
        api = self.client_for(child)
        self.assertEqual(len(api.get('/api/v1/students/').json()), 1)
        self.assertEqual(api.get(f'/api/v1/students/{other.id}/').status_code, 404)

    def test_parent_cannot_read_unlinked_child_detail(self):
        self.assertEqual(self.client_for(self.parent).get(f'/api/v1/students/{self.pupil.id}/').status_code, 404)

    def test_cross_tenant_write_denied(self):
        response = self.client_for(self.admin, self.b).post('/api/v1/students/',
            {'student_code': 'BAD', 'full_name': 'Bad'}, format='json')
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Student.objects.filter(student_code='BAD').exists())

    def test_teacher_sees_empty_assigned_class_but_not_other_enrollment(self):
        empty = Classroom.objects.create(tenant=self.a, year=self.y, code='EMPTY', grade_level=8)
        other = Classroom.objects.create(tenant=self.a, year=self.y, code='OTHER', grade_level=8)
        for classroom in [self.clazz, empty]:
            TeacherAssignment.objects.create(tenant=self.a, teacher=self.teacher, classroom=classroom,
                subject=self.math, kind='SUBJECT', starts_on=self.today)
        Enrollment.objects.create(tenant=self.a, student=self.pupil, classroom=other, starts_on=self.today)
        result = self.client_for(self.teacher).get('/api/v1/classrooms/').json()
        self.assertEqual({r['code'] for r in result}, {'8A1', 'EMPTY'})

    def test_cors_accepts_tenant_header(self):
        response = APIClient().options('/api/v1/students/',
            HTTP_ORIGIN='http://localhost:5174', HTTP_ACCESS_CONTROL_REQUEST_METHOD='GET',
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS='authorization,x-tenant-id')
        self.assertIn('x-tenant-id', response['Access-Control-Allow-Headers'])
        self.assertEqual(response['Access-Control-Allow-Origin'], 'http://localhost:5174')

    def test_expired_token_is_401(self):
        token = RefreshToken.for_user(self.admin).access_token
        token.set_exp(lifetime=timedelta(seconds=-1))
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}', HTTP_X_TENANT_ID=str(self.a.id))
        self.assertEqual(api.get('/api/v1/students/').status_code, 401)

    def test_guardian_verify_requires_evidence_and_admin(self):
        link = GuardianLink.objects.create(tenant=self.a, student=self.pupil, guardian=self.parent,
            relation='GUARDIAN', valid_from=self.today)
        url = f'/api/v1/guardian-links/{link.id}/verify/'
        self.assertEqual(self.client_for(self.parent).post(url, {'evidence_checked':True}, format='json').status_code, 403)
        self.assertEqual(self.client_for(self.admin).post(url, {'evidence_checked':'true'}, format='json').status_code, 400)
        self.assertEqual(self.client_for(self.admin).post(url, {'evidence_checked':True}, format='json').status_code, 200)
        self.assertEqual(len(self.client_for(self.parent).get('/api/v1/students/').json()), 1)
