from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from apps.communications.tests import test_api
from apps.communications.models import Announcement,AnnouncementRecipient,AnnouncementRead,ConversationRead,ConversationMessage,SupportTicket,TicketReply
from apps.attendance.models import NotificationOutbox
from apps.academics.models import GuardianLink,TeacherAssignment,Enrollment,AcademicYear
from apps.schools.models import Membership
from apps.communications.views import CommunicationThrottle

class CommunicationSecurityTests(TestCase):
    setUpTestData=classmethod(test_api.CommunicationAPITests.setUpTestData.__func__)
    cli=test_api.CommunicationAPITests.cli
    create_thread=test_api.CommunicationAPITests.create_thread
    def setUp(self):cache.clear()
    def notice(self,scope='CLASS',publish=True):
        data={'scope':scope,'title':'Private title','body':'Private body'}
        if scope=='CLASS':data['classroom_id']=str(self.clazz.id)
        if scope=='GRADE':data['grade_level']=8
        r=self.cli(self.admin).post('/api/v1/comms/announcements/',data,format='json');self.assertEqual(r.status_code,201,r.content)
        if publish:self.assertEqual(self.cli(self.admin).post(f'/api/v1/comms/announcements/{r.json()["id"]}/publish/',{},format='json').status_code,200)
        return r.json()['id']
    def message(self,thread=None):
        thread=thread or self.create_thread().json()['id']
        r=self.cli().post(f'/api/v1/comms/conversations/{thread}/messages/',{'body':'Private message','client_key':str(uuid4())},format='json')
        self.assertEqual(r.status_code,201,r.content);return thread,r.json()['id']
    def ticket(self):
        r=self.cli().post('/api/v1/comms/tickets/',{'category':'OTHER','subject':'Help','details':'Private details','student_id':str(self.student.id)},format='json')
        self.assertEqual(r.status_code,201,r.content);return r.json()
    def transition(self,ticket,state,version):
        return self.cli(self.support).post(f'/api/v1/comms/tickets/{ticket}/transition/',{'state':state,'expected_version':version},format='json')

    def test_school_and_grade_exclude_unverified_and_unassigned(self):
        for scope in ['SCHOOL','GRADE']:
            self.notice(scope)
        self.assertEqual(self.cli(self.unverified).get('/api/v1/comms/announcements/').json(),[])
        self.assertEqual(self.cli(self.other_teacher).get('/api/v1/comms/announcements/').json(),[])
        self.assertEqual(len(self.cli(self.parent).get('/api/v1/comms/announcements/').json()),2)
        self.assertEqual(len(self.cli(self.pupil).get('/api/v1/comms/announcements/').json()),2)
    def test_recipient_snapshot_excludes_later_verified_guardian(self):
        nid=self.notice();GuardianLink.objects.filter(guardian=self.unverified).update(is_verified=True)
        self.assertEqual(self.cli(self.unverified).get('/api/v1/comms/announcements/').json(),[])
        self.assertEqual(self.cli(self.unverified).post(f'/api/v1/comms/announcements/{nid}/read/',{},format='json').status_code,404)
    def test_revoked_link_hides_notice_and_outbox_even_if_read(self):
        nid=self.notice();events=self.cli().get('/api/v1/comms/notifications/').json();self.assertEqual(len(events),1)
        self.cli().post(f'/api/v1/comms/announcements/{nid}/read/',{},format='json')
        GuardianLink.objects.filter(guardian=self.parent).update(can_view_academic=False)
        self.assertEqual(self.cli().get('/api/v1/comms/announcements/').json(),[])
        self.assertEqual(self.cli().get('/api/v1/comms/notifications/').json(),[])
        self.assertEqual(self.cli().post(f'/api/v1/comms/notifications/{events[0]["id"]}/read/',{},format='json').status_code,404)
        self.assertNotIn('Private title',str(NotificationOutbox.objects.values_list('payload',flat=True)))
    def test_role_kind_mismatch_and_ended_year_remove_teacher(self):
        thread,_=self.message()
        Membership.objects.filter(account=self.teacher).update(role='HOMEROOM_TEACHER')
        self.assertEqual(self.cli(self.teacher).get(f'/api/v1/comms/conversations/{thread}/messages/').status_code,404)
        self.assertEqual(self.cli().get(f'/api/v1/comms/students/{self.student.id}/contacts/').json()['teachers'][0]['id'],str(self.homeroom.id))
        AcademicYear.objects.filter(tenant=self.a).update(ends_on=timezone.localdate()-timedelta(days=1))
        self.assertEqual(self.cli().get(f'/api/v1/comms/students/{self.student.id}/contacts/').json()['teachers'],[])
    def test_revoked_teacher_draft_not_visible_or_publishable(self):
        r=self.cli(self.homeroom).post('/api/v1/comms/announcements/',{'scope':'CLASS','classroom_id':str(self.clazz.id),'title':'x','body':'y'},format='json')
        TeacherAssignment.objects.filter(teacher=self.homeroom).update(is_active=False)
        self.assertEqual(self.cli(self.homeroom).get('/api/v1/comms/announcements/').json(),[])
        self.assertEqual(self.cli(self.homeroom).post(f'/api/v1/comms/announcements/{r.json()["id"]}/publish/',{},format='json').status_code,403)
    def test_staff_and_student_cannot_read_private_thread(self):
        thread,_=self.message()
        for u in [self.admin,self.support,self.pupil,self.other_teacher,self.foreign]:
            client=self.cli(u,self.b if u==self.foreign else self.a)
            self.assertEqual(client.get(f'/api/v1/comms/conversations/{thread}/messages/').status_code,404)
            self.assertEqual(client.post(f'/api/v1/comms/conversations/{thread}/read/',{'last_message_id':None},format='json').status_code,404)
    def test_teacher_revocation_hides_inbox_and_message_access(self):
        thread,_=self.message();TeacherAssignment.objects.filter(teacher=self.teacher).update(is_active=False)
        self.assertEqual(self.cli(self.teacher).get('/api/v1/comms/notifications/').json(),[])
        self.assertEqual(self.cli().get('/api/v1/comms/conversations/').json(),[])
        self.assertEqual(self.cli().post(f'/api/v1/comms/conversations/{thread}/messages/',{'body':'x','client_key':str(uuid4())},format='json').status_code,404)
    def test_key_canonicalization_and_unknown_fields(self):
        thread=self.create_thread().json()['id'];url=f'/api/v1/comms/conversations/{thread}/messages/';key=uuid4()
        for value,expected in [(str(key),201),(key.hex.upper(),200)]:
            self.assertEqual(self.cli().post(url,{'body':'x','client_key':value},format='json').status_code,expected)
        self.assertEqual(ConversationMessage.objects.count(),1)
        self.assertEqual(self.cli().post(url,{'body':'x','client_key':str(key),'sender_id':str(self.teacher.id)},format='json').status_code,400)
    def test_invalid_payloads_return_400_not_500(self):
        for data in [[],{'student_id':'bad'},{'student_id':{},'teacher_id':'bad','guardian_id':None}]:
            self.assertEqual(self.cli().post('/api/v1/comms/conversations/',data,format='json').status_code,400)
        for data in [{'scope':'CLASS','classroom_id':'bad','title':'x','body':'y'},{'scope':'GRADE','grade_level':True,'title':'x','body':'y'},{'scope':'SCHOOL','title':'x','body':'a\x00b'}]:
            self.assertEqual(self.cli(self.admin).post('/api/v1/comms/announcements/',data,format='json').status_code,400)
    def test_observed_read_watermark_preserves_new_arrival(self):
        thread,first=self.message();_,second=self.message(thread);url=f'/api/v1/comms/conversations/{thread}/read/'
        self.assertEqual(self.cli(self.teacher).post(url,{'last_message_id':first},format='json').status_code,200)
        self.assertEqual(self.cli(self.teacher).get('/api/v1/comms/conversations/').json()[0]['unread_count'],1)
        self.cli(self.teacher).post(url,{'last_message_id':second},format='json');self.cli(self.teacher).post(url,{'last_message_id':first},format='json')
        self.assertEqual(self.cli(self.teacher).get('/api/v1/comms/conversations/').json()[0]['unread_count'],0)
        self.assertEqual(self.cli(self.teacher).post(url,{},format='json').status_code,400)
        self.assertEqual(self.cli(self.teacher).post(url,{'last_message_id':str(uuid4())},format='json').status_code,404)
    def test_ticket_revocation_and_private_scope(self):
        t=self.ticket();url=f'/api/v1/comms/tickets/{t["id"]}/'
        for u in [self.teacher,self.pupil,self.unverified]:self.assertEqual(self.cli(u).get(url).status_code,404)
        GuardianLink.objects.filter(guardian=self.parent).update(is_verified=False)
        self.assertEqual(self.cli().get(url).status_code,404);self.assertEqual(self.cli().get('/api/v1/comms/tickets/').json(),[])
        self.assertEqual(self.cli(self.support).get(url).status_code,200)
    def test_first_staff_response_claims_ticket_and_stale_transition_conflicts(self):
        t=self.ticket();r=self.cli(self.support).post(f'/api/v1/comms/tickets/{t["id"]}/reply/',{'body':'Investigating'},format='json')
        self.assertEqual(r.json()['state'],'IN_PROGRESS');self.assertEqual(r.json()['assignee_id'],str(self.support.id))
        self.assertEqual(self.transition(t['id'],'RESOLVED',1).status_code,409)
        self.assertEqual(self.transition(t['id'],'RESOLVED',2).status_code,200)
    def test_repeat_resolution_keeps_distinct_events_and_closed_rejects_reply(self):
        t=self.ticket()
        for version,state in enumerate(['RESOLVED','IN_PROGRESS','RESOLVED','CLOSED'],start=1):
            self.assertEqual(self.transition(t['id'],state,version).status_code,200)
        self.assertEqual(NotificationOutbox.objects.filter(event_type='TICKET_STATUS',payload__state='RESOLVED').count(),2)
        self.assertEqual(self.cli().post(f'/api/v1/comms/tickets/{t["id"]}/reply/',{'body':'late'},format='json').status_code,400)
        self.assertEqual(TicketReply.objects.count(),0)
    def test_publish_limit_and_audit_failure_rollback(self):
        nid=self.notice(publish=False);url=f'/api/v1/comms/announcements/{nid}/publish/'
        with patch('apps.communications.views.announcement_recipients',return_value=set(range(2501))):
            self.assertEqual(self.cli(self.admin).post(url,{},format='json').status_code,400)
        with patch('apps.communications.views.AnnouncementPublish.audit',side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):self.cli(self.admin).post(url,{},format='json')
        self.assertEqual(Announcement.objects.get().state,'DRAFT');self.assertEqual(AnnouncementRecipient.objects.count(),0);self.assertEqual(NotificationOutbox.objects.count(),0)
    def test_publication_and_read_idempotency(self):
        nid=self.notice();url=f'/api/v1/comms/announcements/{nid}/'
        count=NotificationOutbox.objects.count()
        self.assertEqual(self.cli(self.admin).post(url+'publish/',{},format='json').status_code,400)
        for _ in range(2):self.assertEqual(self.cli().post(url+'read/',{},format='json').status_code,200)
        self.assertEqual(AnnouncementRead.objects.count(),1);self.assertEqual(NotificationOutbox.objects.count(),count)
    def test_unknown_events_hidden_and_scoped_throttle(self):
        NotificationOutbox.objects.create(tenant=self.a,recipient=self.parent,event_type='UNKNOWN',subject_id=uuid4(),dedupe_key='unknown',payload={'secret':'hidden'})
        self.assertEqual(self.cli().get('/api/v1/comms/notifications/').json(),[])
        cache.clear()
        with patch.object(CommunicationThrottle,'rate','1/min'):
            self.assertEqual(self.cli().get('/api/v1/comms/notifications/').status_code,200)
            self.assertEqual(self.cli().get('/api/v1/comms/notifications/').status_code,429)
        self.assertEqual(self.cli().get('/api/v1/students/').status_code,200)
    def test_transfer_removes_old_class_notices_and_threads(self):
        from apps.academics.models import Classroom
        nid=self.notice();thread,_=self.message()
        other=Classroom.objects.create(tenant=self.a,year=self.clazz.year,code='8A2',grade_level=8)
        Enrollment.objects.filter(student=self.student).update(classroom=other)
        self.assertEqual(self.cli().get('/api/v1/comms/announcements/').json(),[])
        self.assertEqual(self.cli().get('/api/v1/comms/conversations/').json(),[])
        self.assertEqual(self.cli().get(f'/api/v1/comms/conversations/{thread}/messages/').status_code,404)
        self.assertEqual(self.cli().post(f'/api/v1/comms/announcements/{nid}/read/',{},format='json').status_code,404)
    def test_expired_teacher_and_reassigned_guardian_cannot_reuse_thread(self):
        thread,_=self.message();url=f'/api/v1/comms/conversations/{thread}/messages/'
        TeacherAssignment.objects.filter(teacher=self.teacher).update(ends_on=timezone.localdate()-timedelta(days=1))
        self.assertEqual(self.cli().get(url).status_code,404)
        TeacherAssignment.objects.filter(teacher=self.teacher).update(ends_on=None)
        GuardianLink.objects.filter(guardian=self.parent).update(guardian=self.unverified)
        self.assertEqual(self.cli(self.unverified).get(url).status_code,404)
        self.assertEqual(self.cli().get(url).status_code,404)
    def test_all_mutations_audited_without_private_text(self):
        from apps.schools.models import AuditEvent
        self.notice();self.message();t=self.ticket()
        self.cli(self.support).post(f'/api/v1/comms/tickets/{t["id"]}/reply/',{'body':'Private reply'},format='json')
        self.transition(t['id'],'RESOLVED',2)
        actions=set(AuditEvent.objects.filter(tenant=self.a).values_list('action',flat=True))
        self.assertTrue({'NOTICE_DRAFT_CREATED','NOTICE_PUBLISHED','CONVERSATION_CREATED','MESSAGE_SENT','TICKET_CREATED','TICKET_REPLIED','TICKET_RESOLVED'}<=actions)
        self.assertNotIn('Private',str(list(AuditEvent.objects.values())))
