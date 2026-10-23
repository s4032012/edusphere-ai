"""Integration tests. Run with Django + PostgreSQL before accepting Sprint 2."""
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.identity.models import Account
from apps.schools.models import Tenant,Membership,AuditEvent
from apps.academics.models import (AcademicYear,Classroom,Student,Subject,Enrollment,
                                   TeacherAssignment,GuardianLink)
from apps.attendance.models import AttendanceSession,AttendanceRecord,LeaveRequest,NotificationOutbox

class Sprint2APITests(TestCase):
    def setUp(self):
        self.today=timezone.localdate()
        self.a=Tenant.objects.create(code='at-a',name='School A')
        self.b=Tenant.objects.create(code='at-b',name='School B')
        self.admin=Account.objects.create_user('at_admin',password='testPassword123!')
        self.homeroom=Account.objects.create_user('at_ht',password='testPassword123!')
        self.subject_teacher=Account.objects.create_user('at_st',password='testPassword123!')
        self.parent=Account.objects.create_user('at_parent',password='testPassword123!')
        self.unverified=Account.objects.create_user('at_unverified',password='testPassword123!')
        self.other=Account.objects.create_user('at_other',password='testPassword123!')
        for who,tenant,role in [(self.admin,self.a,'SCHOOL_ADMIN'),(self.homeroom,self.a,'HOMEROOM_TEACHER'),
            (self.subject_teacher,self.a,'SUBJECT_TEACHER'),(self.parent,self.a,'PARENT'),
            (self.unverified,self.a,'PARENT'),(self.other,self.b,'SCHOOL_ADMIN')]:
            Membership.objects.create(tenant=tenant,account=who,role=role,valid_from=self.today-timedelta(days=90))
        yr=AcademicYear.objects.create(tenant=self.a,label='Pilot 2026',starts_on=self.today-timedelta(days=100),ends_on=self.today+timedelta(days=200))
        self.clazz=Classroom.objects.create(tenant=self.a,year=yr,code='8A1',grade_level=8)
        self.student=Student.objects.create(tenant=self.a,student_code='AT1',full_name='Test Student')
        self.student2=Student.objects.create(tenant=self.a,student_code='AT2',full_name='Test Student2')
        self.outsider=Student.objects.create(tenant=self.b,student_code='ATB',full_name='Other school Student')
        for stu in [self.student,self.student2]:
            Enrollment.objects.create(tenant=self.a,student=stu,classroom=self.clazz,starts_on=self.today-timedelta(days=50))
        TeacherAssignment.objects.create(tenant=self.a,teacher=self.homeroom,classroom=self.clazz,kind='HOMEROOM',starts_on=self.today-timedelta(days=50))
        math=Subject.objects.create(tenant=self.a,code='MA',name='Math')
        TeacherAssignment.objects.create(tenant=self.a,teacher=self.subject_teacher,classroom=self.clazz,subject=math,kind='SUBJECT',starts_on=self.today-timedelta(days=50))
        self.link=GuardianLink.objects.create(tenant=self.a,student=self.student,guardian=self.parent,
            relation='FATHER',valid_from=self.today-timedelta(days=50),is_verified=True)
        GuardianLink.objects.create(tenant=self.a,student=self.student2,guardian=self.unverified,
            relation='OTHER',valid_from=self.today-timedelta(days=50),is_verified=False)
    def c(self,person=None,tenant=None):
        cli=APIClient()
        cli.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(person or self.admin).access_token}',
            HTTP_X_TENANT_ID=str((tenant or self.a).id))
        return cli
    def start(self,person=None):
        return self.c(person).post('/api/v1/attendance/sessions/',
            {'classroom_id':str(self.clazz.id),'attendance_date':self.today.isoformat()},format='json')
    def test_homeroom_can_start_and_duplicate_is_idempotent(self):
        a=self.start(self.homeroom);b=self.start(self.homeroom)
        self.assertEqual(a.status_code,201)
        self.assertEqual(b.status_code,200)
        self.assertEqual(a.json()['id'],b.json()['id'])
    def test_subject_teacher_cannot_start_daily_attendance(self):
        self.assertEqual(self.start(self.subject_teacher).status_code,403)
    def test_parent_cannot_start_daily_attendance(self):
        self.assertEqual(self.start(self.parent).status_code,403)
    def test_tenant_isolation(self):
        self.assertEqual(self.c(self.other,self.a).get('/api/v1/attendance/sessions/').status_code,404)
        self.assertEqual(self.c(self.other,self.b).get(f'/api/v1/attendance/sessions/{self.start().json()["id"]}/').status_code,404)
    def test_bulk_rejects_student_outside_roster(self):
        sid=self.start().json()['id']
        res=self.c(self.homeroom).put(f'/api/v1/attendance/sessions/{sid}/records/',
            {'records':[{'student_id':str(self.outsider.id),'mark':'PRESENT'}]},format='json')
        self.assertEqual(res.status_code,400)
        self.assertFalse(AttendanceRecord.objects.exists())
    def test_submit_requires_all_roster_and_locks_changes(self):
        sid=self.start().json()['id'];cli=self.c(self.homeroom)
        rows=[{'student_id':str(self.student.id),'mark':'ABSENT'}]
        self.assertEqual(cli.put(f'/api/v1/attendance/sessions/{sid}/records/',{'records':rows},format='json').status_code,200)
        self.assertEqual(cli.post(f'/api/v1/attendance/sessions/{sid}/submit/',{},format='json').status_code,400)
        rows.append({'student_id':str(self.student2.id),'mark':'PRESENT'})
        self.assertEqual(cli.put(f'/api/v1/attendance/sessions/{sid}/records/',{'records':rows},format='json').status_code,200)
        self.assertEqual(cli.post(f'/api/v1/attendance/sessions/{sid}/submit/',{},format='json').status_code,200)
        self.assertEqual(cli.put(f'/api/v1/attendance/sessions/{sid}/records/',{'records':rows},format='json').status_code,400)
        self.assertEqual(NotificationOutbox.objects.filter(recipient=self.parent,event_type='UNEXCUSED_ABSENCE').count(),1)
        self.assertEqual(self.c().post(f'/api/v1/attendance/sessions/{sid}/lock/',{},format='json').json()['state'],'LOCKED')
        self.assertTrue(AuditEvent.objects.filter(tenant=self.a,action='ATTENDANCE_SUBMITTED').exists())
    def test_parent_can_apply_and_only_homeroom_approve(self):
        payload={'student_id':str(self.student.id),'from_date':self.today.isoformat(),
                 'through_date':self.today.isoformat(),'reason':'Khám bệnh theo lịch'}
        res=self.c(self.parent).post('/api/v1/leave-requests/',payload,format='json')
        self.assertEqual(res.status_code,201)
        rid=res.json()['id']
        self.assertEqual(self.c(self.subject_teacher).post(f'/api/v1/leave-requests/{rid}/decision/',{'action':'approve'},format='json').status_code,403)
        self.assertEqual(self.c(self.homeroom).post(f'/api/v1/leave-requests/{rid}/decision/',{'action':'approve'},format='json').status_code,200)
        self.assertEqual(self.c(self.homeroom).post(f'/api/v1/leave-requests/{rid}/decision/',{'action':'reject'},format='json').status_code,400)
        self.assertEqual(NotificationOutbox.objects.filter(recipient=self.parent,event_type='LEAVE_DECIDED').count(),1)
    def test_unverified_guardian_blocked(self):
        res=self.c(self.unverified).post('/api/v1/leave-requests/',{'student_id':str(self.student2.id),
            'from_date':self.today.isoformat(),'through_date':self.today.isoformat(),'reason':'Chuyện gia đình'},format='json')
        self.assertEqual(res.status_code,403)
    def test_overlap_leave_rejected(self):
        payload={'student_id':str(self.student.id),'from_date':self.today.isoformat(),'through_date':self.today.isoformat(),'reason':'Xin nghỉ khám bệnh'}
        self.assertEqual(self.c(self.parent).post('/api/v1/leave-requests/',payload,format='json').status_code,201)
        self.assertEqual(self.c(self.parent).post('/api/v1/leave-requests/',payload,format='json').status_code,400)
    def test_parent_can_withdraw_own_pending_request(self):
        payload={'student_id':str(self.student.id),'from_date':self.today.isoformat(),'through_date':self.today.isoformat(),'reason':'Xin nghỉ hôm nay'}
        rid=self.c(self.parent).post('/api/v1/leave-requests/',payload,format='json').json()['id']
        self.assertEqual(self.c(self.parent).post(f'/api/v1/leave-requests/{rid}/withdraw/',{},format='json').json()['state'],'WITHDRAWN')
        self.assertEqual(self.c(self.parent).post(f'/api/v1/leave-requests/{rid}/withdraw/',{},format='json').status_code,400)
    def test_parent_read_history_only_after_submission(self):
        sid=self.start().json()['id'];cli=self.c(self.homeroom)
        rows=[{'student_id':str(self.student.id),'mark':'ABSENT'},{'student_id':str(self.student2.id),'mark':'PRESENT'}]
        cli.put(f'/api/v1/attendance/sessions/{sid}/records/',{'records':rows},format='json')
        self.assertEqual(self.c(self.parent).get(f'/api/v1/attendance/students/{self.student.id}/').json(),[])
        cli.post(f'/api/v1/attendance/sessions/{sid}/submit/',{},format='json')
        history=self.c(self.parent).get(f'/api/v1/attendance/students/{self.student.id}/')
        self.assertEqual(history.status_code,200);self.assertEqual(history.json()[0]['mark'],'ABSENT')
        self.assertEqual(self.c(self.parent).get(f'/api/v1/attendance/students/{self.student2.id}/').status_code,404)
        self.assertEqual(self.c(self.subject_teacher).get(f'/api/v1/attendance/students/{self.student.id}/').status_code,403)
    def test_approved_leave_explains_absence_without_overwriting_mark(self):
        sid=self.start().json()['id'];cli=self.c(self.homeroom)
        rows=[{'student_id':str(self.student.id),'mark':'ABSENT'},{'student_id':str(self.student2.id),'mark':'PRESENT'}]
        cli.put(f'/api/v1/attendance/sessions/{sid}/records/',{'records':rows},format='json')
        cli.post(f'/api/v1/attendance/sessions/{sid}/submit/',{},format='json')
        payload={'student_id':str(self.student.id),'from_date':self.today.isoformat(),
                 'through_date':self.today.isoformat(),'reason':'Khám bệnh theo lịch'}
        rid=self.c(self.parent).post('/api/v1/leave-requests/',payload,format='json').json()['id']
        self.c(self.homeroom).post(f'/api/v1/leave-requests/{rid}/decision/',{'action':'approve'},format='json')
        history=self.c(self.parent).get(f'/api/v1/attendance/students/{self.student.id}/').json()
        self.assertEqual(history[0]['mark'],'ABSENT')
        self.assertEqual(history[0]['effective_status'],'EXCUSED_ABSENCE')
        self.assertEqual(NotificationOutbox.objects.filter(recipient=self.parent,event_type='UNEXCUSED_ABSENCE',state='CANCELED').count(),1)

    def create_leave(self):
        return self.c(self.parent).post('/api/v1/leave-requests/',{
            'student_id':str(self.student.id),'from_date':str(self.today),
            'through_date':str(self.today),'reason':'Synthetic leave reason'},format='json').json()['id']

    def complete_draft(self):
        sid=self.start(self.homeroom).json()['id']
        response=self.c(self.homeroom).put(f'/api/v1/attendance/sessions/{sid}/records/',{'records':[
            {'student_id':str(self.student.id),'mark':'ABSENT'},
            {'student_id':str(self.student2.id),'mark':'PRESENT'}]},format='json')
        self.assertEqual(response.status_code,200)
        return sid

    def test_revoked_guardian_loses_history_leave_and_notification_access(self):
        sid=self.complete_draft();rid=self.create_leave()
        self.c(self.homeroom).post(f'/api/v1/attendance/sessions/{sid}/submit/',{},format='json')
        parent=self.c(self.parent)
        self.assertEqual(len(parent.get('/api/v1/notifications/').json()),1)
        self.link.is_active=False;self.link.save()
        self.assertEqual(parent.get('/api/v1/notifications/').json(),[])
        self.assertEqual(parent.get('/api/v1/leave-requests/').json(),[])
        self.assertEqual(parent.get(f'/api/v1/attendance/students/{self.student.id}/').status_code,404)
        self.assertEqual(parent.post(f'/api/v1/leave-requests/{rid}/withdraw/',{},format='json').status_code,403)

    def test_other_guardian_cannot_read_sensitive_leave_reason(self):
        self.create_leave()
        GuardianLink.objects.create(tenant=self.a,student=self.student,guardian=self.unverified,
            relation='MOTHER',is_verified=True,valid_from=self.today)
        self.assertEqual(self.c(self.unverified).get('/api/v1/leave-requests/').json(),[])
        self.assertEqual(len(self.c(self.parent).get('/api/v1/leave-requests/').json()),1)

    def test_revoked_assignment_blocks_all_teacher_operations(self):
        sid=self.complete_draft();rid=self.create_leave();teacher=self.c(self.homeroom)
        TeacherAssignment.objects.filter(teacher=self.homeroom).update(is_active=False)
        self.assertEqual(teacher.get('/api/v1/attendance/sessions/').json(),[])
        self.assertEqual(teacher.get('/api/v1/leave-requests/').json(),[])
        self.assertEqual(teacher.get(f'/api/v1/attendance/sessions/{sid}/').status_code,403)
        self.assertEqual(teacher.post(f'/api/v1/attendance/sessions/{sid}/submit/',{},format='json').status_code,403)
        self.assertEqual(teacher.put(f'/api/v1/attendance/sessions/{sid}/records/',{'records':[]},format='json').status_code,403)
        self.assertEqual(teacher.post(f'/api/v1/leave-requests/{rid}/decision/',{'action':'approve'},format='json').status_code,403)

    def test_cross_tenant_mutations_leave_and_history_are_hidden(self):
        sid=self.complete_draft();rid=self.create_leave();other=self.c(self.other,self.b)
        for suffix in ['submit','lock']:
            self.assertEqual(other.post(f'/api/v1/attendance/sessions/{sid}/{suffix}/',{},format='json').status_code,404)
        self.assertEqual(other.put(f'/api/v1/attendance/sessions/{sid}/records/',{'records':[]},format='json').status_code,404)
        for suffix in ['decision','withdraw']:
            self.assertEqual(other.post(f'/api/v1/leave-requests/{rid}/{suffix}/',{},format='json').status_code,404)
        self.assertEqual(other.get(f'/api/v1/attendance/students/{self.student.id}/').status_code,404)
        self.assertEqual(other.get('/api/v1/leave-requests/').json(),[])
        self.assertEqual(other.get('/api/v1/notifications/').json(),[])

    def test_published_roster_survives_ended_enrollment(self):
        sid=self.complete_draft();self.c().post(f'/api/v1/attendance/sessions/{sid}/submit/',{},format='json')
        Enrollment.objects.filter(student=self.student).update(is_active=False)
        response=self.c().get(f'/api/v1/attendance/sessions/{sid}/')
        self.assertEqual(len(response.json()['roster']),2)
        self.assertTrue(any(r['id']==str(self.student.id) and r['mark']=='ABSENT' for r in response.json()['roster']))

    def test_invalid_dates_payloads_and_duplicate_rows_are_atomic(self):
        for date in [str(self.today+timedelta(days=1)),str(self.today-timedelta(days=8)),'not-a-date']:
            self.assertEqual(self.c().post('/api/v1/attendance/sessions/',{'classroom_id':str(self.clazz.id),'attendance_date':date},format='json').status_code,400)
        sid=self.start().json()['id'];row={'student_id':str(self.student.id),'mark':'PRESENT'}
        for rows in [[row,row],[row,{'student_id':str(self.student2.id),'mark':'UNKNOWN'}],[row,{'student_id':'bad','mark':'ABSENT'}]]:
            self.assertEqual(self.c().put(f'/api/v1/attendance/sessions/{sid}/records/',{'records':rows},format='json').status_code,400)
        self.assertEqual(AttendanceRecord.objects.count(),0)
        self.assertEqual(self.c().get('/api/v1/attendance/sessions/?classroom_id=bad').status_code,400)
        self.assertEqual(self.c().get('/api/v1/leave-requests/?student_id=bad').status_code,400)

    def test_draft_cannot_lock_and_only_admin_can_lock_submitted(self):
        sid=self.complete_draft();url=f'/api/v1/attendance/sessions/{sid}/lock/'
        self.assertEqual(self.c().post(url,{},format='json').status_code,400)
        self.c().post(f'/api/v1/attendance/sessions/{sid}/submit/',{},format='json')
        self.assertEqual(self.c(self.homeroom).post(url,{},format='json').status_code,403)
        self.assertEqual(self.c().post(url,{},format='json').status_code,200)
        self.assertEqual(self.c().post(url,{},format='json').status_code,400)

    def test_approved_leave_before_submission_suppresses_absence_notification(self):
        rid=self.create_leave()
        self.c(self.homeroom).post(f'/api/v1/leave-requests/{rid}/decision/',{'action':'approve'},format='json')
        sid=self.complete_draft();self.c().post(f'/api/v1/attendance/sessions/{sid}/submit/',{},format='json')
        self.assertFalse(NotificationOutbox.objects.filter(event_type='UNEXCUSED_ABSENCE').exists())
        self.assertEqual(self.c(self.parent).get('/api/v1/notifications/').json()[0]['type'],'LEAVE_DECIDED')

    def test_submit_audit_failure_rolls_back_state_and_outbox(self):
        from unittest.mock import patch
        sid=self.complete_draft()
        with patch('apps.access.views.TenantAPIView.audit',side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.c().post(f'/api/v1/attendance/sessions/{sid}/submit/',{},format='json')
        self.assertEqual(AttendanceSession.objects.get(id=sid).state,'DRAFT')
        self.assertFalse(NotificationOutbox.objects.exists())

    def test_parent_cannot_view_draft_roster_or_decide(self):
        sid=self.complete_draft();rid=self.create_leave();parent=self.c(self.parent)
        self.assertEqual(parent.get('/api/v1/attendance/sessions/').json(),[])
        self.assertEqual(parent.get(f'/api/v1/attendance/sessions/{sid}/').status_code,403)
        self.assertEqual(parent.post(f'/api/v1/leave-requests/{rid}/decision/',{'action':'approve'},format='json').status_code,403)

    def test_leave_cannot_extend_beyond_academic_year(self):
        year=self.clazz.year;year.ends_on=self.today;year.save()
        response=self.c(self.parent).post('/api/v1/leave-requests/',{'student_id':str(self.student.id),
            'from_date':str(self.today),'through_date':str(self.today+timedelta(days=1)),'reason':'Synthetic reason'},format='json')
        self.assertEqual(response.status_code,400)

    def test_academic_permission_revocation_hides_notifications_and_leaves(self):
        sid=self.complete_draft();self.create_leave()
        self.c().post(f'/api/v1/attendance/sessions/{sid}/submit/',{},format='json')
        self.link.can_view_academic=False;self.link.save()
        self.assertEqual(self.c(self.parent).get('/api/v1/notifications/').json(),[])
        self.assertEqual(self.c(self.parent).get('/api/v1/leave-requests/').json(),[])
