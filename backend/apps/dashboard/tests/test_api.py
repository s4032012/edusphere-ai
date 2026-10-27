"""Integration tests: needs Django, migrations, and a test database."""
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.identity.models import Account
from apps.schools.models import Tenant, Membership
from apps.academics.models import (AcademicYear, Classroom, Subject, Student, Enrollment,
                                   GuardianLink, StudentAccount)
from apps.attendance.models import AttendanceSession, AttendanceRecord
from apps.grades.models import GradeBook, Assessment, GradeEntry
from apps.homework.models import HomeworkAssignment, HomeworkSubmission
from apps.communications.models import Announcement, AnnouncementRecipient


class StudentDashboardAPITest(TestCase):
    @classmethod
    def setUpTestData(cls):
        today=timezone.localdate()
        cls.a=Tenant.objects.create(code='dash-a',name='THCS A')
        cls.b=Tenant.objects.create(code='dash-b',name='THCS B')
        def actor(name,tenant,role):
            user=Account.objects.create_user(username=name,password='Synthetic-Only!123')
            Membership.objects.create(tenant=tenant,account=user,role=role,valid_from=today-timedelta(days=60))
            return user
        cls.parent=actor('dash_parent',cls.a,'PARENT')
        cls.unverified=actor('dash_unverified',cls.a,'PARENT')
        cls.student_user=actor('dash_student',cls.a,'STUDENT')
        cls.admin=actor('dash_admin',cls.a,'SCHOOL_ADMIN')
        cls.foreign=actor('dash_foreign',cls.b,'PARENT')
        yr=AcademicYear.objects.create(tenant=cls.a,label='2026',starts_on=today-timedelta(days=60),ends_on=today+timedelta(days=360))
        cls.clazz=Classroom.objects.create(tenant=cls.a,year=yr,code='8A1',grade_level=8)
        subj=Subject.objects.create(tenant=cls.a,code='MATH',name='Toán')
        cls.s1=Student.objects.create(tenant=cls.a,student_code='D-1',full_name='Synthetic One')
        cls.s2=Student.objects.create(tenant=cls.a,student_code='D-2',full_name='Synthetic Two')
        for st in (cls.s1,cls.s2):
            Enrollment.objects.create(tenant=cls.a,student=st,classroom=cls.clazz,starts_on=today-timedelta(days=60))
        GuardianLink.objects.create(tenant=cls.a,student=cls.s1,guardian=cls.parent,relation='MOTHER',
                                    is_verified=True,valid_from=today-timedelta(days=60))
        GuardianLink.objects.create(tenant=cls.a,student=cls.s2,guardian=cls.unverified,relation='MOTHER',
                                    is_verified=False,valid_from=today-timedelta(days=60))
        StudentAccount.objects.create(tenant=cls.a,student=cls.s1,account=cls.student_user)
        cls.book=GradeBook.objects.create(tenant=cls.a,classroom=cls.clazz,subject=subj,semester='1',mode='SCORE',regular_required=2)
        cls.pub=Assessment.objects.create(tenant=cls.a,book=cls.book,kind='TX',slot=1,title='Công bố',
                                          state='PUBLISHED',created_by=cls.admin,published_at=timezone.now())
        cls.draft=Assessment.objects.create(tenant=cls.a,book=cls.book,kind='TX',slot=2,title='Bản nháp',
                                            state='DRAFT',created_by=cls.admin)
        for a in (cls.pub,cls.draft):
            GradeEntry.objects.create(tenant=cls.a,assessment=a,student=cls.s1,score='8.0',updated_by=cls.admin)
        submitted=AttendanceSession.objects.create(tenant=cls.a,classroom=cls.clazz,attendance_date=today,
                                                    state='SUBMITTED',created_by=cls.admin)
        draft=AttendanceSession.objects.create(tenant=cls.a,classroom=cls.clazz,attendance_date=today-timedelta(days=1),
                                                state='DRAFT',created_by=cls.admin)
        for session in (submitted,draft):
            AttendanceRecord.objects.create(tenant=cls.a,session=session,student=cls.s1,mark='ABSENT',updated_by=cls.admin)
        cls.hw=HomeworkAssignment.objects.create(tenant=cls.a,classroom=cls.clazz,subject=subj,teacher=cls.admin,
                       title='Bài tập mới',instructions='Demo',due_at=timezone.now()+timedelta(days=1),state='PUBLISHED')
        HomeworkSubmission.objects.create(tenant=cls.a,assignment=cls.hw,student=cls.s1,
                                           content_text='Test',state='SUBMITTED')
        notice=Announcement.objects.create(tenant=cls.a,author=cls.admin,scope='CLASS',classroom=cls.clazz,
                                           title='Lịch họp',body='Bản tin giả lập',state='PUBLISHED',published_at=timezone.now())
        AnnouncementRecipient.objects.create(tenant=cls.a,announcement=notice,account=cls.parent)

    def cli(self,user=None,tenant=None):
        c=APIClient()
        if user is not False:
            c.credentials(HTTP_AUTHORIZATION='Bearer '+str(RefreshToken.for_user(user or self.parent).access_token),
                          HTTP_X_TENANT_ID=str((tenant or self.a).id))
        return c

    def url(self, student):return f'/api/v1/dashboard/students/{student.id}/'

    def test_parent_only_verified_student_list(self):
        r=self.cli().get('/api/v1/dashboard/children/')
        self.assertEqual(r.status_code,200)
        self.assertEqual([s['student_code'] for s in r.json()['students']],['D-1'])
        self.assertEqual(self.cli(self.unverified).get(self.url(self.s2)).status_code,404)
        self.assertEqual(self.cli().get(self.url(self.s2)).status_code,404)

    def test_released_information_only(self):
        r=self.cli().get(self.url(self.s1))
        self.assertEqual(r.status_code,200,r.content)
        data=r.json()
        self.assertEqual(len(data['grades']['items']),1)
        self.assertEqual(data['grades']['items'][0]['title'],'Công bố')
        self.assertEqual(data['attendance']['recorded_days'],1)
        self.assertEqual(data['homework']['summary']['submitted_or_returned'],1)
        self.assertEqual(data['announcements'][0]['title'],'Lịch họp')
        self.assertNotIn('content_text',str(data))

    def test_student_self_and_admin_denied(self):
        self.assertEqual(self.cli(self.student_user).get(self.url(self.s1)).status_code,200)
        self.assertEqual(self.cli(self.student_user).get(self.url(self.s2)).status_code,404)
        self.assertEqual(self.cli(self.admin).get(self.url(self.s1)).status_code,403)

    def test_cross_tenant_denied(self):
        self.assertEqual(self.cli(self.foreign,self.b).get(self.url(self.s1)).status_code,404)
        self.assertEqual(self.cli(self.parent,self.b).get(self.url(self.s1)).status_code,404)

    def test_revocation_takes_effect_without_caching(self):
        self.assertEqual(self.cli().get(self.url(self.s1)).status_code,200)
        GuardianLink.objects.filter(tenant=self.a,guardian=self.parent,student=self.s1).update(is_active=False)
        self.assertEqual(self.cli().get(self.url(self.s1)).status_code,404)

    def test_preview_does_not_call_external_ai(self):
        r=self.cli().get(self.url(self.s1)+'ai-preview/')
        self.assertEqual(r.status_code,200,r.content)
        self.assertFalse(r.json()['model_called'])
        self.assertFalse(r.json()['exported_to_provider'])
        self.assertTrue(all(entry['source'] for entry in r.json()['sentences']))
