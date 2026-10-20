"""Sprint 1 school administration APIs.

Every entry-point inherits TenantAPIView, enforces membership, and explicitly
scopes DB objects to tenant.  Write operations are SCHOOL_ADMIN-only for the
pilot. Teacher and guardian grants require separately validated relationships.
"""
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from apps.identity.models import Account
from apps.schools.models import Membership, AuditEvent
from apps.academics.models import (AcademicYear, Subject, Classroom, Student,
                                  Enrollment, TeacherAssignment, GuardianLink)
from .views import TenantAPIView, StudentSerializer, ClassroomSerializer


class YearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = ('id', 'label', 'starts_on', 'ends_on')
        read_only_fields = ('id',)

    def validate(self, attrs):
        if attrs['starts_on'] >= attrs['ends_on']:
            raise serializers.ValidationError('Ngày bắt đầu phải trước ngày kết thúc.')
        return attrs


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ('id', 'code', 'name')
        read_only_fields = ('id',)


class StaffSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    username = serializers.CharField(max_length=150)
    display_name = serializers.CharField(max_length=200)
    email = serializers.EmailField(required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=[('HOMEROOM_TEACHER','Giáo viên chủ nhiệm'),
                                             ('SUBJECT_TEACHER','Giáo viên bộ môn'),
                                             ('ACADEMIC_AFFAIRS','Giáo vụ'),
                                             ('DEPARTMENT_HEAD','Tổ trưởng chuyên môn')])


class YearView(TenantAPIView):
    def get(self, request):
        if not self.roles.intersection({'SCHOOL_ADMIN','PRINCIPAL','VICE_PRINCIPAL','ACADEMIC_AFFAIRS',
                                         'HOMEROOM_TEACHER','SUBJECT_TEACHER','DEPARTMENT_HEAD'}):
            return Response([], status=200)
        data = AcademicYear.objects.filter(tenant=self.tenant).order_by('-starts_on')[:100]
        return Response(YearSerializer(data, many=True).data)

    @transaction.atomic
    def post(self, request):
        self.require_school_admin()
        data = YearSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        if AcademicYear.objects.filter(tenant=self.tenant, label=data.validated_data['label']).exists():
            raise ValidationError({'label':'Năm học đã tồn tại.'})
        item = data.save(tenant=self.tenant)
        self.audit(action='ACADEMIC_YEAR_CREATED', instance=item)
        return Response(YearSerializer(item).data, status=201)


class SubjectView(TenantAPIView):
    def get(self, request):
        if not self.roles.intersection({'SCHOOL_ADMIN','PRINCIPAL','VICE_PRINCIPAL','ACADEMIC_AFFAIRS',
                                         'HOMEROOM_TEACHER','SUBJECT_TEACHER','DEPARTMENT_HEAD'}):
            return Response([])
        return Response(SubjectSerializer(Subject.objects.filter(tenant=self.tenant).order_by('code')[:200], many=True).data)

    @transaction.atomic
    def post(self, request):
        self.require_school_admin()
        data = SubjectSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        if Subject.objects.filter(tenant=self.tenant, code=data.validated_data['code']).exists():
            raise ValidationError({'code':'Mã môn học đã tồn tại.'})
        item = data.save(tenant=self.tenant)
        self.audit(action='SUBJECT_CREATED', instance=item)
        return Response(SubjectSerializer(item).data, status=201)


class ClassroomDetailView(TenantAPIView):
    @transaction.atomic
    def patch(self, request, classroom_id):
        self.require_school_admin()
        classroom = get_object_or_404(Classroom.objects.select_for_update(), tenant=self.tenant, pk=classroom_id)
        data = ClassroomSerializer(classroom, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        year = data.validated_data.get('year', classroom.year)
        if year.tenant_id != self.tenant.id:
            raise ValidationError({'year':'Năm học không thuộc trường.'})
        if year.id != classroom.year_id and (Enrollment.objects.filter(classroom=classroom).exists() or TeacherAssignment.objects.filter(classroom=classroom).exists()):
            raise ValidationError({'year': 'Lớp đã có lịch sử học vụ; hãy tạo lớp mới cho năm học khác.'})
        grade = data.validated_data.get('grade_level', classroom.grade_level)
        if not 6 <= grade <= 9:
            raise ValidationError({'grade_level':'Pilot chỉ hỗ trợ lớp 6–9.'})
        code = data.validated_data.get('code', classroom.code)
        if Classroom.objects.filter(tenant=self.tenant, year=year, code=code).exclude(id=classroom_id).exists():
            raise ValidationError({'code':'Lớp đã tồn tại trong năm học.'})
        item = data.save()
        self.audit(action='CLASSROOM_UPDATED', instance=item)
        return Response(ClassroomSerializer(item).data)


class StudentUpdateView(TenantAPIView):
    @transaction.atomic
    def patch(self, request, student_id):
        self.require_school_admin()
        item = get_object_or_404(Student.objects.select_for_update(), tenant=self.tenant, id=student_id)
        data = StudentSerializer(item, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        code = data.validated_data.get('student_code', item.student_code)
        if Student.objects.filter(tenant=self.tenant, student_code=code).exclude(id=item.id).exists():
            raise ValidationError({'student_code':'Mã học sinh đã tồn tại.'})
        item = data.save()
        self.audit(action='STUDENT_UPDATED', instance=item)
        return Response(StudentSerializer(item).data)


class StudentArchiveView(TenantAPIView):
    @transaction.atomic
    def post(self, request, student_id):
        self.require_school_admin()
        item = get_object_or_404(Student.objects.select_for_update(), tenant=self.tenant, id=student_id)
        if not item.is_active:
            raise ValidationError({'student':'Hồ sơ đã ngừng hoạt động.'})
        if Enrollment.objects.filter(tenant=self.tenant, student=item, is_active=True).exists():
            raise ValidationError({'student':'Cần kết thúc phân lớp đang hoạt động trước khi lưu trữ.'})
        item.is_active = False
        item.save(update_fields=['is_active'])
        self.audit(action='STUDENT_ARCHIVED', instance=item)
        return Response({'id':item.id,'is_active':False})


class StaffView(TenantAPIView):
    def get(self, request):
        if not self.roles.intersection({'SCHOOL_ADMIN','PRINCIPAL','VICE_PRINCIPAL','ACADEMIC_AFFAIRS','DEPARTMENT_HEAD'}):
            return Response([])
        today = timezone.localdate()
        rows = Membership.objects.filter(tenant=self.tenant, is_active=True, account__is_active=True, valid_from__lte=today,
                role__in=['HOMEROOM_TEACHER','SUBJECT_TEACHER','ACADEMIC_AFFAIRS','DEPARTMENT_HEAD']).filter(
                Q(valid_to__isnull=True)|Q(valid_to__gte=today)).select_related('account').order_by('account__username')[:300]
        return Response([{'id':str(m.account_id),'username':m.account.username,'display_name':m.account.display_name,
                          'role':m.role, 'membership_id':str(m.id), 'invitation_status': 'ACTIVE' if m.account.has_usable_password() else 'NOT_SENT'} for m in rows])

    @transaction.atomic
    def post(self, request):
        self.require_school_admin()
        data = StaffSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        info = data.validated_data
        username = info['username'].strip()
        if not username:
            raise ValidationError({'username':'Username không được để trống.'})
        if Account.objects.filter(username=username).exists():
            # Privacy: avoid revealing which school already holds a global username.
            raise ValidationError({'username':'Username không khả dụng.'})
        account = Account(username=username, display_name=info['display_name'].strip(), email=info.get('email',''))
        account.set_unusable_password()  # invitation/reset workflow is required before login
        account.save()
        Membership.objects.create(tenant=self.tenant, account=account, role=info['role'],
                                  valid_from=timezone.localdate())
        self.audit(action='STAFF_CREATED', instance=account)
        return Response({'id':account.id, 'username':account.username, 'display_name':account.display_name,
                         'role':info['role'], 'invitation_status':'NOT_SENT'}, status=201)


class EnrollmentListView(TenantAPIView):
    def get(self, request):
        self.require_school_admin()
        visible = Student.objects.filter(tenant=self.tenant)
        qs = Enrollment.objects.filter(tenant=self.tenant, student__in=visible).select_related('student','classroom').order_by('-starts_on')[:500]
        return Response([{'id':str(x.id),'student_id':str(x.student_id),'student_name':x.student.full_name,
                          'classroom_id':str(x.classroom_id),'classroom_code':x.classroom.code,
                          'starts_on':x.starts_on, 'ends_on':x.ends_on, 'is_active':x.is_active} for x in qs])


class EnrollmentEndView(TenantAPIView):
    @transaction.atomic
    def post(self, request, enrollment_id):
        self.require_school_admin()
        enrollment = get_object_or_404(Enrollment.objects.select_for_update(), tenant=self.tenant, id=enrollment_id)
        if not enrollment.is_active:
            raise ValidationError({'enrollment':'Phân lớp đã kết thúc.'})
        enrollment.is_active = False
        enrollment.ends_on = max(enrollment.starts_on, timezone.localdate())
        enrollment.save(update_fields=['is_active','ends_on'])
        self.audit(action='ENROLLMENT_ENDED', instance=enrollment)
        return Response({'id':enrollment.id,'is_active':False})


class AssignmentListView(TenantAPIView):
    def get(self, request):
        self.require_school_admin()
        classes = Classroom.objects.filter(tenant=self.tenant)
        qs = TeacherAssignment.objects.filter(tenant=self.tenant, classroom__in=classes).select_related('teacher','classroom','subject').order_by('-starts_on')[:500]
        return Response([{'id':str(x.id),'teacher_id':str(x.teacher_id),'teacher_name':x.teacher.display_name or x.teacher.username,
                          'classroom_id':str(x.classroom_id),'classroom_code':x.classroom.code,
                          'kind':x.kind, 'subject_id':str(x.subject_id) if x.subject_id else None,
                          'subject_name':x.subject.name if x.subject else None,
                          'is_active':x.is_active,'starts_on':x.starts_on,'ends_on':x.ends_on} for x in qs])


class AssignmentEndView(TenantAPIView):
    @transaction.atomic
    def post(self, request, assignment_id):
        self.require_school_admin()
        item = get_object_or_404(TeacherAssignment.objects.select_for_update(), tenant=self.tenant, id=assignment_id)
        if not item.is_active:
            raise ValidationError({'assignment':'Phân công đã kết thúc.'})
        item.is_active = False
        item.ends_on = max(item.starts_on, timezone.localdate())
        item.save(update_fields=['is_active','ends_on'])
        self.audit(action='TEACHER_ASSIGNMENT_ENDED', instance=item)
        return Response({'id':item.id,'is_active':False})


class GuardianListView(TenantAPIView):
    def get(self, request):
        self.require_school_admin()
        rows = GuardianLink.objects.filter(tenant=self.tenant).select_related('guardian','student').order_by('-valid_from')[:300]
        return Response([{'id':str(x.id),'student_id':str(x.student_id),'student_name':x.student.full_name,
                          'guardian_id':str(x.guardian_id),'guardian_name':x.guardian.display_name or x.guardian.username,
                          'relation':x.relation,'is_verified':x.is_verified,'is_active':x.is_active} for x in rows])


class AuditListView(TenantAPIView):
    def get(self, request):
        self.require_school_admin()
        rows = AuditEvent.objects.filter(tenant=self.tenant).order_by('-created_at')[:100]
        return Response([{'id':str(x.id),'action':x.action,'target_type':x.target_type,
                          'target_id':str(x.target_id),'created_at':x.created_at} for x in rows])


class SchoolDashboardView(TenantAPIView):
    def get(self, request):
        self.require_school_admin()
        today = timezone.localdate()
        effective = Q(starts_on__lte=today) & (Q(ends_on__isnull=True) | Q(ends_on__gte=today))
        membership_effective = Q(valid_from__lte=today) & (Q(valid_to__isnull=True) | Q(valid_to__gte=today))
        return Response({
            'students':Student.objects.filter(tenant=self.tenant, is_active=True).count(),
            'classes':Classroom.objects.filter(tenant=self.tenant).count(),
            'staff_memberships':Membership.objects.filter(membership_effective, tenant=self.tenant, is_active=True, account__is_active=True,
                role__in=['HOMEROOM_TEACHER','SUBJECT_TEACHER','ACADEMIC_AFFAIRS','DEPARTMENT_HEAD']).count(),
            'academic_years':AcademicYear.objects.filter(tenant=self.tenant).count(),
            'active_enrollments':Enrollment.objects.filter(effective, tenant=self.tenant,is_active=True, classroom__year__starts_on__lte=today, classroom__year__ends_on__gte=today).count(),
            'active_assignments':TeacherAssignment.objects.filter(effective, tenant=self.tenant,is_active=True, classroom__year__starts_on__lte=today, classroom__year__ends_on__gte=today).count(),
        })

class GuardianAccountView(TenantAPIView):
    """Accounts are created disabled for interactive sign-in until an invitation flow exists."""
    def get(self, request):
        self.require_school_admin()
        today = timezone.localdate()
        rows = Membership.objects.filter(tenant=self.tenant, role='PARENT', is_active=True, account__is_active=True,
                valid_from__lte=today).filter(Q(valid_to__isnull=True)|Q(valid_to__gte=today)).select_related('account')[:300]
        return Response([{'id':str(m.account_id),'username':m.account.username,
                          'display_name':m.account.display_name or m.account.username, 'invitation_status': 'ACTIVE' if m.account.has_usable_password() else 'NOT_SENT'} for m in rows])

    @transaction.atomic
    def post(self, request):
        self.require_school_admin()
        username = serializers.CharField(max_length=150).run_validation(request.data.get('username'))
        display_name = serializers.CharField(max_length=200).run_validation(request.data.get('display_name'))
        if Account.objects.filter(username=username).exists():
            raise ValidationError({'username':'Username không khả dụng.'})
        actor = Account(username=username,display_name=display_name)
        actor.set_unusable_password()
        actor.save()
        Membership.objects.create(tenant=self.tenant,account=actor,role='PARENT',valid_from=timezone.localdate())
        self.audit(action='GUARDIAN_ACCOUNT_CREATED',instance=actor)
        return Response({'id':actor.id,'username':actor.username,'display_name':actor.display_name,
                         'invitation_status':'NOT_SENT'},status=201)
