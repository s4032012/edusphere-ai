"""API-level journeys across Sprint 0–6, isolated by Django's test database.
These exercise real views/authorization/transactions, not native-device UI.
"""
from datetime import timedelta
from uuid import uuid4

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.academics.models import GuardianLink, TeacherAssignment, Student, Enrollment
from apps.communications.models import ConversationMessage, NotificationReceipt
from apps.grades.models import GradeEntry
from apps.homework.models import HomeworkSubmission
from apps.identity.models import Account
from apps.schools.models import Membership
from . import test_security_journeys as fixtures


class IntegrationJourneys(TestCase):
    setUpTestData = classmethod(fixtures.TenantAndRoleRegressionTests.setUpTestData.__func__)
    client_as = fixtures.TenantAndRoleRegressionTests.client_as

    def setUp(self):
        cache.clear()
        self.parent = self.client_as(self.parent_a)
        self.pupil = self.client_as(self.student_actor)
        self.teacher = self.client_as(self.teacher_a)
        self.admin = self.client_as(self.admin_a)
        self.foreign = self.client_as(self.admin_b, self.b)
        # Same teacher is homeroom + subject teacher in this synthetic class.
        Membership.objects.create(tenant=self.a, account=self.teacher_a,
                                  role='HOMEROOM_TEACHER', valid_from=timezone.localdate())
        TeacherAssignment.objects.create(tenant=self.a, teacher=self.teacher_a, classroom=self.clazz,
                                         kind='HOMEROOM', starts_on=timezone.localdate())
        self.dashboard = f'/api/v1/dashboard/students/{self.child.id}/'

    def request(self, client, method, path, data=None, status=200):
        response = getattr(client, method)(path, data or {}, format='json')
        self.assertEqual(response.status_code, status, response.content)
        return response.json()

    def snapshot(self, client=None):
        return self.request(client or self.parent, 'get', self.dashboard)

    def test_j01_school_setup_and_verified_guardian(self):
        today = timezone.localdate()
        year = self.request(self.admin, 'post', '/api/v1/academic-years/', {
            'label':'Journey year', 'starts_on':str(today), 'ends_on':str(today+timedelta(days=180))}, 201)
        classroom = self.request(self.admin, 'post', '/api/v1/classrooms/', {
            'year':year['id'], 'code':'9A1', 'grade_level':9}, 201)
        subject = self.request(self.admin, 'post', '/api/v1/subjects/', {'code':'SCI','name':'Science'}, 201)
        staff = self.request(self.admin, 'post', '/api/v1/staff/', {
            'username':'journey_teacher','display_name':'Synthetic Teacher','role':'SUBJECT_TEACHER'}, 201)
        self.assertFalse(Account.objects.get(pk=staff['id']).has_usable_password())
        self.request(self.admin, 'post', '/api/v1/teacher-assignments/', {
            'teacher_id':staff['id'],'classroom_id':classroom['id'],'subject_id':subject['id'],'kind':'SUBJECT'}, 201)
        self.request(self.admin, 'post', '/api/v1/teacher-assignments/', {
            'teacher_id':str(self.teacher_a.id),'classroom_id':classroom['id'],'kind':'HOMEROOM'}, 201)
        child = self.request(self.admin, 'post', '/api/v1/students/', {
            'student_code':'J01','full_name':'Synthetic Journey Child'}, 201)
        self.request(self.admin, 'post', '/api/v1/enrollments/', {
            'student_id':child['id'],'classroom_id':classroom['id']}, 201)
        guardian = self.request(self.admin, 'post', '/api/v1/guardian-accounts/', {
            'username':'journey_guardian','display_name':'Synthetic Guardian'}, 201)
        link = self.request(self.admin, 'post', '/api/v1/guardian-links/', {
            'student_id':child['id'],'guardian_id':guardian['id'],'relation':'MOTHER'}, 201)
        viewer = self.client_as(Account.objects.get(pk=guardian['id']))
        url = f'/api/v1/dashboard/students/{child["id"]}/'
        self.assertEqual(viewer.get(url).status_code, 404)
        self.request(self.admin, 'post', f'/api/v1/guardian-links/{link["id"]}/verify/', {'evidence_checked':True})
        self.assertEqual(self.request(viewer, 'get', url)['student']['id'], child['id'])
        self.assertEqual(self.foreign.get(url).status_code, 403)

    def attendance_draft(self):
        payload = {'classroom_id':str(self.clazz.id),'attendance_date':str(timezone.localdate())}
        session = self.request(self.teacher, 'post', '/api/v1/attendance/sessions/', payload, 201)
        again = self.request(self.teacher, 'post', '/api/v1/attendance/sessions/', payload)
        self.assertEqual(session['id'], again['id'])
        url = f'/api/v1/attendance/sessions/{session["id"]}/'
        self.request(self.teacher, 'put', url+'records/', {'records':[
            {'student_id':str(self.child.id),'mark':'ABSENT'},
            {'student_id':str(self.other.id),'mark':'PRESENT'}]})
        return url

    def test_j02_attendance_published_into_dashboard(self):
        url = self.attendance_draft()
        self.assertEqual(self.snapshot()['attendance']['recorded_days'], 0)
        self.request(self.teacher, 'post', url+'submit/')
        self.assertEqual(self.snapshot()['attendance']['ABSENT'], 1)
        self.assertEqual(self.snapshot(self.pupil)['attendance']['recorded_days'], 1)
        self.assertEqual(self.foreign.get(url).status_code, 404)
        self.assertEqual(self.teacher.post(url+'submit/').status_code, 400)

    def test_j03_leave_decision_and_inbox(self):
        url = self.attendance_draft()
        self.request(self.teacher, 'post', url+'submit/')
        data = {'student_id':str(self.child.id),'from_date':str(timezone.localdate()),
                'through_date':str(timezone.localdate()),'reason':'Synthetic sensitive reason'}
        leave = self.request(self.parent, 'post', '/api/v1/leave-requests/', data, 201)
        self.request(self.teacher, 'post', f'/api/v1/leave-requests/{leave["id"]}/decision/', {'action':'approve'})
        history = self.request(self.parent, 'get', f'/api/v1/attendance/students/{self.child.id}/')
        self.assertEqual(history[0]['effective_status'], 'EXCUSED_ABSENCE')
        inbox = self.request(self.parent, 'get', '/api/v1/comms/notifications/')
        self.assertIn('LEAVE_DECIDED', [item['type'] for item in inbox])
        self.assertNotIn('Synthetic sensitive reason', str(self.snapshot()))

    def test_j04_grade_publication_and_zero_score(self):
        book = self.request(self.admin, 'post', '/api/v1/gradebooks/', {
            'classroom_id':str(self.clazz.id),'subject_id':str(self.subject.id),
            'semester':'1','mode':'SCORE','regular_required':2}, 201)
        assessment = self.request(self.teacher, 'post', f'/api/v1/gradebooks/{book["id"]}/assessments/', {
            'kind':'TX','slot':1,'title':'Journey assessment'}, 201)
        url = f'/api/v1/assessments/{assessment["id"]}/'
        self.request(self.teacher, 'put', url+'entries/', {'entries':[
            {'student_id':str(self.child.id),'score':'0.0'},
            {'student_id':str(self.other.id),'score':'9.0'}]})
        self.assertEqual(self.snapshot()['grades']['items'], [])
        self.request(self.teacher, 'post', url+'lock/')
        self.assertEqual(self.snapshot(self.pupil)['grades']['items'], [])
        self.assertEqual(self.teacher.post(url+'publish/').status_code, 403)
        self.request(self.admin, 'post', url+'publish/')
        for client in (self.parent, self.pupil):
            self.assertEqual(self.snapshot(client)['grades']['items'][0]['score'], '0.0')
        self.assertEqual(self.foreign.get(self.dashboard).status_code, 403)

    def test_j05_homework_submission_return_and_dashboard(self):
        task = self.request(self.teacher, 'post', '/api/v1/homework/', {
            'classroom_id':str(self.clazz.id),'subject_id':str(self.subject.id),
            'title':'Journey homework','instructions':'Synthetic question',
            'due_at':(timezone.now()+timedelta(days=1)).isoformat()}, 201)
        url = f'/api/v1/homework/{task["id"]}/'
        self.assertEqual(self.snapshot()['homework']['summary']['total'], 0)
        self.request(self.teacher, 'post', url+'publish/')
        self.assertEqual(self.snapshot()['homework']['summary']['total'], 1)
        self.request(self.pupil, 'put', url+'my-submission/', {'content_text':'PRIVATE ANSWER','action':'submit'})
        sub = HomeworkSubmission.objects.get(assignment_id=task['id'])
        self.assertEqual(self.pupil.put(url+'my-submission/', {
            'content_text':'Retry','action':'submit','expected_version':0}, format='json').status_code, 409)
        self.assertEqual(HomeworkSubmission.objects.count(), 1)
        self.request(self.teacher, 'post', f'/api/v1/homework/submissions/{sub.id}/return/', {
            'feedback':'Good','score':'9.0','expected_version':1})
        self.assertEqual(self.snapshot()['homework']['summary']['submitted_or_returned'], 1)
        self.assertNotIn('PRIVATE ANSWER', str(self.snapshot()))
        self.assertEqual(GradeEntry.objects.count(), 0)

    def thread(self):
        return self.request(self.parent, 'post', '/api/v1/comms/conversations/', {
            'student_id':str(self.child.id),'teacher_id':str(self.teacher_a.id),
            'guardian_id':str(self.parent_a.id)}, 201)

    def test_j06_messages_retry_and_assignment_revocation(self):
        thread = self.thread()
        url = f'/api/v1/comms/conversations/{thread["id"]}/messages/'
        payload = {'body':'Private synthetic message','client_key':str(uuid4())}
        self.request(self.parent, 'post', url, payload, 201)
        self.request(self.parent, 'post', url, payload)
        self.assertEqual(ConversationMessage.objects.count(), 1)
        self.assertEqual(len(self.request(self.teacher, 'get', url)['messages']), 1)
        TeacherAssignment.objects.filter(teacher=self.teacher_a).update(is_active=False)
        self.assertEqual(self.teacher.get(url).status_code, 404)
        self.assertEqual(self.parent.get(url).status_code, 404)
        self.assertNotIn('Private synthetic message', str(self.snapshot()))

    def test_j07_announcement_publication_and_read_receipts(self):
        url = '/api/v1/comms/announcements/'
        notice = self.request(self.admin, 'post', url, {'scope':'CLASS','classroom_id':str(self.clazz.id),
            'title':'Journey notice','body':'Synthetic notice body'}, 201)
        self.assertEqual(self.snapshot()['announcements'], [])
        self.request(self.admin, 'post', url+notice['id']+'/publish/')
        self.assertEqual(self.snapshot()['announcements'][0]['title'], 'Journey notice')
        self.assertEqual(self.request(self.foreign, 'get', url), [])
        self.assertEqual(NotificationReceipt.objects.count(), 0)
        self.request(self.parent, 'post', url+notice['id']+'/read/')
        self.assertTrue(self.snapshot()['announcements'][0]['read'])

    def test_j08_support_can_resolve_ticket_but_not_read_private_messages(self):
        thread = self.thread()
        support = Account.objects.create_user(username='journey_support')
        Membership.objects.create(tenant=self.a, account=support, role='SUPPORT_STAFF', valid_from=timezone.localdate())
        client = self.client_as(support)
        url = '/api/v1/comms/tickets/'
        ticket = self.request(self.parent, 'post', url, {'category':'ACCOUNT','subject':'Synthetic help',
            'details':'Synthetic details','student_id':str(self.child.id)}, 201)
        detail = url+ticket['id']+'/'
        self.request(client, 'post', detail+'reply/', {'body':'Synthetic reply'}, 201)
        self.request(client, 'post', detail+'transition/', {'state':'RESOLVED','expected_version':2})
        self.assertEqual(self.request(self.parent, 'get', detail)['state'], 'RESOLVED')
        self.assertEqual(client.get(f'/api/v1/comms/conversations/{thread["id"]}/messages/').status_code, 404)
        self.assertEqual(self.foreign.get(detail).status_code, 404)

    def test_j09_preview_is_deterministic_and_read_only(self):
        before = NotificationReceipt.objects.count()
        one = self.request(self.parent, 'get', self.dashboard+'ai-preview/')
        two = self.request(self.parent, 'get', self.dashboard+'ai-preview/')
        self.assertFalse(one['model_called'])
        self.assertFalse(one['exported_to_provider'])
        self.assertEqual(one['sentences'], two['sentences'])
        self.assertEqual(NotificationReceipt.objects.count(), before)

    def test_j10_revocation_and_expired_token_across_modules(self):
        paths = [self.dashboard, self.dashboard+'ai-preview/', f'/api/v1/students/{self.child.id}/',
            f'/api/v1/students/{self.child.id}/grades/', f'/api/v1/attendance/students/{self.child.id}/',
            f'/api/v1/homework/students/{self.child.id}/', f'/api/v1/comms/students/{self.child.id}/contacts/']
        for path in paths:
            self.assertEqual(self.parent.get(path).status_code, 200, path)
        GuardianLink.objects.filter(guardian=self.parent_a).update(is_active=False)
        for path in paths:
            self.assertEqual(self.parent.get(path).status_code, 404, path)
        token = RefreshToken.for_user(self.student_actor).access_token
        token.set_exp(lifetime=timedelta(seconds=-1))
        self.pupil.credentials(HTTP_AUTHORIZATION='Bearer '+str(token), HTTP_X_TENANT_ID=str(self.a.id))
        self.assertEqual(self.pupil.get(self.dashboard).status_code, 401)

    def test_large_class_45_roster_and_single_child_dashboard(self):
        for index in range(43):
            child = Student.objects.create(tenant=self.a, student_code=f'L{index}', full_name=f'Synthetic {index}')
            Enrollment.objects.create(tenant=self.a, student=child, classroom=self.clazz, starts_on=timezone.localdate())
        self.assertEqual(len(self.request(self.teacher, 'get', '/api/v1/students/')), 45)
        children = self.request(self.parent, 'get', '/api/v1/dashboard/children/')['students']
        self.assertEqual([row['id'] for row in children], [str(self.child.id)])
        self.assertEqual(self.snapshot()['student']['id'], str(self.child.id))
