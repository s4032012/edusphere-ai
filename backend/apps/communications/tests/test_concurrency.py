from unittest import skipUnless
from django.db import connection
from django.test import TransactionTestCase
from django.core.cache import cache
from apps.homework.tests import test_concurrency as homework_concurrency
from . import test_api
from . import test_security
from apps.communications.models import Conversation,ConversationMessage,AnnouncementRecipient,AnnouncementRead,SupportTicket
from apps.attendance.models import NotificationOutbox
from uuid import uuid4

@skipUnless(connection.vendor=='postgresql','Requires PostgreSQL row locks')
class CommunicationConcurrencyTests(TransactionTestCase):
    cli=test_api.CommunicationAPITests.cli
    create_thread=test_api.CommunicationAPITests.create_thread
    race=homework_concurrency.HomeworkConcurrencyTests.race
    notice=test_security.CommunicationSecurityTests.notice
    ticket=test_security.CommunicationSecurityTests.ticket
    transition=test_security.CommunicationSecurityTests.transition
    def setUp(self):
        cache.clear();test_api.CommunicationAPITests.setUpTestData.__func__(type(self))
    def test_concurrent_thread_creation_is_idempotent(self):
        job=(self.parent,'post','/api/v1/comms/conversations/',{'student_id':str(self.student.id),'teacher_id':str(self.teacher.id),'guardian_id':str(self.parent.id)})
        self.assertEqual(self.race([job,job]),[200,201]);self.assertEqual(Conversation.objects.count(),1)
    def test_concurrent_send_is_idempotent(self):
        tid=self.create_thread().json()['id'];job=(self.parent,'post',f'/api/v1/comms/conversations/{tid}/messages/',{'body':'retry','client_key':str(uuid4())})
        self.assertEqual(self.race([job,job]),[200,201]);self.assertEqual(ConversationMessage.objects.count(),1)
        self.assertEqual(NotificationOutbox.objects.filter(event_type='MESSAGE_RECEIVED').count(),1)
    def test_concurrent_publication_and_receipt(self):
        nid=self.notice(publish=False);job=(self.admin,'post',f'/api/v1/comms/announcements/{nid}/publish/',{})
        self.assertEqual(self.race([job,job]),[200,400]);self.assertEqual(NotificationOutbox.objects.count(),AnnouncementRecipient.objects.count())
        job=(self.parent,'post',f'/api/v1/comms/announcements/{nid}/read/',{})
        self.assertEqual(self.race([job,job]),[200,200]);self.assertEqual(AnnouncementRead.objects.count(),1)
    def test_conflicting_ticket_transitions(self):
        t=self.ticket();jobs=[(self.support,'post',f'/api/v1/comms/tickets/{t["id"]}/transition/',{'state':s,'expected_version':1}) for s in ['IN_PROGRESS','RESOLVED']]
        self.assertEqual(self.race(jobs),[200,409]);self.assertEqual(SupportTicket.objects.get().version,2)
    def test_reply_against_close_cannot_write_after_closed(self):
        t=self.ticket();self.transition(t['id'],'RESOLVED',1)
        jobs=[(self.support,'post',f'/api/v1/comms/tickets/{t["id"]}/transition/',{'state':'CLOSED','expected_version':2}),
              (self.parent,'post',f'/api/v1/comms/tickets/{t["id"]}/reply/',{'body':'New info'})]
        self.assertIn(self.race(jobs),[[200,400],[201,409]])
        ticket=SupportTicket.objects.get()
        if ticket.state=='CLOSED':self.assertFalse(ticket.replies.exists())
        else:self.assertTrue(ticket.replies.exists())
