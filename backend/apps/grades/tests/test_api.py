"""Django integration tests (run after installing dependencies and creating database)."""
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.identity.models import Account
from apps.schools.models import Tenant, Membership, AuditEvent
from apps.academics.models import AcademicYear, Classroom, Subject, Student, Enrollment, TeacherAssignment, GuardianLink, StudentAccount
from apps.grades.models import GradeBook, Assessment, GradeEntry, GradeRevision
from apps.attendance.models import NotificationOutbox


class Sprint3IntegrationTests(TestCase):
    def setUp(self):
        today=timezone.localdate()
        self.a=Tenant.objects.create(code='gr-a',name='Demo A')
        self.b=Tenant.objects.create(code='gr-b',name='Demo B')
        self.admin=Account.objects.create_user('gr_admin',password='test-password')
        self.teacher=Account.objects.create_user('gr_teacher',password='test-password')
        self.teacher_other=Account.objects.create_user('gr_teacher_other',password='test-password')
        self.homeroom=Account.objects.create_user('gr_homeroom',password='test-password')
        self.parent=Account.objects.create_user('gr_parent',password='test-password')
        self.unverified=Account.objects.create_user('gr_unverified',password='test-password')
        self.child=Account.objects.create_user('gr_student',password='test-password')
        self.other_admin=Account.objects.create_user('gr_other_admin',password='test-password')
        for account,school,role in [(self.admin,self.a,'SCHOOL_ADMIN'),(self.teacher,self.a,'SUBJECT_TEACHER'),
            (self.teacher_other,self.a,'SUBJECT_TEACHER'),(self.homeroom,self.a,'HOMEROOM_TEACHER'),
            (self.parent,self.a,'PARENT'),(self.unverified,self.a,'PARENT'),(self.child,self.a,'STUDENT'),
            (self.other_admin,self.b,'SCHOOL_ADMIN')]:
            Membership.objects.create(tenant=school,account=account,role=role,valid_from=today-timedelta(days=30))
        year=AcademicYear.objects.create(tenant=self.a,label='2026-2027',starts_on=today-timedelta(days=80),ends_on=today+timedelta(days=220))
        self.cls=Classroom.objects.create(tenant=self.a,year=year,code='8A1',grade_level=8)
        self.subj=Subject.objects.create(tenant=self.a,code='MATH',name='Toán')
        self.st1=Student.objects.create(tenant=self.a,student_code='A1',full_name='Học sinh 1')
        self.st2=Student.objects.create(tenant=self.a,student_code='A2',full_name='Học sinh 2')
        for stu in (self.st1,self.st2):
            Enrollment.objects.create(tenant=self.a,student=stu,classroom=self.cls,starts_on=today-timedelta(days=50))
        TeacherAssignment.objects.create(tenant=self.a,teacher=self.teacher,classroom=self.cls,subject=self.subj,
            kind='SUBJECT',starts_on=today-timedelta(days=50))
        TeacherAssignment.objects.create(tenant=self.a,teacher=self.homeroom,classroom=self.cls,kind='HOMEROOM',starts_on=today-timedelta(days=50))
        GuardianLink.objects.create(tenant=self.a,student=self.st1,guardian=self.parent,relation='MOTHER',
            is_verified=True,valid_from=today-timedelta(days=50))
        GuardianLink.objects.create(tenant=self.a,student=self.st2,guardian=self.unverified,relation='MOTHER',
            is_verified=False,valid_from=today-timedelta(days=50))
        StudentAccount.objects.create(tenant=self.a,student=self.st1,account=self.child)

    def c(self,actor=None,school=None):
        c=APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(actor or self.admin).access_token}',
                      HTTP_X_TENANT_ID=str((school or self.a).id))
        return c

    def book(self,mode='SCORE',required=2):
        r=self.c().post('/api/v1/gradebooks/',{'classroom_id':str(self.cls.id),'subject_id':str(self.subj.id),
                        'semester':'1','mode':mode,'regular_required':required},format='json')
        self.assertEqual(r.status_code,201,r.content)
        return r.json()['id']

    def assessment(self,book,kind='TX',slot=1):
        response=self.c(self.teacher).post(f'/api/v1/gradebooks/{book}/assessments/',
             {'kind':kind,'slot':slot,'title':'Đánh giá kiểm tra'},format='json')
        self.assertEqual(response.status_code,201,response.content)
        return response.json()['id']

    def fill(self,assessment,values=None,actor=None):
        values=values or ['8.0','9.0']
        return self.c(actor or self.teacher).put(f'/api/v1/assessments/{assessment}/entries/',
              {'entries':[{'student_id':str(stu.id),'score':value} for stu,value in zip((self.st1,self.st2),values)]},format='json')

    def test_teacher_can_write_but_parent_cannot_and_invalid_score_rejected(self):
        b=self.book();a=self.assessment(b)
        self.assertEqual(self.c(self.parent).put(f'/api/v1/assessments/{a}/entries/',{
            'entries':[{'student_id':str(self.st1.id),'score':'9.0'}]},format='json').status_code,403)
        self.assertEqual(self.c(self.teacher_other).put(f'/api/v1/assessments/{a}/entries/',{
            'entries':[{'student_id':str(self.st1.id),'score':'9.0'}]},format='json').status_code,403)
        self.assertEqual(self.fill(a,['11.0','9.0']).status_code,400)
        self.assertEqual(self.fill(a).status_code,200)
        self.assertEqual(GradeEntry.objects.filter(assessment_id=a).count(),2)

    def test_no_partial_lock_no_unapproved_publish(self):
        b=self.book();a=self.assessment(b)
        self.assertEqual(self.c().post(f'/api/v1/assessments/{a}/publish/',{},format='json').status_code,400)
        self.c(self.teacher).put(f'/api/v1/assessments/{a}/entries/',{
            'entries':[{'student_id':str(self.st1.id),'score':'9.0'}]},format='json')
        self.assertEqual(self.c(self.teacher).post(f'/api/v1/assessments/{a}/lock/',{},format='json').status_code,400)
        self.assertEqual(self.fill(a).status_code,200)
        self.assertEqual(self.c(self.teacher).post(f'/api/v1/assessments/{a}/lock/',{},format='json').status_code,200)
        self.assertEqual(self.fill(a).status_code,400)
        self.assertEqual(self.c(self.teacher).post(f'/api/v1/assessments/{a}/publish/',{},format='json').status_code,403)
        self.assertEqual(self.c().post(f'/api/v1/assessments/{a}/publish/',{},format='json').status_code,200)
        self.assertEqual(NotificationOutbox.objects.filter(event_type='GRADE_PUBLISHED').count(),1)
        self.assertTrue(AuditEvent.objects.filter(action='ASSESSMENT_PUBLISHED').exists())

    def test_parent_sees_only_published_and_only_verified_child(self):
        b=self.book();a=self.assessment(b);self.fill(a)
        path=f'/api/v1/students/{self.st1.id}/grades/'
        self.assertEqual(self.c(self.parent).get(path).json()['books'],[])
        self.assertEqual(self.c(self.unverified).get(f'/api/v1/students/{self.st2.id}/grades/').status_code,404)
        self.assertEqual(self.c(self.parent).get(f'/api/v1/students/{self.st2.id}/grades/').status_code,404)
        self.c(self.teacher).post(f'/api/v1/assessments/{a}/lock/',{},format='json')
        self.c().post(f'/api/v1/assessments/{a}/publish/',{},format='json')
        rows=self.c(self.parent).get(path).json()['books'][0]['assessments']
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['score'],'8.0')
        self.assertEqual(len(self.c(self.child).get(path).json()['books'][0]['assessments']),1)

    def test_other_tenant_cannot_query_or_change(self):
        b=self.book();a=self.assessment(b)
        self.assertEqual(self.c(self.other_admin,self.b).get(f'/api/v1/gradebooks/{b}/').status_code,404)
        self.assertEqual(self.c(self.other_admin,self.a).get('/api/v1/gradebooks/').status_code,404)
        self.assertEqual(self.c(self.other_admin,self.b).post(f'/api/v1/assessments/{a}/publish/',{},format='json').status_code,404)

    def test_revision_approval_and_versioning(self):
        b=self.book();a=self.assessment(b);self.fill(a)
        self.c(self.teacher).post(f'/api/v1/assessments/{a}/lock/',{},format='json')
        self.c().post(f'/api/v1/assessments/{a}/publish/',{},format='json')
        entry=GradeEntry.objects.get(assessment_id=a,student=self.st1)
        url=f'/api/v1/grade-entries/{entry.id}/revision-requests/'
        r=self.c(self.teacher).post(url,{'score':'7.0','reason':'Nhập nhầm điểm lúc đối chiếu'},format='json')
        self.assertEqual(r.status_code,201,r.content)
        self.assertEqual(self.c(self.teacher).post(url,{'score':'6.0','reason':'Có nhầm số học sinh'},format='json').status_code,400)
        self.assertEqual(self.c(self.teacher).post(f'/api/v1/grade-revisions/{r.json()["id"]}/decision/',{'action':'approve'},format='json').status_code,403)
        res=self.c().post(f'/api/v1/grade-revisions/{r.json()["id"]}/decision/',{'action':'approve'},format='json')
        self.assertEqual(res.status_code,200,res.content)
        entry.refresh_from_db()
        self.assertEqual(str(entry.score),'7.0');self.assertEqual(entry.version,2)
        self.assertEqual(self.c().post(f'/api/v1/grade-revisions/{r.json()["id"]}/decision/',{'action':'approve'},format='json').status_code,400)
        self.assertEqual(GradeRevision.objects.get(pk=r.json()['id']).state,'APPROVED')

    def test_comment_mode_rejects_score_and_accepts_pass(self):
        b=self.book(mode='COMMENT');a=self.assessment(b)
        r=self.c(self.teacher).put(f'/api/v1/assessments/{a}/entries/',{
          'entries':[{'student_id':str(self.st1.id),'score':'9.0'}]},format='json')
        self.assertEqual(r.status_code,400)
        r=self.c(self.teacher).put(f'/api/v1/assessments/{a}/entries/',{
          'entries':[{'student_id':str(self.st1.id),'result':'PASS'},
                     {'student_id':str(self.st2.id),'result':'FAIL'}]},format='json')
        self.assertEqual(r.status_code,200,r.content)

    def test_student_from_other_tenant_blocked(self):
        b=self.book();a=self.assessment(b)
        outside=Student.objects.create(tenant=self.b,student_code='B1',full_name='Other pupil')
        r=self.c(self.teacher).put(f'/api/v1/assessments/{a}/entries/',{
          'entries':[{'student_id':str(outside.id),'score':'9.0'}]},format='json')
        self.assertEqual(r.status_code,400)

    def published(self):
        book=self.book();assessment=self.assessment(book);self.fill(assessment)
        self.assertEqual(self.c(self.teacher).post(f'/api/v1/assessments/{assessment}/lock/',{},format='json').status_code,200)
        self.assertEqual(self.c().post(f'/api/v1/assessments/{assessment}/publish/',{},format='json').status_code,200)
        return book,assessment

    def revision(self,assessment):
        entry=GradeEntry.objects.get(assessment_id=assessment,student=self.st1)
        response=self.c(self.teacher).post(f'/api/v1/grade-entries/{entry.id}/revision-requests/',
            {'score':'7.0','reason':'Correct synthetic input error'},format='json')
        self.assertEqual(response.status_code,201)
        return entry,response.json()['id']

    def test_all_numeric_edge_cases_reject_whole_batch(self):
        assessment=self.assessment(self.book())
        for invalid in ['NaN','Infinity','-Infinity','7.55',True,{},None,'-0.1','10.1']:
            with self.subTest(value=invalid):
                self.assertEqual(self.fill(assessment,['8.0',invalid]).status_code,400)
                self.assertFalse(GradeEntry.objects.exists())
        row={'student_id':str(self.st1.id),'score':'8.0'}
        self.assertEqual(self.c(self.teacher).put(f'/api/v1/assessments/{assessment}/entries/',{'entries':[row,row]},format='json').status_code,400)

    def test_homeroom_only_sees_published_and_cannot_mutate(self):
        book=self.book();assessment=self.assessment(book);self.fill(assessment)
        api=self.c(self.homeroom);url=f'/api/v1/gradebooks/{book}/'
        self.assertEqual(api.get(url).json()['assessments'],[])
        self.assertFalse(api.get(url).json()['can_edit'])
        self.assertEqual(self.fill(assessment,actor=self.homeroom).status_code,403)
        self.c().post(f'/api/v1/assessments/{assessment}/lock/',{},format='json')
        self.assertEqual(api.get(url).json()['assessments'],[])
        self.c().post(f'/api/v1/assessments/{assessment}/publish/',{},format='json')
        self.assertEqual(len(api.get(url).json()['assessments']),1)

    def test_revoked_assignment_blocks_existing_teacher_token(self):
        book,assessment=self.published();entry=GradeEntry.objects.get(assessment_id=assessment,student=self.st1)
        api=self.c(self.teacher)
        TeacherAssignment.objects.filter(teacher=self.teacher).update(is_active=False)
        self.assertEqual(api.get('/api/v1/gradebooks/').json(),[])
        self.assertEqual(api.get(f'/api/v1/gradebooks/{book}/').status_code,403)
        self.assertEqual(api.get('/api/v1/grade-revisions/').json(),[])
        self.assertEqual(api.post(f'/api/v1/grade-entries/{entry.id}/revision-requests/',{'score':'7.0','reason':'Synthetic correction request'},format='json').status_code,403)

    def test_revoked_guardian_hides_scores_and_outbox(self):
        self.published();api=self.c(self.parent)
        self.assertEqual(len(api.get('/api/v1/notifications/').json()),1)
        GuardianLink.objects.filter(guardian=self.parent).update(can_view_academic=False)
        self.assertEqual(api.get(f'/api/v1/students/{self.st1.id}/grades/').status_code,404)
        self.assertEqual(api.get('/api/v1/notifications/').json(),[])

    def test_expired_parent_role_does_not_expand_subject_teacher_access(self):
        book,assessment=self.published()
        other=Subject.objects.create(tenant=self.a,code='PHYS',name='Physics')
        other_book=GradeBook.objects.create(tenant=self.a,classroom=self.cls,subject=other,semester='1',mode='SCORE',regular_required=2)
        other_assessment=Assessment.objects.create(tenant=self.a,book=other_book,kind='TX',slot=1,title='Physics grade',state='PUBLISHED',created_by=self.admin)
        GradeEntry.objects.create(tenant=self.a,assessment=other_assessment,student=self.st1,score='9',updated_by=self.admin)
        today=timezone.localdate()
        Membership.objects.create(tenant=self.a,account=self.teacher,role='PARENT',valid_from=today-timedelta(days=10))
        GuardianLink.objects.create(tenant=self.a,student=self.st1,guardian=self.teacher,relation='FATHER',is_verified=True,valid_from=today-timedelta(days=10),valid_to=today-timedelta(days=1))
        data=self.c(self.teacher).get(f'/api/v1/students/{self.st1.id}/grades/').json()
        self.assertEqual([row['id'] for row in data['books']],[book])

    def test_stale_revision_cannot_approve_but_can_be_rejected(self):
        _,assessment=self.published();entry,rid=self.revision(assessment)
        GradeEntry.objects.filter(pk=entry.id).update(version=entry.version+1)
        url=f'/api/v1/grade-revisions/{rid}/decision/'
        self.assertEqual(self.c().post(url,{'action':'approve'},format='json').status_code,400)
        self.assertEqual(self.c().post(url,{'action':'reject','decision_note':'Stale request'},format='json').status_code,200)
        entry.refresh_from_db();self.assertEqual(str(entry.score),'8.0')
        self.assertFalse(NotificationOutbox.objects.filter(event_type='GRADE_CORRECTED').exists())

    def test_revision_correction_notifies_without_score_or_reason(self):
        _,assessment=self.published();entry,rid=self.revision(assessment)
        response=self.c().post(f'/api/v1/grade-revisions/{rid}/decision/',{'action':'approve'},format='json')
        self.assertEqual(response.status_code,200)
        notice=NotificationOutbox.objects.get(event_type='GRADE_CORRECTED')
        self.assertEqual(set(notice.payload),{'revision_id','assessment_id'})
        notices=self.c(self.parent).get('/api/v1/notifications/').json()
        self.assertEqual({x['type'] for x in notices},{'GRADE_PUBLISHED','GRADE_CORRECTED'})
        self.assertEqual(self.c(self.parent).get(f'/api/v1/students/{self.st1.id}/grades/').json()['books'][0]['assessments'][0]['score'],'7.0')

    def test_locked_entries_survive_enrollment_closure(self):
        book,assessment=self.published()
        Enrollment.objects.filter(student=self.st1).update(is_active=False)
        rows=self.c().get(f'/api/v1/gradebooks/{book}/').json()['assessments'][0]['entries']
        self.assertEqual({x['student_id'] for x in rows},{str(self.st1.id),str(self.st2.id)})
        self.assertEqual(len(self.c(self.parent).get(f'/api/v1/students/{self.st1.id}/grades/').json()['books']),1)

    def test_publication_audit_failure_rolls_back_outbox_and_state(self):
        from unittest.mock import patch
        assessment=self.assessment(self.book());self.fill(assessment)
        self.c().post(f'/api/v1/assessments/{assessment}/lock/',{},format='json')
        with patch('apps.access.views.TenantAPIView.audit',side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.c().post(f'/api/v1/assessments/{assessment}/publish/',{},format='json')
        self.assertEqual(Assessment.objects.get(pk=assessment).state,'LOCKED')
        self.assertFalse(NotificationOutbox.objects.exists())

    def test_student_average_requires_all_published_columns(self):
        book=self.book();path=f'/api/v1/students/{self.st1.id}/grades/'
        for kind,slot,score in [('TX',1,'7.0'),('TX',2,'8.0'),('GK',1,'8.0'),('CK',1,'9.0')]:
            assessment=self.assessment(book,kind,slot);self.fill(assessment,[score,'9.0'])
            self.c().post(f'/api/v1/assessments/{assessment}/lock/',{},format='json')
            before=self.c(self.child).get(path).json()['books']
            if before:self.assertIsNone(before[0]['semester_average'])
            self.c().post(f'/api/v1/assessments/{assessment}/publish/',{},format='json')
        self.assertEqual(self.c(self.child).get(path).json()['books'][0]['semester_average'],'8.3')
        self.assertEqual(self.c(self.child).get(f'/api/v1/students/{self.st2.id}/grades/').status_code,404)

    def test_configuration_slot_and_exempt_permission_rules(self):
        book=self.book(mode='COMMENT');assessment=self.assessment(book)
        for kind,slot in [('TX',3),('GK',2),('CK',2)]:
            self.assertEqual(self.c(self.teacher).post(f'/api/v1/gradebooks/{book}/assessments/',{'kind':kind,'slot':slot,'title':'Invalid column'},format='json').status_code,400)
        payload={'entries':[{'student_id':str(self.st1.id),'result':'EXEMPT'}]}
        self.assertEqual(self.c(self.teacher).put(f'/api/v1/assessments/{assessment}/entries/',payload,format='json').status_code,403)
        self.assertEqual(self.c().put(f'/api/v1/assessments/{assessment}/entries/',payload,format='json').status_code,200)

    def test_foreign_objects_cannot_be_modified_or_reviewed(self):
        book,assessment=self.published();entry,rid=self.revision(assessment);api=self.c(self.other_admin,self.b)
        for path,payload in [(f'gradebooks/{book}/assessments',{'kind':'TX','slot':2,'title':'Foreign'}),
            (f'assessments/{assessment}/lock',{}),(f'assessments/{assessment}/publish',{}),
            (f'grade-entries/{entry.id}/revision-requests',{'score':'7.0','reason':'Foreign request'}),
            (f'grade-revisions/{rid}/decision',{'action':'approve'})]:
            self.assertEqual(api.post(f'/api/v1/{path}/',payload,format='json').status_code,404)
        self.assertEqual(api.put(f'/api/v1/assessments/{assessment}/entries/',{'entries':[]},format='json').status_code,404)
        self.assertEqual(api.get('/api/v1/grade-revisions/').json(),[])
