"""Django + DRF integration: requires installed dependencies and migrated test DB."""
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.identity.models import Account
from apps.schools.models import Tenant, Membership
from apps.academics.models import (AcademicYear,Subject,Classroom,Student,Enrollment,
                                  TeacherAssignment,GuardianLink,StudentAccount)
from apps.homework.models import HomeworkAssignment,HomeworkSubmission
from apps.attendance.models import NotificationOutbox
from apps.schools.models import AuditEvent


class HomeworkIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        today=timezone.localdate()
        cls.a=Tenant.objects.create(code='sprint4-a',name='School A');cls.b=Tenant.objects.create(code='sprint4-b',name='School B')
        def acct(username,tenant,role):
            x=Account.objects.create_user(username=username,password='TestingOnly!9876')
            Membership.objects.create(tenant=tenant,account=x,role=role,valid_from=today-timedelta(days=30))
            return x
        cls.teacher=acct('hwteacher',cls.a,'SUBJECT_TEACHER')
        cls.outsider=acct('hwoutsider',cls.a,'SUBJECT_TEACHER')
        cls.homeroom=acct('hwhomeroom',cls.a,'HOMEROOM_TEACHER')
        cls.parent=acct('hwparent',cls.a,'PARENT')
        cls.unverified=acct('hwunverified',cls.a,'PARENT')
        cls.pupil=acct('hwpupil',cls.a,'STUDENT')
        cls.other=acct('hwother',cls.b,'SCHOOL_ADMIN')
        cls.admin=acct('hwadmin',cls.a,'SCHOOL_ADMIN')
        year=AcademicYear.objects.create(tenant=cls.a,label='2026-2027',starts_on=today-timedelta(days=90),ends_on=today+timedelta(days=275))
        cls.clazz=Classroom.objects.create(tenant=cls.a,year=year,code='8A1',grade_level=8)
        cls.subject=Subject.objects.create(tenant=cls.a,code='MATH',name='Math')
        cls.stu=Student.objects.create(tenant=cls.a,student_code='ST1',full_name='Test student')
        cls.stu2=Student.objects.create(tenant=cls.a,student_code='ST2',full_name='Other student')
        for s in [cls.stu,cls.stu2]:Enrollment.objects.create(tenant=cls.a,student=s,classroom=cls.clazz,starts_on=today-timedelta(days=30))
        TeacherAssignment.objects.create(tenant=cls.a,teacher=cls.teacher,classroom=cls.clazz,
            subject=cls.subject,kind='SUBJECT',starts_on=today-timedelta(days=30))
        TeacherAssignment.objects.create(tenant=cls.a,teacher=cls.homeroom,classroom=cls.clazz,
            kind='HOMEROOM',starts_on=today-timedelta(days=30))
        GuardianLink.objects.create(tenant=cls.a,student=cls.stu,guardian=cls.parent,relation='FATHER',
            is_verified=True,valid_from=today-timedelta(days=30))
        GuardianLink.objects.create(tenant=cls.a,student=cls.stu2,guardian=cls.unverified,relation='MOTHER',
            is_verified=False,valid_from=today-timedelta(days=30))
        StudentAccount.objects.create(tenant=cls.a,student=cls.stu,account=cls.pupil)

    def c(self,actor=None,tenant=None):
        c=APIClient();c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(actor or self.teacher).access_token}',
            HTTP_X_TENANT_ID=str((tenant or self.a).id));return c

    def task(self):
        return self.c().post('/api/v1/homework/',{
            'classroom_id':str(self.clazz.id),'subject_id':str(self.subject.id),
            'title':'Bài tập số 1','instructions':'Giải phương trình',
            'due_at':(timezone.now()+timedelta(days=2)).isoformat(),'allow_late':False},format='json')

    def test_create_scope_and_publish(self):
        self.assertEqual(self.c(self.outsider).post('/api/v1/homework/',{
            'classroom_id':str(self.clazz.id),'subject_id':str(self.subject.id),'title':'Test','instructions':'Test',
            'due_at':(timezone.now()+timedelta(days=2)).isoformat()},format='json').status_code,403)
        r=self.task();self.assertEqual(r.status_code,201,r.content);id=r.json()['id']
        self.assertEqual(self.c(self.parent).get('/api/v1/homework/').json(),[])
        self.assertEqual(self.c().post(f'/api/v1/homework/{id}/publish/',{},format='json').status_code,200)
        self.assertEqual(len(self.c(self.parent).get('/api/v1/homework/').json()),1)
        self.assertEqual(self.c().post(f'/api/v1/homework/{id}/publish/',{},format='json').status_code,400)
        self.assertEqual(self.c(self.outsider).get(f'/api/v1/homework/{id}/').status_code,404)
        self.assertTrue(AuditEvent.objects.filter(action='HOMEWORK_PUBLISHED').exists())

    def test_student_submit_teacher_return_parent_read_only(self):
        r=self.task();id=r.json()['id'];self.c().post(f'/api/v1/homework/{id}/publish/',{},format='json')
        url=f'/api/v1/homework/{id}/my-submission/'
        self.assertEqual(self.c(self.parent).put(url,{'content_text':'Fake','action':'submit'},format='json').status_code,403)
        self.assertEqual(self.c(self.pupil).put(url,{'content_text':'x=5','action':'submit'},format='json').status_code,200)
        sub=HomeworkSubmission.objects.get(assignment_id=id,student=self.stu)
        self.assertEqual(self.c(self.pupil).put(url,{'content_text':'x=4','action':'submit','expected_version':0},format='json').status_code,409)
        self.assertEqual(self.c(self.outsider).post(f'/api/v1/homework/submissions/{sub.id}/return/',{'feedback':'Very good','expected_version':1},format='json').status_code,403)
        self.assertEqual(self.c().post(f'/api/v1/homework/submissions/{sub.id}/return/',{'feedback':'Tốt','score':'9.0','expected_version':1},format='json').status_code,200)
        self.assertEqual(self.c(self.pupil).put(url,{'content_text':'x=6','action':'submit','expected_version':sub.version},format='json').status_code,400)
        report=self.c(self.parent).get(f'/api/v1/homework/students/{self.stu.id}/').json()
        self.assertEqual(report['items'][0]['submission']['score'],'9.0')
        self.assertIsNone(report['items'][0]['submission']['content_text'])
        self.assertTrue(NotificationOutbox.objects.filter(event_type='HOMEWORK_RETURNED').exists())

    def test_unverified_guardian_and_cross_tenant(self):
        id=self.task().json()['id'];self.c().post(f'/api/v1/homework/{id}/publish/',{},format='json')
        self.assertEqual(self.c(self.unverified).get(f'/api/v1/homework/students/{self.stu2.id}/').status_code,404)
        self.assertEqual(self.c(self.other,self.b).get(f'/api/v1/homework/{id}/').status_code,404)
        self.assertEqual(self.c(self.other,self.b).get(f'/api/v1/homework/students/{self.stu.id}/').status_code,404)
        self.assertEqual(self.c(self.parent).get(f'/api/v1/homework/students/{self.stu2.id}/').status_code,404)

    def test_read_only_homeroom(self):
        id=self.task().json()['id'];self.c().post(f'/api/v1/homework/{id}/publish/',{},format='json')
        self.assertEqual(self.c(self.homeroom).get(f'/api/v1/homework/{id}/roster/').status_code,200)
        self.assertEqual(self.c(self.homeroom).post(f'/api/v1/homework/{id}/close/',{},format='json').status_code,403)

    def test_close_blocks_submit(self):
        id=self.task().json()['id'];self.c().post(f'/api/v1/homework/{id}/publish/',{},format='json')
        self.assertEqual(self.c().post(f'/api/v1/homework/{id}/close/',{},format='json').status_code,200)
        self.assertEqual(self.c(self.pupil).put(f'/api/v1/homework/{id}/my-submission/',
            {'content_text':'x=5','action':'submit'},format='json').status_code,400)

    def test_invalid_feedback_and_blank_work(self):
        id=self.task().json()['id'];self.c().post(f'/api/v1/homework/{id}/publish/',{},format='json')
        url=f'/api/v1/homework/{id}/my-submission/'
        self.assertEqual(self.c(self.pupil).put(url,{'content_text':'  ','action':'submit'},format='json').status_code,400)
        self.c(self.pupil).put(url,{'content_text':'x=5','action':'submit'},format='json')
        sub=HomeworkSubmission.objects.get(assignment_id=id)
        self.assertEqual(self.c().post(f'/api/v1/homework/submissions/{sub.id}/return/',{'score':'12','expected_version':1},format='json').status_code,400)
        self.assertEqual(self.c().post(f'/api/v1/homework/submissions/{sub.id}/return/',{'score':'8.5','expected_version':1},format='json').status_code,200)
