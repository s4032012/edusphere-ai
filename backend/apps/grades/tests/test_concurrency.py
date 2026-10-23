from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from django.db import connection,connections
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from . import test_api
from apps.grades.models import GradeBook,Assessment,GradeEntry,GradeRevision
from apps.attendance.models import NotificationOutbox

@skipUnless(connection.vendor=='postgresql','Requires PostgreSQL locks')
class GradeConcurrencyTests(TransactionTestCase):
    setUp=test_api.Sprint3IntegrationTests.setUp
    c=test_api.Sprint3IntegrationTests.c
    book=test_api.Sprint3IntegrationTests.book
    assessment=test_api.Sprint3IntegrationTests.assessment
    fill=test_api.Sprint3IntegrationTests.fill
    published=test_api.Sprint3IntegrationTests.published
    revision=test_api.Sprint3IntegrationTests.revision

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

    def test_duplicate_book(self):
        job=(self.admin,'post','/api/v1/gradebooks/',{'classroom_id':str(self.cls.id),'subject_id':str(self.subj.id),'semester':'1','mode':'SCORE','regular_required':2})
        self.assertEqual(self.race([job,job]),[201,400]);self.assertEqual(GradeBook.objects.count(),1)

    def test_duplicate_assessment(self):
        book=self.book();job=(self.teacher,'post',f'/api/v1/gradebooks/{book}/assessments/',{'kind':'TX','slot':1,'title':'Test column'})
        self.assertEqual(self.race([job,job]),[201,400]);self.assertEqual(Assessment.objects.count(),1)

    def test_double_publish(self):
        assessment=self.assessment(self.book());self.fill(assessment)
        self.c().post(f'/api/v1/assessments/{assessment}/lock/',{},format='json')
        job=(self.admin,'post',f'/api/v1/assessments/{assessment}/publish/',{})
        self.assertEqual(self.race([job,job]),[200,400]);self.assertEqual(NotificationOutbox.objects.filter(event_type='GRADE_PUBLISHED').count(),1)

    def test_duplicate_revision(self):
        _,assessment=self.published();entry=GradeEntry.objects.get(assessment_id=assessment,student=self.st1)
        job=(self.teacher,'post',f'/api/v1/grade-entries/{entry.id}/revision-requests/',{'score':'7.0','reason':'Correct synthetic input error'})
        self.assertEqual(self.race([job,job]),[201,400]);self.assertEqual(GradeRevision.objects.count(),1)

    def test_double_approval(self):
        _,assessment=self.published();entry,rid=self.revision(assessment)
        job=(self.admin,'post',f'/api/v1/grade-revisions/{rid}/decision/',{'action':'approve'})
        self.assertEqual(self.race([job,job]),[200,400]);entry.refresh_from_db();self.assertEqual(entry.version,2)
        self.assertEqual(NotificationOutbox.objects.filter(event_type='GRADE_CORRECTED').count(),1)

    def test_save_lock_race_never_changes_locked_result_afterward(self):
        assessment=self.assessment(self.book());self.fill(assessment)
        jobs=[(self.teacher,'put',f'/api/v1/assessments/{assessment}/entries/',{'entries':[{'student_id':str(self.st1.id),'score':'7.0'}]}),
              (self.teacher,'post',f'/api/v1/assessments/{assessment}/lock/',{})]
        result=self.race(jobs);self.assertIn(result,[[200,200],[200,400]])
        self.assertEqual(Assessment.objects.get(pk=assessment).state,'LOCKED')
        entry=GradeEntry.objects.get(assessment_id=assessment,student=self.st1)
        self.assertIn(str(entry.score),['7.0','8.0'])
        self.assertEqual(self.fill(assessment).status_code,400)
