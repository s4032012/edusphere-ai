from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from django.db import connection, connections
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from . import test_api
from apps.attendance.models import AttendanceSession, LeaveRequest, NotificationOutbox


@skipUnless(connection.vendor == 'postgresql', 'Requires PostgreSQL row locks')
class AttendanceConcurrencyTests(TransactionTestCase):
    setUp = test_api.Sprint2APITests.setUp
    c = test_api.Sprint2APITests.c
    start = test_api.Sprint2APITests.start
    create_leave = test_api.Sprint2APITests.create_leave
    complete_draft = test_api.Sprint2APITests.complete_draft

    def race(self, jobs):
        barrier=Barrier(len(jobs),timeout=10)
        requests=[(str(RefreshToken.for_user(user).access_token),url,payload) for user,url,payload in jobs]
        tenant=str(self.a.id)
        def send(job):
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '10s'")
                token,url,payload=job
                api=APIClient();api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}',HTTP_X_TENANT_ID=tenant)
                barrier.wait()
                return api.post(url,payload,format='json').status_code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=len(jobs)) as executor:
            return sorted(executor.map(send,requests))

    def test_concurrent_session_start_is_idempotent(self):
        job=(self.homeroom,'/api/v1/attendance/sessions/',{'classroom_id':str(self.clazz.id),'attendance_date':str(self.today)})
        self.assertEqual(self.race([job,job]),[200,201])
        self.assertEqual(AttendanceSession.objects.count(),1)

    def test_double_submit_emits_one_notification(self):
        sid=self.complete_draft();job=(self.homeroom,f'/api/v1/attendance/sessions/{sid}/submit/',{})
        self.assertEqual(self.race([job,job]),[200,400])
        self.assertEqual(NotificationOutbox.objects.filter(event_type='UNEXCUSED_ABSENCE').count(),1)

    def test_overlapping_leave_requests_create_one_row(self):
        job=(self.parent,'/api/v1/leave-requests/',{'student_id':str(self.student.id),'from_date':str(self.today),'through_date':str(self.today),'reason':'Synthetic reason'})
        self.assertEqual(self.race([job,job]),[201,400])
        self.assertEqual(LeaveRequest.objects.count(),1)

    def test_review_and_withdraw_have_one_winner(self):
        rid=self.create_leave()
        self.assertEqual(self.race([(self.homeroom,f'/api/v1/leave-requests/{rid}/decision/',{'action':'approve'}),
                                   (self.parent,f'/api/v1/leave-requests/{rid}/withdraw/',{})]),[200,400])
        leave=LeaveRequest.objects.get(id=rid)
        self.assertEqual(NotificationOutbox.objects.filter(event_type='LEAVE_DECIDED').count(),int(leave.state=='APPROVED'))

    def test_submit_and_approval_never_leave_false_queued_absence(self):
        sid=self.complete_draft();rid=self.create_leave()
        self.assertEqual(self.race([(self.homeroom,f'/api/v1/attendance/sessions/{sid}/submit/',{}),
            (self.homeroom,f'/api/v1/leave-requests/{rid}/decision/',{'action':'approve'})]),[200,200])
        self.assertFalse(NotificationOutbox.objects.filter(event_type='UNEXCUSED_ABSENCE',state='QUEUED').exists())
        self.assertEqual(NotificationOutbox.objects.filter(event_type='LEAVE_DECIDED').count(),1)
