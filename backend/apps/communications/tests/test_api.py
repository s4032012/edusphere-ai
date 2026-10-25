"""Django integration scenarios; execute after migrations on test database."""
from datetime import timedelta
from uuid import uuid4
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.identity.models import Account
from apps.schools.models import Tenant,Membership
from apps.academics.models import AcademicYear,Classroom,Student,Subject,Enrollment,TeacherAssignment,GuardianLink,StudentAccount
from apps.communications.models import (Announcement,ConversationMessage,SupportTicket,NotificationReceipt)

class CommunicationAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        today=timezone.localdate();cls.a=Tenant.objects.create(code='comms-a',name='A');cls.b=Tenant.objects.create(code='comms-b',name='B')
        def actor(name,tenant,role):
            a=Account.objects.create_user(username=name,password='SyntheticOnly123!')
            Membership.objects.create(tenant=tenant,account=a,role=role,valid_from=today-timedelta(days=30))
            return a
        cls.admin=actor('com_admin',cls.a,'SCHOOL_ADMIN');cls.support=actor('com_support',cls.a,'SUPPORT_STAFF')
        cls.teacher=actor('com_teacher',cls.a,'SUBJECT_TEACHER');cls.other_teacher=actor('com_other_teacher',cls.a,'SUBJECT_TEACHER')
        cls.homeroom=actor('com_home',cls.a,'HOMEROOM_TEACHER');cls.parent=actor('com_parent',cls.a,'PARENT')
        cls.unverified=actor('com_unverified',cls.a,'PARENT');cls.pupil=actor('com_pupil',cls.a,'STUDENT')
        cls.foreign=actor('com_foreign',cls.b,'SCHOOL_ADMIN')
        year=AcademicYear.objects.create(tenant=cls.a,label='Y',starts_on=today-timedelta(days=90),ends_on=today+timedelta(days=360))
        cls.clazz=Classroom.objects.create(tenant=cls.a,year=year,code='8A1',grade_level=8)
        cls.subject=Subject.objects.create(tenant=cls.a,code='MATH',name='Toán')
        cls.student=Student.objects.create(tenant=cls.a,student_code='S1',full_name='Student One')
        cls.student2=Student.objects.create(tenant=cls.a,student_code='S2',full_name='Student Two')
        for s in (cls.student,cls.student2):
            Enrollment.objects.create(tenant=cls.a,student=s,classroom=cls.clazz,starts_on=today-timedelta(days=20))
        TeacherAssignment.objects.create(tenant=cls.a,classroom=cls.clazz,teacher=cls.teacher,subject=cls.subject,
            kind='SUBJECT',starts_on=today-timedelta(days=20))
        TeacherAssignment.objects.create(tenant=cls.a,classroom=cls.clazz,teacher=cls.homeroom,
            kind='HOMEROOM',starts_on=today-timedelta(days=20))
        GuardianLink.objects.create(tenant=cls.a,student=cls.student,guardian=cls.parent,
            relation='MOTHER',is_verified=True,valid_from=today-timedelta(days=20))
        GuardianLink.objects.create(tenant=cls.a,student=cls.student2,guardian=cls.unverified,
            relation='MOTHER',is_verified=False,valid_from=today-timedelta(days=20))
        StudentAccount.objects.create(tenant=cls.a,student=cls.student,account=cls.pupil)

    def cli(self,user=None,tenant=None):
        client=APIClient();client.credentials(HTTP_AUTHORIZATION='Bearer '+str(RefreshToken.for_user(user or self.parent).access_token),
            HTTP_X_TENANT_ID=str((tenant or self.a).id));return client

    def create_thread(self):
        return self.cli().post('/api/v1/comms/conversations/',{'student_id':str(self.student.id),
            'teacher_id':str(self.teacher.id),'guardian_id':str(self.parent.id)},format='json')

    def test_contacts_and_tenant_isolation(self):
        url=f'/api/v1/comms/students/{self.student.id}/contacts/'
        self.assertEqual(self.cli(self.parent).get(url).status_code,200)
        self.assertEqual(self.cli(self.unverified).get(url).status_code,404)
        self.assertEqual(self.cli(self.foreign, self.b).get(url).status_code,404)

    def test_thread_requires_live_links(self):
        r=self.create_thread();self.assertEqual(r.status_code,201,r.content)
        self.assertEqual(self.cli(self.unverified).post('/api/v1/comms/conversations/',{
            'student_id':str(self.student2.id),'teacher_id':str(self.teacher.id),
            'guardian_id':str(self.unverified.id)},format='json').status_code,404)
        self.assertEqual(self.cli(self.parent).post('/api/v1/comms/conversations/',{
            'student_id':str(self.student.id),'teacher_id':str(self.other_teacher.id),
            'guardian_id':str(self.parent.id)},format='json').status_code,404)
        self.assertEqual(self.cli(self.admin).get('/api/v1/comms/conversations/').json(),[])
        self.assertEqual(self.cli(self.foreign,self.b).get(f'/api/v1/comms/conversations/{r.json()["id"]}/messages/').status_code,404)
        GuardianLink.objects.filter(tenant=self.a,student=self.student,guardian=self.parent).update(is_active=False)
        self.assertEqual(self.cli(self.teacher).get(f'/api/v1/comms/conversations/{r.json()["id"]}/messages/').status_code,404)

    def test_idempotent_message_and_inbox(self):
        r=self.create_thread();tid=r.json()['id'];key=str(uuid4())
        url=f'/api/v1/comms/conversations/{tid}/messages/'
        data={'body':'Nhờ cô kiểm tra bài tập','client_key':key}
        self.assertEqual(self.cli().post(url,data,format='json').status_code,201)
        self.assertEqual(self.cli().post(url,data,format='json').status_code,200)
        self.assertEqual(ConversationMessage.objects.count(),1)
        self.assertEqual(self.cli().post(url,{'body':'khác','client_key':key},format='json').status_code,400)
        self.assertEqual(self.cli(self.unverified).get(url).status_code,404)
        items=self.cli(self.teacher).get('/api/v1/comms/notifications/').json();self.assertEqual(len(items),1)
        self.assertEqual(self.cli().post(f'/api/v1/comms/notifications/{items[0]["id"]}/read/').status_code,404)
        self.assertEqual(self.cli(self.teacher).post(f'/api/v1/comms/notifications/{items[0]["id"]}/read/').status_code,200)
        self.assertEqual(NotificationReceipt.objects.count(),1)

    def test_announcements_permissions_and_audience(self):
        url='/api/v1/comms/announcements/'
        data={'scope':'CLASS','classroom_id':str(self.clazz.id),'title':'Họp lớp','body':'Thứ sáu'}
        self.assertEqual(self.cli(self.teacher).post(url,data,format='json').status_code,403)
        self.assertEqual(self.cli(self.homeroom).post(url,data,format='json').status_code,201)
        notice=Announcement.objects.get()
        self.assertEqual(self.cli(self.parent).get(url).json(),[])
        self.assertEqual(self.cli(self.homeroom).post(f'{url}{notice.id}/publish/').status_code,200)
        self.assertEqual(len(self.cli(self.parent).get(url).json()),1)
        self.assertEqual(self.cli(self.unverified).get(url).json(),[])
        self.assertEqual(self.cli(self.parent).post(f'{url}{notice.id}/read/').status_code,200)
        self.assertEqual(self.cli(self.unverified).post(f'{url}{notice.id}/read/').status_code,404)
        self.assertEqual(self.cli(self.foreign,self.b).get(url).json(),[])

    def test_tickets_scope_reply_transitions(self):
        url='/api/v1/comms/tickets/'
        self.assertEqual(self.cli(self.teacher).post(url,{'category':'OTHER','subject':'Test','details':'x'},format='json').status_code,403)
        r=self.cli().post(url,{'category':'ACCOUNT','subject':'Không vào được app','details':'Cần hỗ trợ',
            'student_id':str(self.student.id)},format='json')
        self.assertEqual(r.status_code,201,r.content);tid=r.json()['id']
        self.assertEqual(self.cli(self.unverified).get(f'{url}{tid}/').status_code,404)
        self.assertEqual(self.cli(self.support).get(f'{url}{tid}/').status_code,200)
        self.assertEqual(self.cli(self.support).post(f'{url}{tid}/reply/',{'body':'Xin chào'},format='json').status_code,201)
        self.assertEqual(self.cli().post(f'{url}{tid}/transition/',{'state':'RESOLVED'},format='json').status_code,403)
        self.assertEqual(self.cli(self.support).post(f'{url}{tid}/transition/',{'state':'RESOLVED','expected_version':2},format='json').status_code,200)
        self.assertEqual(self.cli(self.support).post(f'{url}{tid}/transition/',{'state':'OPEN','expected_version':3},format='json').status_code,400)
        self.assertTrue(SupportTicket.objects.filter(pk=tid,assignee=self.support).exists())
