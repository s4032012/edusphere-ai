"""PostgreSQL row-lock regression tests; SQLite cannot validate this guarantee."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless

from django.db import connection, connections
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.identity.models import Account
from apps.schools.models import Tenant, Membership
from apps.academics.models import AcademicYear, Classroom, Student, Enrollment, TeacherAssignment


@skipUnless(connection.vendor == 'postgresql', 'Requires PostgreSQL row locks')
class ConcurrentAdministrationTests(TransactionTestCase):
    def setUp(self):
        today = timezone.localdate()
        self.tenant = Tenant.objects.create(code='concurrent', name='Concurrent test')
        admin = Account.objects.create_user(username='concurrent_admin')
        self.teacher = Account.objects.create_user(username='concurrent_teacher')
        for account, role in [(admin, 'SCHOOL_ADMIN'), (self.teacher, 'HOMEROOM_TEACHER')]:
            Membership.objects.create(tenant=self.tenant, account=account, role=role, valid_from=today)
        year = AcademicYear.objects.create(tenant=self.tenant, label='Current',
            starts_on=today-timedelta(days=1), ends_on=today+timedelta(days=100))
        self.classroom = Classroom.objects.create(tenant=self.tenant, year=year, code='6A', grade_level=6)
        self.student = Student.objects.create(tenant=self.tenant, student_code='S1', full_name='Synthetic')
        self.token = str(RefreshToken.for_user(admin).access_token)

    def simultaneous_posts(self, path, payload):
        barrier = Barrier(2, timeout=10)

        def post():
            try:
                # Bound lock waits so a regression cannot hang CI indefinitely.
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '10s'")
                client = APIClient()
                client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}',
                                   HTTP_X_TENANT_ID=str(self.tenant.id))
                barrier.wait()
                return client.post(path, payload, format='json').status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: post(), range(2)))
        self.assertEqual(sorted(results), [201, 400])

    def test_simultaneous_enrollments_create_only_one_record(self):
        self.simultaneous_posts('/api/v1/enrollments/', {
            'student_id': str(self.student.id), 'classroom_id': str(self.classroom.id)})
        self.assertEqual(Enrollment.objects.count(), 1)

    def test_simultaneous_homeroom_assignments_create_only_one_record(self):
        self.simultaneous_posts('/api/v1/teacher-assignments/', {
            'teacher_id': str(self.teacher.id), 'classroom_id': str(self.classroom.id), 'kind': 'HOMEROOM'})
        self.assertEqual(TeacherAssignment.objects.count(), 1)
