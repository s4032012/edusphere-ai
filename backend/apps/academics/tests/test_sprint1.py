"""Sprint 1 tenant isolation and business invariant coverage; Django TestCase integration."""
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.identity.models import Account
from apps.schools.models import Tenant, Membership, AuditEvent
from apps.academics.models import AcademicYear, Classroom, Student, Subject, Enrollment, TeacherAssignment


class SchoolAdminSprint1Tests(TestCase):
    def setUp(self):
        today = timezone.localdate()
        self.today = today
        self.a = Tenant.objects.create(code='sprint1-a', name='School A')
        self.b = Tenant.objects.create(code='sprint1-b', name='School B')
        self.admin = Account.objects.create_user('admin_s1', password='testing123456')
        self.parent = Account.objects.create_user('parent_s1', password='testing123456')
        self.teacher = Account.objects.create_user('teacher_s1', password='testing123456')
        self.other = Account.objects.create_user('other_s1', password='testing123456')
        for acc, tenant, role in [(self.admin,self.a,'SCHOOL_ADMIN'),(self.parent,self.a,'PARENT'),
                                  (self.teacher,self.a,'SUBJECT_TEACHER'),(self.other,self.b,'SCHOOL_ADMIN')]:
            Membership.objects.create(tenant=tenant, account=acc, role=role, valid_from=today-timedelta(days=5))
        self.year = AcademicYear.objects.create(tenant=self.a, label='2026–2027',
                      starts_on=today-timedelta(days=30), ends_on=today+timedelta(days=300))
        self.year_b = AcademicYear.objects.create(tenant=self.b, label='2026–2027',
                      starts_on=today-timedelta(days=30), ends_on=today+timedelta(days=300))
        self.clazz = Classroom.objects.create(tenant=self.a, year=self.year, code='8A1', grade_level=8)
        self.subject = Subject.objects.create(tenant=self.a, code='MATH', name='Math')
        self.student = Student.objects.create(tenant=self.a, student_code='A01', full_name='Pilot Student')

    def client_for(self, user=None, tenant=None):
        user = user or self.admin
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}',
                           HTTP_X_TENANT_ID=str((tenant or self.a).id))
        return client

    def test_school_admin_can_create_year_and_audit(self):
        response = self.client_for().post('/api/v1/academic-years/',
                         {'label':'2027–2028','starts_on':'2027-08-01','ends_on':'2028-05-31'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(AuditEvent.objects.filter(tenant=self.a,action='ACADEMIC_YEAR_CREATED').exists())

    def test_dates_invalid(self):
        response = self.client_for().post('/api/v1/academic-years/',
                        {'label':'Bad', 'starts_on':'2027-08-01','ends_on':'2027-06-01'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_parent_cannot_create_subject(self):
        response = self.client_for(self.parent).post('/api/v1/subjects/', {'code':'PHY','name':'Physics'}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_other_tenant_admin_gets_not_found(self):
        self.assertEqual(self.client_for(self.other,self.a).get('/api/v1/admin/dashboard/').status_code,404)

    def test_duplicate_student_code_rejected(self):
        response = self.client_for().post('/api/v1/students/', {'student_code':'A01','full_name':'Duplicate'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_archiving_requires_end_enrollment(self):
        enrollment = Enrollment.objects.create(tenant=self.a, student=self.student,
                                                 classroom=self.clazz,starts_on=self.today)
        response = self.client_for().post(f'/api/v1/students/{self.student.id}/archive/',{}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client_for().post(f'/api/v1/enrollments/{enrollment.id}/end/',{},format='json').status_code,200)
        self.assertEqual(self.client_for().post(f'/api/v1/students/{self.student.id}/archive/',{},format='json').status_code,200)

    def test_invalid_cross_tenant_student_update(self):
        student_b = Student.objects.create(tenant=self.b,student_code='B1',full_name='B School')
        response = self.client_for().patch(f'/api/v1/students/{student_b.id}/edit/',{'full_name':'No'},format='json')
        self.assertEqual(response.status_code,404)

    def test_invalid_cross_tenant_class_year(self):
        response = self.client_for().patch(f'/api/v1/classrooms/{self.clazz.id}/',{'year':str(self.year_b.id)},format='json')
        self.assertEqual(response.status_code,400)

    def test_staff_created_without_active_password(self):
        response = self.client_for().post('/api/v1/staff/',
                                     {'username':'teacher_new_s1','display_name':'New Teacher',
                                      'role':'SUBJECT_TEACHER'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertFalse(Account.objects.get(username='teacher_new_s1').has_usable_password())
        self.assertEqual(response.json()['invitation_status'],'NOT_SENT')

    def test_staff_account_created_forbidden_for_parent(self):
        response = self.client_for(self.parent).post('/api/v1/staff/',
                                     {'username':'nope','display_name':'No','role':'SUBJECT_TEACHER'},format='json')
        self.assertEqual(response.status_code,403)

    def test_teacher_requires_assignment(self):
        self.assertEqual(self.client_for(self.teacher).get('/api/v1/students/').json(), [])
        TeacherAssignment.objects.create(tenant=self.a,teacher=self.teacher, classroom=self.clazz,
                                         subject=self.subject,kind='SUBJECT',starts_on=self.today)
        Enrollment.objects.create(tenant=self.a,student=self.student,classroom=self.clazz,starts_on=self.today)
        self.assertEqual(len(self.client_for(self.teacher).get('/api/v1/students/').json()),1)

    def test_teacher_assignment_ends_immediately(self):
        assignment = TeacherAssignment.objects.create(tenant=self.a,teacher=self.teacher,classroom=self.clazz,
                           subject=self.subject,kind='SUBJECT',starts_on=self.today)
        response = self.client_for().post(f'/api/v1/teacher-assignments/{assignment.id}/end/',{},format='json')
        self.assertEqual(response.status_code, 200)
        assignment.refresh_from_db()
        self.assertFalse(assignment.is_active)

    def test_staff_not_allowed_to_view_audit(self):
        self.assertEqual(self.client_for(self.teacher).get('/api/v1/audit-events/').status_code,403)

    def test_administration_lists_reject_other_roles(self):
        for user in [self.teacher, self.parent]:
            for path in ['admin/dashboard', 'enrollments/list', 'teacher-assignments/list',
                         'guardian-accounts', 'guardian-links/list', 'audit-events']:
                with self.subTest(user=user.username, path=path):
                    self.assertEqual(self.client_for(user).get(f'/api/v1/{path}/').status_code, 403)

    def test_all_sprint1_lists_reject_other_tenant_membership(self):
        for path in ['admin/dashboard','academic-years','subjects','staff','enrollments/list',
                     'teacher-assignments/list','guardian-accounts','guardian-links/list','audit-events']:
            with self.subTest(path=path):
                self.assertEqual(self.client_for(self.admin,self.b).get(f'/api/v1/{path}/').status_code,404)

    def test_all_admin_writes_reject_teacher_and_parent(self):
        paths = ['academic-years','subjects','staff','guardian-accounts','students','classrooms',
                 'enrollments','teacher-assignments','guardian-links',
                 f'enrollments/{self.student.id}/end',f'teacher-assignments/{self.student.id}/end',
                 f'students/{self.student.id}/archive',f'guardian-links/{self.student.id}/verify']
        for user in [self.teacher,self.parent]:
            api=self.client_for(user)
            for path in paths:
                with self.subTest(user=user.username,path=path):
                    self.assertEqual(api.post(f'/api/v1/{path}/',{},format='json').status_code,403)
            for path in [f'classrooms/{self.clazz.id}',f'students/{self.student.id}/edit']:
                self.assertEqual(api.patch(f'/api/v1/{path}/',{},format='json').status_code,403)

    def test_foreign_objects_cannot_be_changed_or_ended(self):
        classroom=Classroom.objects.create(tenant=self.b,year=self.year_b,code='B',grade_level=8)
        student=Student.objects.create(tenant=self.b,student_code='B',full_name='Other school')
        enrollment=Enrollment.objects.create(tenant=self.b,student=student,classroom=classroom,starts_on=self.today)
        assignment=TeacherAssignment.objects.create(tenant=self.b,teacher=self.other,classroom=classroom,kind='HOMEROOM',starts_on=self.today)
        api=self.client_for()
        for path in [f'students/{student.id}/archive',f'enrollments/{enrollment.id}/end',f'teacher-assignments/{assignment.id}/end']:
            self.assertEqual(api.post(f'/api/v1/{path}/',{},format='json').status_code,404)
        self.assertEqual(api.patch(f'/api/v1/classrooms/{classroom.id}/',{'code':'No'},format='json').status_code,404)
        self.assertEqual(AuditEvent.objects.count(),0)

    def test_enrollment_rejects_duplicates_and_inactive_students(self):
        api=self.client_for();payload={'student_id':str(self.student.id),'classroom_id':str(self.clazz.id)}
        self.assertEqual(api.post('/api/v1/enrollments/',payload,format='json').status_code,201)
        self.assertEqual(api.post('/api/v1/enrollments/',payload,format='json').status_code,400)
        self.student.is_active=False;self.student.save()
        self.assertEqual(api.post('/api/v1/enrollments/',payload,format='json').status_code,404)
        self.assertEqual(Enrollment.objects.count(),1)

    def test_homeroom_assignment_rejects_duplicate_and_wrong_role(self):
        api=self.client_for();payload={'teacher_id':str(self.teacher.id),'classroom_id':str(self.clazz.id),'kind':'HOMEROOM'}
        self.assertEqual(api.post('/api/v1/teacher-assignments/',payload,format='json').status_code,400)
        Membership.objects.create(tenant=self.a,account=self.teacher,role='HOMEROOM_TEACHER',valid_from=self.today)
        response=api.post('/api/v1/teacher-assignments/',payload,format='json')
        self.assertEqual(response.status_code,201)
        self.assertEqual(api.post('/api/v1/teacher-assignments/',payload,format='json').status_code,400)
        self.assertEqual(TeacherAssignment.objects.count(),1)
        self.assertEqual(TeacherAssignment.objects.get().ends_on,self.year.ends_on)

    def test_year_dates_restrict_relationships_and_teacher_access(self):
        self.year.starts_on=self.today-timedelta(days=100);self.year.ends_on=self.today-timedelta(days=1);self.year.save()
        api=self.client_for()
        self.assertEqual(api.post('/api/v1/enrollments/',{'student_id':str(self.student.id),'classroom_id':str(self.clazz.id)},format='json').status_code,400)
        self.assertEqual(api.post('/api/v1/teacher-assignments/',{'teacher_id':str(self.teacher.id),'classroom_id':str(self.clazz.id),'kind':'SUBJECT','subject_id':str(self.subject.id)},format='json').status_code,400)
        Enrollment.objects.create(tenant=self.a,student=self.student,classroom=self.clazz,starts_on=self.year.starts_on)
        TeacherAssignment.objects.create(tenant=self.a,teacher=self.teacher,classroom=self.clazz,kind='SUBJECT',subject=self.subject,starts_on=self.year.starts_on)
        self.assertEqual(self.client_for(self.teacher).get('/api/v1/students/').json(),[])

    def test_end_assignment_revokes_existing_teacher_token(self):
        Enrollment.objects.create(tenant=self.a,student=self.student,classroom=self.clazz,starts_on=self.today)
        assignment=TeacherAssignment.objects.create(tenant=self.a,teacher=self.teacher,classroom=self.clazz,kind='SUBJECT',subject=self.subject,starts_on=self.today)
        api=self.client_for(self.teacher)
        self.assertEqual(len(api.get('/api/v1/students/').json()),1)
        admin=self.client_for();url=f'/api/v1/teacher-assignments/{assignment.id}/end/'
        self.assertEqual(admin.post(url,{},format='json').status_code,200)
        self.assertEqual(api.get('/api/v1/students/').json(),[])
        self.assertEqual(admin.post(url,{},format='json').status_code,400)

    def test_class_with_history_cannot_change_year(self):
        enrollment=Enrollment.objects.create(tenant=self.a,student=self.student,classroom=self.clazz,starts_on=self.today,is_active=False)
        other=AcademicYear.objects.create(tenant=self.a,label='Next',starts_on=self.today,ends_on=self.today+timedelta(days=365))
        response=self.client_for().patch(f'/api/v1/classrooms/{self.clazz.id}/',{'year':str(other.id)},format='json')
        self.assertEqual(response.status_code,400)
        enrollment.refresh_from_db();self.assertEqual(enrollment.classroom.year_id,self.year.id)

    def test_guardian_account_validation_and_unusable_password(self):
        api=self.client_for()
        for payload in [{}, {'username':'   ','display_name':'Name'}, {'username':'x','display_name':{}}, {'username':'x'*151,'display_name':'Name'}]:
            self.assertEqual(api.post('/api/v1/guardian-accounts/',payload,format='json').status_code,400)
        response=api.post('/api/v1/guardian-accounts/',{'username':'new_parent','display_name':'Parent'},format='json')
        self.assertEqual(response.status_code,201)
        self.assertFalse(Account.objects.get(username='new_parent').has_usable_password())
        self.assertTrue(Membership.objects.filter(account__username='new_parent',tenant=self.a,role='PARENT').exists())

    def test_guardian_link_verification_and_duplicate_guard(self):
        api=self.client_for();parent=self.client_for(self.parent)
        data={'student_id':str(self.student.id),'guardian_id':str(self.parent.id),'relation':'MOTHER','is_verified':True}
        response=api.post('/api/v1/guardian-links/',data,format='json')
        self.assertEqual(response.status_code,201)
        self.assertEqual(parent.get('/api/v1/students/').json(),[])
        self.assertEqual(api.post('/api/v1/guardian-links/',data,format='json').status_code,400)
        url=f"/api/v1/guardian-links/{response.json()['id']}/verify/"
        self.assertEqual(api.post(url,{'evidence_checked':True},format='json').status_code,200)
        self.assertEqual(len(parent.get('/api/v1/students/').json()),1)

    def test_audit_scope_and_transaction_rollback(self):
        from unittest.mock import patch
        AuditEvent.objects.create(tenant=self.b,actor=self.other,action='OTHER',target_type='Student',target_id=self.student.id)
        api=self.client_for()
        self.assertEqual(api.get('/api/v1/audit-events/').json(),[])
        with patch('apps.access.views.TenantAPIView.audit',side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                api.post('/api/v1/subjects/',{'code':'ROLLBACK','name':'Rollback'},format='json')
        self.assertFalse(Subject.objects.filter(code='ROLLBACK').exists())

    def test_dashboard_ignores_expired_memberships(self):
        membership=Membership.objects.get(account=self.teacher)
        membership.valid_to=self.today-timedelta(days=1);membership.save()
        self.assertEqual(self.client_for().get('/api/v1/admin/dashboard/').json()['staff_memberships'],0)
