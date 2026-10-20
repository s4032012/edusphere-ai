"""Sprint 0 endpoints: identity, roster and relations only (not the full Phase 1 API)."""
from uuid import UUID
from django.db import transaction, IntegrityError
from django.http import Http404
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.schools.models import Tenant, Membership, AuditEvent
from apps.identity.models import Account
from apps.academics.models import (AcademicYear, Subject, Classroom, Student,
    Enrollment, TeacherAssignment, GuardianLink)
from .scopes import active_roles, visible_students, visible_classrooms, student_profile_detail_level


class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ('id', 'student_code', 'full_name', 'date_of_birth', 'is_active')
        read_only_fields = ('id', 'is_active')

class ClassroomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Classroom
        fields = ('id','code','grade_level','year')
        read_only_fields = ('id',)

class StudentPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ('id','student_code','full_name')


class MeView(APIView):
    def get(self, request):
        today = timezone.localdate()
        memberships = Membership.objects.filter(account=request.user, is_active=True,
            tenant__is_active=True, valid_from__lte=today).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gte=today)).select_related('tenant')
        return Response({'id': request.user.id, 'username': request.user.username,
            'session_expires_at': request.auth['exp'],
            'display_name': request.user.display_name or request.user.username,
            'memberships': [{'tenant_id': str(m.tenant_id), 'tenant': m.tenant.name,
                             'role': m.role} for m in memberships]})


class TenantAPIView(APIView):
    tenant = None
    roles = set()

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        tenant_id = request.headers.get('X-Tenant-ID')
        if not tenant_id:
            raise ValidationError({'tenant': 'Thiếu header X-Tenant-ID.'})
        try:
            self.tenant = Tenant.objects.filter(id=tenant_id, is_active=True).first()
        except (ValueError, TypeError, DjangoValidationError):
            self.tenant = None
        if not self.tenant:
            raise Http404('Trường không tồn tại hoặc không hoạt động.')
        self.roles = active_roles(request.user, self.tenant)
        if not self.roles:
            # Do not disclose tenant membership details to a non-member.
            raise Http404('Không tìm thấy tài nguyên.')

    def handle_exception(self, exc):
        # Constraints are the final guard, including concurrent duplicate writes.
        if isinstance(exc, IntegrityError):
            exc = ValidationError({'detail': 'Dữ liệu trùng hoặc không hợp lệ.'})
        return super().handle_exception(exc)

    def payload_id(self, name):
        value = self.request.data.get(name)
        try:
            return UUID(str(value))
        except (ValueError, TypeError, AttributeError):
            raise ValidationError({name: 'Cần UUID hợp lệ.'})

    def require_school_admin(self):
        if 'SCHOOL_ADMIN' not in self.roles:
            raise PermissionDenied('Chỉ quản trị viên trường có quyền thực hiện.')

    def audit(self, *, action, instance):
        AuditEvent.objects.create(tenant=self.tenant, actor=self.request.user,
                                  action=action, target_type=instance._meta.label,
                                  target_id=instance.id)


class ClassroomListCreateView(TenantAPIView):
    def get(self, request):
        items = visible_classrooms(request.user, self.tenant, self.roles).order_by('code')[:200]
        return Response(ClassroomSerializer(items, many=True).data)

    @transaction.atomic
    def post(self, request):
        self.require_school_admin()
        serializer = ClassroomSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        year = serializer.validated_data['year']
        if year.tenant_id != self.tenant.id:
            raise ValidationError({'year': 'Năm học không thuộc trường này.'})
        if not 6 <= serializer.validated_data['grade_level'] <= 9:
            raise ValidationError({'grade_level': 'Pilot chỉ hỗ trợ lớp 6–9.'})
        if Classroom.objects.filter(tenant=self.tenant, year=year, code=serializer.validated_data['code']).exists():
            raise ValidationError({'code': 'Lớp đã tồn tại trong năm học.'})
        instance = serializer.save(tenant=self.tenant)
        self.audit(action='CLASSROOM_CREATED', instance=instance)
        return Response(ClassroomSerializer(instance).data, status=status.HTTP_201_CREATED)


class StudentListCreateView(TenantAPIView):
    def get(self, request):
        students = visible_students(request.user, self.tenant, self.roles).order_by('student_code')[:200]
        return Response([self._serialize(request, student) for student in students])

    def _serialize(self, request, student):
        level = student_profile_detail_level(request.user, self.tenant, self.roles, student)
        return (StudentSerializer(student).data if level == 'full'
                else StudentPublicSerializer(student).data)

    @transaction.atomic
    def post(self, request):
        self.require_school_admin()
        serializer = StudentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if Student.objects.filter(tenant=self.tenant, student_code=serializer.validated_data['student_code']).exists():
            raise ValidationError({'student_code': 'Mã học sinh đã tồn tại.'})
        instance = serializer.save(tenant=self.tenant)
        self.audit(action='STUDENT_CREATED', instance=instance)
        return Response(StudentSerializer(instance).data, status=status.HTTP_201_CREATED)


class StudentDetailView(TenantAPIView):
    def get(self, request, student_id):
        student = get_object_or_404(
            visible_students(request.user, self.tenant, self.roles), id=student_id)
        if student_profile_detail_level(request.user, self.tenant, self.roles, student) == 'full':
            return Response(StudentSerializer(student).data)
        return Response(StudentPublicSerializer(student).data)


class EnrollmentCreateView(TenantAPIView):
    @transaction.atomic
    def post(self, request):
        self.require_school_admin()
        student = get_object_or_404(Student.objects.select_for_update(), id=self.payload_id('student_id'), tenant=self.tenant, is_active=True)
        classroom = get_object_or_404(Classroom.objects.select_for_update(), id=self.payload_id('classroom_id'), tenant=self.tenant)
        today = timezone.localdate()
        if not classroom.year.starts_on <= today <= classroom.year.ends_on:
            raise ValidationError({'classroom_id': 'Năm học của lớp chưa hoặc không còn hiệu lực.'})
        if Enrollment.objects.select_for_update().filter(
            tenant=self.tenant, student=student, is_active=True
        ).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today)).exists():
            raise ValidationError({'student_id':'Học sinh đã có lớp đang hiệu lực.'})
        enrollment = Enrollment.objects.create(tenant=self.tenant, student=student,
                      classroom=classroom, starts_on=today, ends_on=classroom.year.ends_on)
        self.audit(action='ENROLLMENT_CREATED', instance=enrollment)
        return Response({'id': enrollment.id}, status=201)


class TeacherAssignmentCreateView(TenantAPIView):
    @transaction.atomic
    def post(self, request):
        self.require_school_admin()
        teacher = get_object_or_404(Account, id=self.payload_id('teacher_id'), is_active=True)
        classroom = get_object_or_404(Classroom.objects.select_for_update(), id=self.payload_id('classroom_id'), tenant=self.tenant)
        kind = request.data.get('kind')
        if kind not in {'HOMEROOM','SUBJECT'}:
            raise ValidationError({'kind': 'HOMEROOM hoặc SUBJECT.'})
        required_role = 'HOMEROOM_TEACHER' if kind == 'HOMEROOM' else 'SUBJECT_TEACHER'
        if required_role not in active_roles(teacher, self.tenant):
            raise ValidationError({'teacher_id':'Giáo viên chưa có membership phù hợp tại trường.'})
        subject = None
        if kind == 'SUBJECT':
            subject = get_object_or_404(Subject, id=self.payload_id('subject_id'), tenant=self.tenant)
        elif request.data.get('subject_id'):
            raise ValidationError({'subject_id':'GVCN không cần môn học.'})
        today = timezone.localdate()
        if not classroom.year.starts_on <= today <= classroom.year.ends_on:
            raise ValidationError({'classroom_id': 'Năm học của lớp chưa hoặc không còn hiệu lực.'})
        existing = TeacherAssignment.objects.filter(
            tenant=self.tenant, classroom=classroom, kind=kind, is_active=True
        ).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today))
        if kind == 'HOMEROOM' and existing.exists():
            raise ValidationError({'classroom_id': 'Lớp đã có giáo viên chủ nhiệm đang hiệu lực.'})
        if kind == 'SUBJECT' and existing.filter(subject=subject, teacher=teacher).exists():
            raise ValidationError({'subject_id': 'Phân công bộ môn này đã tồn tại.'})
        assignment = TeacherAssignment.objects.create(
            tenant=self.tenant, teacher=teacher, classroom=classroom, subject=subject,
            kind=kind, starts_on=today, ends_on=classroom.year.ends_on)
        self.audit(action='TEACHER_ASSIGNED', instance=assignment)
        return Response({'id': assignment.id, 'kind': assignment.kind}, status=201)


class GuardianLinkCreateView(TenantAPIView):
    @transaction.atomic
    def post(self, request):
        self.require_school_admin()
        guardian = get_object_or_404(Account, id=self.payload_id('guardian_id'), is_active=True)
        student = get_object_or_404(Student.objects.select_for_update(), id=self.payload_id('student_id'), tenant=self.tenant, is_active=True)
        if 'PARENT' not in active_roles(guardian, self.tenant):
            raise ValidationError({'guardian_id':'Người giám hộ chưa có membership tại trường.'})
        relation = serializers.CharField(max_length=40).run_validation(request.data.get('relation', 'GUARDIAN'))
        if GuardianLink.objects.filter(tenant=self.tenant, student=student, guardian=guardian, is_active=True).filter(Q(valid_to__isnull=True) | Q(valid_to__gte=timezone.localdate())).exists():
            raise ValidationError({'guardian_id': 'Liên kết giám hộ đang hoạt động đã tồn tại.'})
        # No automatic verification from API payload. Human verification comes later.
        link = GuardianLink.objects.create(tenant=self.tenant, student=student,
            guardian=guardian, relation=relation,
            valid_from=timezone.localdate(), is_verified=False)
        self.audit(action='GUARDIAN_LINK_REQUESTED', instance=link)
        return Response({'id': link.id, 'is_verified': False}, status=201)


class GuardianVerifyView(TenantAPIView):
    @transaction.atomic
    def post(self, request, link_id):
        self.require_school_admin()
        link = get_object_or_404(GuardianLink.objects.select_for_update(),
                                 id=link_id, tenant=self.tenant)
        if not link.is_active:
            raise ValidationError({'link':'Liên kết đã vô hiệu.'})
        if not request.data.get('evidence_checked') is True:
            raise ValidationError({'evidence_checked': 'Phải xác nhận đã kiểm tra bằng chứng.'})
        link.is_verified = True
        link.verified_by = request.user
        link.save(update_fields=['is_verified','verified_by'])
        self.audit(action='GUARDIAN_LINK_VERIFIED', instance=link)
        return Response({'id': link.id, 'is_verified': True})
