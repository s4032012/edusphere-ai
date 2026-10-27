from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch
from django.test import TestCase
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from apps.academics.models import AcademicYear,Classroom,Enrollment,GuardianLink,StudentAccount,Subject,TeacherAssignment
from apps.schools.models import Membership,AuditEvent
from apps.attendance.models import AttendanceSession,AttendanceRecord,NotificationOutbox
from apps.communications.models import Announcement,AnnouncementRecipient,AnnouncementRead,Conversation,ConversationMessage,NotificationReceipt
from apps.homework.models import HomeworkAssignment,HomeworkSubmission
from apps.grades.models import Assessment,GradeEntry
from apps.dashboard.views import DashboardThrottle
from . import test_api

class DashboardSecurityTests(TestCase):
    setUpTestData=classmethod(test_api.StudentDashboardAPITest.setUpTestData.__func__)
    cli=test_api.StudentDashboardAPITest.cli
    url=test_api.StudentDashboardAPITest.url
    def setUp(self):cache.clear()
    def snapshot(self):
        r=self.cli().get(self.url(self.s1));self.assertEqual(r.status_code,200,r.content);return r.json()
    def task(self,**kwargs):
        return HomeworkAssignment.objects.create(tenant=self.a,classroom=self.clazz,subject=self.book.subject,teacher=self.admin,
            title=kwargs.pop('title','Additional task'),instructions='SECRET_INSTRUCTIONS',due_at=kwargs.pop('due_at',timezone.now()+timedelta(days=1)),state=kwargs.pop('state','PUBLISHED'),**kwargs)
    def notice(self,scope='CLASS',**kwargs):
        return Announcement.objects.create(tenant=self.a,author=self.admin,scope=scope,title='Other notice',body='SECRET_NOTICE_BODY',
            state='PUBLISHED',published_at=timezone.now(),**kwargs)

    def test_mixed_admin_roles_do_not_expand_children_or_snapshot(self):
        for role in ['SCHOOL_ADMIN','HOMEROOM_TEACHER']:
            Membership.objects.create(tenant=self.a,account=self.parent,role=role,valid_from=timezone.localdate())
        children=self.cli().get('/api/v1/dashboard/children/').json()['students']
        self.assertEqual([s['id'] for s in children],[str(self.s1.id)])
        for suffix in ['','ai-preview/']:self.assertEqual(self.cli().get(self.url(self.s2)+suffix).status_code,404)
    def test_student_mapping_and_guardian_membership_rechecked(self):
        client=self.cli(self.student_user)
        self.assertEqual(client.get(self.url(self.s1)).status_code,200)
        StudentAccount.objects.filter(account=self.student_user).update(student=self.s2)
        self.assertEqual(client.get(self.url(self.s1)).status_code,404)
        self.assertEqual(client.get(self.url(self.s2)).status_code,200)
        client=self.cli();Membership.objects.filter(account=self.parent).update(valid_to=timezone.localdate()-timedelta(days=1))
        self.assertEqual(client.get(self.url(self.s1)).status_code,404)
    def test_future_expired_unverified_or_private_guardian_links_deny(self):
        link=GuardianLink.objects.get(guardian=self.parent)
        for changes in [{'valid_from':timezone.localdate()+timedelta(days=1)},{'valid_to':timezone.localdate()-timedelta(days=1)},
                        {'can_view_academic':False},{'is_verified':False},{'is_active':False}]:
            with self.subTest(changes=changes):
                GuardianLink.objects.filter(pk=link.id).update(valid_from=timezone.localdate()-timedelta(days=60),valid_to=None,can_view_academic=True,is_verified=True,is_active=True,**{})
                GuardianLink.objects.filter(pk=link.id).update(**changes)
                self.assertEqual(self.cli().get(self.url(self.s1)).status_code,404)
                self.assertEqual(self.cli().get(self.url(self.s1)+'ai-preview/').status_code,404)
    def test_archived_student_hidden_even_with_live_link(self):
        self.s1.is_active=False;self.s1.save()
        self.assertEqual(self.cli().get('/api/v1/dashboard/children/').json()['students'],[])
        self.assertEqual(self.cli().get(self.url(self.s1)).status_code,404)
    def test_expired_year_or_missing_enrollment_is_explicit_empty(self):
        for queryset,changes in [(Enrollment.objects.filter(student=self.s1),{'is_active':False}),
                                 (AcademicYear.objects.filter(id=self.clazz.year_id),{'ends_on':timezone.localdate()-timedelta(days=1)})]:
            queryset.update(**changes);d=self.snapshot()
            self.assertEqual(d['enrollment_status'],'NONE');self.assertIsNone(d['student']['classroom'])
            self.assertEqual(d['grades']['items'],[]);self.assertEqual(d['homework']['summary']['total'],0);self.assertEqual(d['announcements'],[])
    def test_multiple_classes_fail_closed_but_duplicate_same_class_does_not(self):
        Enrollment.objects.create(tenant=self.a,student=self.s1,classroom=self.clazz,starts_on=timezone.localdate())
        self.assertEqual(self.snapshot()['enrollment_status'],'CURRENT')
        other=Classroom.objects.create(tenant=self.a,year=self.clazz.year,code='8A2',grade_level=8)
        Enrollment.objects.create(tenant=self.a,student=self.s1,classroom=other,starts_on=timezone.localdate())
        d=self.snapshot();self.assertEqual(d['enrollment_status'],'AMBIGUOUS');self.assertEqual(d['grades']['items'],[])
    def test_class_transfer_excludes_old_class_and_other_child_notice(self):
        other=Classroom.objects.create(tenant=self.a,year=self.clazz.year,code='9B',grade_level=9)
        n=self.notice(classroom=other);AnnouncementRecipient.objects.create(tenant=self.a,account=self.parent,announcement=n)
        self.assertNotIn(str(n.id),[x['id'] for x in self.snapshot()['announcements']])
        Enrollment.objects.filter(student=self.s1).update(classroom=other)
        d=self.snapshot();self.assertEqual(d['grades']['items'],[]);self.assertEqual(d['attendance']['recorded_days'],0);self.assertEqual(d['homework']['summary']['total'],0)
        self.assertEqual([x['id'] for x in d['announcements']],[str(n.id)])
    def test_attendance_window_is_inclusive_and_draft_not_in_denominator(self):
        today=timezone.localdate()
        for delta,mark in [(-29,'PRESENT'),(-30,'ABSENT'),(1,'LATE')]:
            session=AttendanceSession.objects.create(tenant=self.a,classroom=self.clazz,attendance_date=today+timedelta(days=delta),state='LOCKED',created_by=self.admin)
            AttendanceRecord.objects.create(tenant=self.a,session=session,student=self.s1,mark=mark,updated_by=self.admin)
        a=self.snapshot()['attendance'];self.assertEqual(a['recorded_days'],2);self.assertEqual(a['PRESENT'],1);self.assertEqual(a['ABSENT'],1);self.assertEqual(a['LATE'],0)
    def test_deadline_same_day_draft_and_closed_homework(self):
        now=timezone.now();late=self.task(due_at=now-timedelta(seconds=1),allow_late=True)
        HomeworkSubmission.objects.create(tenant=self.a,student=self.s1,assignment=late,state='DRAFT',content_text='SECRET_ANSWER')
        closed=self.task(state='CLOSED',due_at=now+timedelta(days=2))
        denied=self.task(due_at=now-timedelta(hours=1),allow_late=False)
        d=self.snapshot();items={x['id']:x for x in d['homework']['items']}
        self.assertEqual(items[str(late.id)]['status'],'OVERDUE');self.assertTrue(items[str(late.id)]['actionable'])
        self.assertFalse(items[str(closed.id)]['actionable']);self.assertFalse(items[str(denied.id)]['actionable'])
        self.assertEqual(d['homework']['summary']['overdue'],2);self.assertNotIn('SECRET_ANSWER',str(d))
    def test_feed_limits_do_not_limit_homework_summary_or_hide_actionable(self):
        for i in range(12):self.task(state='CLOSED',title=f'Closed {i}')
        action=self.task(title='Urgent',due_at=timezone.now()-timedelta(hours=1),allow_late=True)
        d=self.snapshot();self.assertEqual(len(d['homework']['items']),8);self.assertEqual(d['homework']['summary']['total'],14)
        self.assertEqual(d['homework']['items'][0]['id'],str(action.id));self.assertEqual(d['homework']['summary']['pending_action'],1)
    def test_grade_comment_zero_and_no_unreleased_results(self):
        GradeEntry.objects.filter(assessment=self.pub).update(score=0,note='Published teacher note')
        Assessment.objects.filter(pk=self.draft.id).update(state='LOCKED')
        d=self.snapshot();self.assertEqual(len(d['grades']['items']),1);self.assertEqual(d['grades']['items'][0]['score'],'0.0')
        self.assertEqual(d['grades']['items'][0]['note'],'Published teacher note')
        preview=self.cli().get(self.url(self.s1)+'ai-preview/').json();self.assertNotIn('Published teacher note',str(preview))
    def test_grade_limit_and_preview_count_are_labelled_as_feed(self):
        for kind in ['TX','GK','CK']:
            for slot in [1,2,3,4]:
                if kind=='TX' and slot in [1,2]:continue
                a=Assessment.objects.create(tenant=self.a,book=self.book,kind=kind,slot=slot,title='Published',state='PUBLISHED',published_at=timezone.now(),created_by=self.admin)
                GradeEntry.objects.create(tenant=self.a,assessment=a,student=self.s1,score=7,updated_by=self.admin)
        self.assertEqual(len(self.snapshot()['grades']['items']),8)
        preview=self.cli().get(self.url(self.s1)+'ai-preview/').json()
        self.assertIn('tối đa 8',preview['sentences'][-1]['text'])
    def test_cross_tenant_related_subjects_and_attendance_are_excluded(self):
        foreign_subject=Subject.objects.create(tenant=self.b,code='SECRET',name='SECRET_FOREIGN_SUBJECT')
        self.book.subject=foreign_subject;self.book.save();HomeworkAssignment.objects.filter(pk=self.hw.id).update(subject=foreign_subject)
        AttendanceSession.objects.filter(tenant=self.a,state='SUBMITTED').update(tenant=self.b)
        d=self.snapshot();self.assertEqual(d['grades']['items'],[]);self.assertEqual(d['homework']['items'],[]);self.assertEqual(d['attendance']['recorded_days'],0)
        self.assertNotIn('SECRET_FOREIGN',str(d))
    def test_notices_require_snapshot_and_receipts_are_per_viewer(self):
        n=self.notice(scope='SCHOOL')
        self.assertNotIn(str(n.id),[x['id'] for x in self.snapshot()['announcements']])
        AnnouncementRecipient.objects.create(tenant=self.a,account=self.parent,announcement=n)
        AnnouncementRead.objects.create(tenant=self.a,account=self.parent,announcement=n)
        d=self.snapshot();self.assertTrue(next(x for x in d['announcements'] if x['id']==str(n.id))['read']);self.assertNotIn('SECRET_NOTICE_BODY',str(d))
    def test_inbox_filters_unknown_foreign_and_revoked_message_events(self):
        # Another child is legitimately visible to the same guardian; revoke only its thread relationship.
        GuardianLink.objects.create(tenant=self.a,guardian=self.parent,student=self.s2,is_verified=True,valid_from=timezone.localdate(),relation='MOTHER')
        Membership.objects.create(tenant=self.a,account=self.admin,role='HOMEROOM_TEACHER',valid_from=timezone.localdate())
        TeacherAssignment.objects.create(tenant=self.a,teacher=self.admin,classroom=self.clazz,kind='HOMEROOM',starts_on=timezone.localdate())
        thread=Conversation.objects.create(tenant=self.a,student=self.s2,teacher=self.admin,guardian=self.parent,created_by=self.parent)
        msg=ConversationMessage.objects.create(tenant=self.a,conversation=thread,sender=self.admin,body='SECRET_MESSAGE',client_key=str(uuid4()))
        event=NotificationOutbox.objects.create(tenant=self.a,recipient=self.parent,event_type='MESSAGE_RECEIVED',subject_id=msg.id,dedupe_key='message',payload={'secret':'NEVER_EXPORT_PAYLOAD'})
        NotificationOutbox.objects.create(tenant=self.a,recipient=self.parent,event_type='UNKNOWN',subject_id=uuid4(),dedupe_key='unknown',payload={})
        NotificationOutbox.objects.create(tenant=self.b,recipient=self.parent,event_type='MESSAGE_RECEIVED',subject_id=msg.id,dedupe_key='foreign',payload={})
        self.assertEqual([x['id'] for x in self.snapshot()['notifications']['items']],[str(event.id)])
        NotificationReceipt.objects.create(tenant=self.a,recipient=self.parent,event=event)
        self.assertTrue(self.snapshot()['notifications']['items'][0]['read'])
        GuardianLink.objects.filter(student=self.s2,guardian=self.parent).update(is_active=False)
        d=self.snapshot();self.assertEqual(d['notifications']['items'],[]);self.assertNotIn('SECRET_MESSAGE',str(d));self.assertNotIn('NEVER_EXPORT',str(d))
    def test_preview_is_minimized_deterministic_and_read_only(self):
        before=AuditEvent.objects.count();first=self.cli().get(self.url(self.s1)+'ai-preview/').json();second=self.cli().get(self.url(self.s1)+'ai-preview/').json()
        self.assertEqual(first['sentences'],second['sentences']);self.assertFalse(first['model_called']);self.assertFalse(first['exported_to_provider'])
        self.assertTrue(first['human_review_required']);self.assertNotIn('Test',str(first));self.assertNotIn('Synthetic One',str(first))
        self.assertEqual(AuditEvent.objects.count(),before)
        for path in ['/api/v1/dashboard/children/',self.url(self.s1),self.url(self.s1)+'ai-preview/']:
            self.assertEqual(self.cli().post(path,{},format='json').status_code,405)
    def test_no_store_headers_throttle_and_invalid_ids(self):
        r=self.cli().get(self.url(self.s1));self.assertEqual(r['Cache-Control'],'private, no-store');self.assertIn('X-Tenant-ID',r['Vary'])
        self.assertEqual(self.cli(False).get(self.url(self.s1)).status_code,401)
        self.assertEqual(self.cli().get('/api/v1/dashboard/students/not-uuid/').status_code,404)
        cache.clear()
        with patch.object(DashboardThrottle,'rate','1/min'):
            self.assertEqual(self.cli().get('/api/v1/dashboard/children/').status_code,200)
            self.assertEqual(self.cli().get('/api/v1/dashboard/children/').status_code,429)
    def test_query_count_does_not_grow_per_homework_row(self):
        with CaptureQueriesContext(connection) as baseline:self.snapshot()
        for _ in range(20):self.task()
        with CaptureQueriesContext(connection) as expanded:self.snapshot()
        self.assertLessEqual(len(expanded),len(baseline)+1)
        self.assertLess(len(expanded),55)
