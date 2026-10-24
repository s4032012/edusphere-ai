from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from . import test_api
from apps.academics.models import AcademicYear,Classroom,Subject,TeacherAssignment,GuardianLink,Enrollment,StudentAccount
from apps.schools.models import Membership,AuditEvent
from apps.grades.models import GradeEntry
from apps.attendance.models import NotificationOutbox
from apps.homework.models import HomeworkAssignment,HomeworkSubmission

class HomeworkSecurityTests(TestCase):
    setUpTestData=classmethod(test_api.HomeworkIntegrationTests.setUpTestData.__func__)
    c=test_api.HomeworkIntegrationTests.c
    task=test_api.HomeworkIntegrationTests.task

    def published(self):
        r=self.task();self.assertEqual(r.status_code,201,r.content);tid=r.json()['id']
        self.assertEqual(self.c().post(f'/api/v1/homework/{tid}/publish/',{},format='json').status_code,200)
        return tid

    def submit(self,tid=None):
        tid=tid or self.published()
        r=self.c(self.pupil).put(f'/api/v1/homework/{tid}/my-submission/',{'action':'submit','content_text':'secret answer','expected_version':0},format='json')
        self.assertEqual(r.status_code,200,r.content)
        return HomeworkSubmission.objects.get(id=r.json()['id'])

    def return_work(self,sub,**extra):
        return self.c().post(f'/api/v1/homework/submissions/{sub.id}/return/',{'feedback':'Good','expected_version':sub.version,**extra},format='json')

    def test_draft_patch_validation_and_publish_freezes_content(self):
        tid=self.task().json()['id'];url=f'/api/v1/homework/{tid}/'
        for data in [{'title':None},{'instructions':{}},{'due_at':'2026-99-99T25:70:00Z'},{'due_at':'2030-01-01T10:00:00'},{'allow_late':'false'},{'classroom_id':str(self.clazz.id)},[]]:
            self.assertEqual(self.c().patch(url,data,format='json').status_code,400,data)
        self.assertEqual(self.c().patch(url,{'title':'Edited','allow_late':True},format='json').status_code,200)
        self.c().post(url+'publish/',{},format='json')
        self.assertEqual(self.c().patch(url,{'title':'Changed'},format='json').status_code,400)
        self.assertEqual(HomeworkAssignment.objects.get(id=tid).title,'Edited')

    def test_invalid_create_types_never_500(self):
        good={'classroom_id':str(self.clazz.id),'subject_id':str(self.subject.id),'title':'Title','instructions':'Do work','due_at':(timezone.now()+timedelta(days=1)).isoformat()}
        for key,value in [('classroom_id','bad'),('subject_id',None),('title',{}),('instructions',True),('due_at',[]),('due_at','2030-02-31T10:00:00Z'),('allow_late',1)]:
            self.assertEqual(self.c().post('/api/v1/homework/',{**good,key:value},format='json').status_code,400)
        self.assertFalse(HomeworkAssignment.objects.exists())

    def test_revoke_membership_and_assignment_with_existing_token(self):
        tid=self.published();client=self.c()
        TeacherAssignment.objects.filter(teacher=self.teacher).update(is_active=False)
        self.assertEqual(client.get('/api/v1/homework/').json(),[])
        self.assertEqual(client.get(f'/api/v1/homework/{tid}/').status_code,404)
        self.assertEqual(client.post(f'/api/v1/homework/{tid}/close/',{},format='json').status_code,403)
        Membership.objects.filter(account=self.teacher).update(is_active=False)
        self.assertEqual(client.get('/api/v1/homework/').status_code,404)

    def test_expired_year_and_future_assignments_deny(self):
        tid=self.published()
        TeacherAssignment.objects.filter(teacher=self.teacher).update(starts_on=timezone.localdate()+timedelta(days=1))
        self.assertEqual(self.c().get('/api/v1/homework/').json(),[])
        AcademicYear.objects.filter(id=self.clazz.year_id).update(ends_on=timezone.localdate()-timedelta(days=1))
        self.assertEqual(self.c(self.pupil).get('/api/v1/homework/').json(),[])
        self.assertEqual(self.c(self.pupil).get(f'/api/v1/homework/{tid}/my-submission/').status_code,404)

    def test_parent_and_homeroom_never_read_answer_text(self):
        sub=self.submit()
        for user in [self.parent,self.homeroom]:
            data=self.c(user).get(f'/api/v1/homework/students/{self.stu.id}/').json()
            self.assertIsNone(data['items'][0]['submission']['content_text'])
        data=self.c(self.homeroom).get(f'/api/v1/homework/{sub.assignment_id}/roster/').json()
        self.assertIsNone(data['students'][0]['submission']['content_text'])
        self.assertFalse(data['assignment']['can_manage'])
        self.assertEqual(self.c(self.parent).get(f'/api/v1/homework/{sub.assignment_id}/roster/').status_code,404)

    def test_mixed_parent_teacher_role_does_not_expose_other_subject_work(self):
        sub=self.submit()
        Membership.objects.create(tenant=self.a,account=self.parent,role='SUBJECT_TEACHER',valid_from=timezone.localdate())
        other=Subject.objects.create(tenant=self.a,code='HISTORY',name='History')
        TeacherAssignment.objects.create(tenant=self.a,teacher=self.parent,classroom=self.clazz,subject=other,kind='SUBJECT',starts_on=timezone.localdate())
        data=self.c(self.parent).get(f'/api/v1/homework/students/{self.stu.id}/').json()
        self.assertIsNone(data['items'][0]['submission']['content_text'])
        GuardianLink.objects.filter(guardian=self.parent).update(valid_to=timezone.localdate()-timedelta(days=1))
        self.assertEqual(self.c(self.parent).get(f'/api/v1/homework/students/{self.stu.id}/').status_code,404)

    def test_same_subject_colleague_can_read_but_not_return_or_edit(self):
        sub=self.submit()
        TeacherAssignment.objects.create(tenant=self.a,teacher=self.outsider,classroom=self.clazz,subject=self.subject,kind='SUBJECT',starts_on=timezone.localdate())
        data=self.c(self.outsider).get(f'/api/v1/homework/{sub.assignment_id}/roster/').json()
        self.assertEqual(data['students'][0]['submission']['content_text'],'secret answer')
        self.assertFalse(data['assignment']['can_manage'])
        self.assertEqual(self.c(self.outsider).post(f'/api/v1/homework/submissions/{sub.id}/return/',{'feedback':'x','expected_version':1},format='json').status_code,403)
        tid=self.task().json()['id']
        self.assertEqual(self.c(self.outsider).get(f'/api/v1/homework/{tid}/roster/').status_code,404)

    def test_ended_enrollment_removes_access_without_deleting_work(self):
        sub=self.submit();Enrollment.objects.filter(student=self.stu).update(ends_on=timezone.localdate()-timedelta(days=1))
        for user in [self.parent,self.pupil]:
            self.assertEqual(self.c(user).get('/api/v1/homework/').json(),[])
            self.assertEqual(self.c(user).get(f'/api/v1/homework/{sub.assignment_id}/').status_code,404)
        self.assertEqual(self.c(self.pupil).put(f'/api/v1/homework/{sub.assignment_id}/my-submission/',{'content_text':'x','expected_version':1},format='json').status_code,404)
        self.assertEqual(self.return_work(sub).status_code,404)
        self.assertEqual(HomeworkSubmission.objects.get(id=sub.id).content_text,'secret answer')

    def test_draft_empty_save_resubmit_and_no_downgrade(self):
        tid=self.published();url=f'/api/v1/homework/{tid}/my-submission/'
        r=self.c(self.pupil).put(url,{'content_text':'','action':'save','expected_version':0},format='json');self.assertEqual(r.status_code,200)
        r=self.c(self.pupil).put(url,{'content_text':'one','action':'submit','expected_version':1},format='json');self.assertEqual(r.json()['version'],2)
        r=self.c(self.pupil).put(url,{'content_text':'two','action':'submit','expected_version':2},format='json');self.assertEqual(r.json()['version'],3)
        self.assertEqual(self.c(self.pupil).put(url,{'content_text':'','action':'save','expected_version':3},format='json').status_code,400)
        self.assertEqual(HomeworkSubmission.objects.get(assignment_id=tid).content_text,'two')

    def test_versions_are_strict_and_student_id_cannot_redirect(self):
        tid=self.published();url=f'/api/v1/homework/{tid}/my-submission/'
        for version in [True,1.5,'1',None,-1,{}]:
            self.assertEqual(self.c(self.pupil).put(url,{'content_text':'x','expected_version':version},format='json').status_code,400)
        self.assertEqual(self.c(self.pupil).put(url,{'content_text':'x','student_id':str(self.stu2.id)},format='json').status_code,400)
        self.assertFalse(HomeworkSubmission.objects.exists())

    def test_deadline_late_and_closed(self):
        tid=self.published();HomeworkAssignment.objects.filter(id=tid).update(due_at=timezone.now()-timedelta(seconds=1))
        url=f'/api/v1/homework/{tid}/my-submission/'
        payload={'content_text':'late','expected_version':0}
        self.assertEqual(self.c(self.pupil).put(url,payload,format='json').status_code,400)
        HomeworkAssignment.objects.filter(id=tid).update(allow_late=True)
        self.assertEqual(self.c(self.pupil).put(url,payload,format='json').status_code,200)
        self.c().post(f'/api/v1/homework/{tid}/close/',{},format='json')
        self.assertEqual(self.c(self.pupil).put(url,{**payload,'expected_version':1},format='json').status_code,400)
        sub=HomeworkSubmission.objects.get(assignment_id=tid)
        self.assertEqual(self.return_work(sub).status_code,200)

    def test_stale_return_cannot_grade_new_content(self):
        sub=self.submit()
        self.c(self.pupil).put(f'/api/v1/homework/{sub.assignment_id}/my-submission/',{'content_text':'updated','expected_version':1},format='json')
        self.assertEqual(self.return_work(sub).status_code,409)
        sub.refresh_from_db();self.assertEqual(sub.state,'SUBMITTED');self.assertEqual(sub.feedback,'')
        self.assertEqual(self.return_work(sub).status_code,200)

    def test_feedback_precision_and_official_grade_unchanged(self):
        sub=self.submit();before=GradeEntry.objects.count()
        for score in ['NaN','Infinity',True,{},'7.55','-1','10.1']:
            self.assertEqual(self.return_work(sub,score=score).status_code,400)
        self.assertEqual(self.return_work(sub,score='0').status_code,200)
        self.assertEqual(GradeEntry.objects.count(),before)
        self.assertEqual(NotificationOutbox.objects.filter(event_type='HOMEWORK_RETURNED').count(),2)
        for event in NotificationOutbox.objects.all():self.assertEqual(set(event.payload),{'assignment_id','student_id'})

    def test_notifications_hide_after_guardian_revoke_or_student_transfer(self):
        sub=self.submit();self.return_work(sub)
        self.assertEqual(len(self.c(self.parent).get('/api/v1/notifications/').json()),1)
        self.assertEqual(len(self.c(self.pupil).get('/api/v1/notifications/').json()),1)
        GuardianLink.objects.filter(guardian=self.parent).update(can_view_academic=False)
        self.assertEqual(self.c(self.parent).get('/api/v1/notifications/').json(),[])
        Enrollment.objects.filter(student=self.stu).update(is_active=False)
        self.assertEqual(self.c(self.pupil).get('/api/v1/notifications/').json(),[])

    def test_audit_failure_rolls_back_return_and_outbox(self):
        sub=self.submit()
        with patch('apps.access.views.TenantAPIView.audit',side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):self.return_work(sub)
        sub.refresh_from_db();self.assertEqual(sub.state,'SUBMITTED');self.assertFalse(NotificationOutbox.objects.exists())

    def test_cross_tenant_all_mutations(self):
        sub=self.submit();client=self.c(self.other,self.b)
        for method,url,data in [('patch',f'/api/v1/homework/{sub.assignment_id}/',{'title':'x'}),('post',f'/api/v1/homework/{sub.assignment_id}/publish/',{}),('post',f'/api/v1/homework/{sub.assignment_id}/close/',{}),('put',f'/api/v1/homework/{sub.assignment_id}/my-submission/',{'content_text':'x'}),('post',f'/api/v1/homework/submissions/{sub.id}/return/',{'feedback':'x','expected_version':1})]:
            self.assertEqual(getattr(client,method)(url,data,format='json').status_code,404)

    def test_admin_is_read_only(self):
        sub=self.submit();data=self.c(self.admin).get(f'/api/v1/homework/{sub.assignment_id}/roster/').json()
        self.assertFalse(data['assignment']['can_manage'])
        self.assertEqual(self.c(self.admin).post(f'/api/v1/homework/{sub.assignment_id}/close/',{},format='json').status_code,403)
        self.assertEqual(self.c(self.admin).post(f'/api/v1/homework/submissions/{sub.id}/return/',{'feedback':'x','expected_version':1},format='json').status_code,403)
