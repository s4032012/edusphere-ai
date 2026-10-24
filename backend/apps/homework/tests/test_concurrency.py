from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from django.db import connection,connections
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from . import test_api,test_security
from apps.homework.models import HomeworkAssignment,HomeworkSubmission
from apps.attendance.models import NotificationOutbox

@skipUnless(connection.vendor=='postgresql','Requires PostgreSQL row locks')
class HomeworkConcurrencyTests(TransactionTestCase):
    c=test_api.HomeworkIntegrationTests.c
    task=test_api.HomeworkIntegrationTests.task
    published=test_security.HomeworkSecurityTests.published
    submit=test_security.HomeworkSecurityTests.submit
    def setUp(self):test_api.HomeworkIntegrationTests.setUpTestData.__func__(type(self))

    def race(self,jobs):
        barrier=Barrier(len(jobs),timeout=10);tenant=str(self.a.id)
        jobs=[(str(RefreshToken.for_user(user).access_token),method,path,data) for user,method,path,data in jobs]
        def send(job):
            try:
                with connection.cursor() as cursor:cursor.execute("SET lock_timeout = '10s'")
                token,method,path,data=job;api=APIClient()
                api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}',HTTP_X_TENANT_ID=tenant)
                barrier.wait();return getattr(api,method)(path,data,format='json').status_code
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=len(jobs)) as executor:return sorted(executor.map(send,jobs))

    def test_first_submission_race_returns_conflict(self):
        tid=self.published();job=(self.pupil,'put',f'/api/v1/homework/{tid}/my-submission/',{'content_text':'first','expected_version':0})
        self.assertEqual(self.race([job,job]),[200,409])
        self.assertEqual(HomeworkSubmission.objects.count(),1)
        self.assertEqual(HomeworkSubmission.objects.get().version,1)

    def test_same_version_updates_only_once(self):
        sub=self.submit();job=(self.pupil,'put',f'/api/v1/homework/{sub.assignment_id}/my-submission/',{'content_text':'update','expected_version':1})
        self.assertEqual(self.race([job,job]),[200,409]);sub.refresh_from_db();self.assertEqual(sub.version,2)

    def test_double_return_one_outbox_per_recipient(self):
        sub=self.submit();job=(self.teacher,'post',f'/api/v1/homework/submissions/{sub.id}/return/',{'feedback':'Good','expected_version':1})
        self.assertEqual(self.race([job,job]),[200,409]);sub.refresh_from_db();self.assertEqual(sub.version,2)
        self.assertEqual(NotificationOutbox.objects.filter(event_type='HOMEWORK_RETURNED').count(),2)

    def test_submit_against_close_respects_final_state(self):
        tid=self.published();jobs=[(self.pupil,'put',f'/api/v1/homework/{tid}/my-submission/',{'content_text':'first','expected_version':0}),
                                 (self.teacher,'post',f'/api/v1/homework/{tid}/close/',{})]
        self.assertIn(self.race(jobs),[[200,200],[200,400]])
        self.assertEqual(HomeworkAssignment.objects.get(id=tid).state,'CLOSED')
        self.assertEqual(self.c(self.pupil).put(f'/api/v1/homework/{tid}/my-submission/',{'content_text':'later','expected_version':1},format='json').status_code,400)

    def test_return_against_resubmit_never_grades_unseen_version(self):
        sub=self.submit();jobs=[(self.pupil,'put',f'/api/v1/homework/{sub.assignment_id}/my-submission/',{'content_text':'new answer','expected_version':1}),
                                (self.teacher,'post',f'/api/v1/homework/submissions/{sub.id}/return/',{'feedback':'Good','expected_version':1})]
        result=self.race(jobs);self.assertIn(result,[[200,400],[200,409]]);sub.refresh_from_db()
        if sub.state=='RETURNED':self.assertEqual(sub.content_text,'secret answer')
        else:self.assertEqual(sub.content_text,'new answer');self.assertEqual(sub.feedback,'');self.assertFalse(NotificationOutbox.objects.exists())

    def test_double_publish_one_state_change(self):
        tid=self.task().json()['id'];job=(self.teacher,'post',f'/api/v1/homework/{tid}/publish/',{})
        self.assertEqual(self.race([job,job]),[200,400])
