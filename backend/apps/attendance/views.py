"""Sprint 2 daily roll-call and parent leave workflows (one THCS pilot)."""
from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from apps.access.views import TenantAPIView
from apps.academics.models import Classroom, Enrollment, Student, TeacherAssignment, GuardianLink, StudentAccount
from apps.schools.models import Tenant
from .models import AttendanceSession, AttendanceRecord, LeaveRequest, NotificationOutbox
from .rules import leave_range_valid, next_leave_state, effective_presence, can_edit_attendance

def lock_school(tenant):
    # Pilot-sized write serialization prevents submit/approval outbox races.
    Tenant.objects.select_for_update().get(pk=tenant.pk)


SCHOOL_ATTENDANCE = {'SCHOOL_ADMIN', 'ACADEMIC_AFFAIRS'}
SCHOOL_LEAVE_READ = SCHOOL_ATTENDANCE | {'PRINCIPAL', 'VICE_PRINCIPAL'}

class AttendanceStartSerializer(serializers.Serializer):
    classroom_id = serializers.UUIDField()
    attendance_date = serializers.DateField()

class AttendanceRowSerializer(serializers.Serializer):
    student_id = serializers.UUIDField()
    mark = serializers.ChoiceField(choices=AttendanceRecord.Mark.choices)
    note = serializers.CharField(max_length=300, allow_blank=True, required=False)

class BatchSerializer(serializers.Serializer):
    records = AttendanceRowSerializer(many=True, allow_empty=False)

class LeaveCreateSerializer(serializers.Serializer):
    student_id = serializers.UUIDField()
    from_date = serializers.DateField()
    through_date = serializers.DateField()
    reason = serializers.CharField(max_length=500, min_length=5, trim_whitespace=True)

class LeaveDecisionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['approve','reject'])
    decision_note = serializers.CharField(max_length=500, allow_blank=True, required=False)


def active_homeroom(user, tenant, classroom, on_date):
    """Must hold the assignment now AND on the target date; never trust old role alone."""
    now = timezone.localdate()
    return TeacherAssignment.objects.filter(
        tenant=tenant, teacher=user, classroom=classroom, kind='HOMEROOM', is_active=True,
        classroom__year__starts_on__lte=now, classroom__year__ends_on__gte=now,
        starts_on__lte=min(on_date, now)
    ).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=max(on_date, now))).exists()


def can_manage_class(user, tenant, roles, classroom, on_date):
    return bool(SCHOOL_ATTENDANCE & roles) or ('HOMEROOM_TEACHER' in roles and active_homeroom(user, tenant, classroom, on_date))


def can_view_class(user, tenant, roles, classroom, on_date):
    return bool(SCHOOL_LEAVE_READ & roles) or can_manage_class(user, tenant, roles, classroom, on_date)


def eligible_roster(tenant, classroom, on_date):
    return Enrollment.objects.filter(
        tenant=tenant, classroom=classroom, student__tenant=tenant,
        student__is_active=True, is_active=True, starts_on__lte=on_date
    ).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=on_date)).values_list('student_id', flat=True).distinct()


def verified_guardians(tenant, student, on_date):
    return GuardianLink.objects.filter(
        tenant=tenant, student=student, student__is_active=True, is_active=True, is_verified=True, can_view_academic=True,
        valid_from__lte=on_date
    ).filter(Q(valid_to__isnull=True) | Q(valid_to__gte=on_date))


def has_guardian_link(user, tenant, student):
    return verified_guardians(tenant, student, timezone.localdate()).filter(guardian=user).exists()


def parent_can_see_leave(user, tenant, roles, student):
    return 'PARENT' in roles and has_guardian_link(user, tenant, student)


def reviewer_can_see_leave(user, tenant, roles, student):
    if SCHOOL_LEAVE_READ & roles:
        return True
    today = timezone.localdate()
    classes = Classroom.objects.filter(
        tenant=tenant, enrollments__student=student, enrollments__tenant=tenant,
        enrollments__is_active=True, enrollments__starts_on__lte=today
    ).filter(Q(enrollments__ends_on__isnull=True) | Q(enrollments__ends_on__gte=today))
    return 'HOMEROOM_TEACHER' in roles and any(active_homeroom(user, tenant, cl, today) for cl in classes.distinct())


def serialize_leave(obj, *, show_reason=True):
    record = {'id':str(obj.id),'student_id':str(obj.student_id), 'from_date':obj.from_date.isoformat(),
              'through_date':obj.through_date.isoformat(),'state':obj.state,
              'created_at':obj.created_at.isoformat(),'decision_note':obj.decision_note}
    if show_reason:
        record['reason'] = obj.reason
    return record


def emit_outbox(tenant, recipient, event_type, subject_id, payload):
    key = f'{tenant.id}:{recipient.id}:{event_type}:{subject_id}'
    NotificationOutbox.objects.get_or_create(dedupe_key=key,
        defaults={'tenant':tenant,'recipient':recipient,'event_type':event_type,
                  'subject_id':subject_id,'payload':payload})


class AttendanceSessionList(TenantAPIView):
    def get(self, request):
        qs = AttendanceSession.objects.filter(tenant=self.tenant).select_related('classroom').order_by('-attendance_date')
        date_string = request.query_params.get('date')
        classroom_id = request.query_params.get('classroom_id')
        if date_string:
            field = serializers.DateField()
            target = field.run_validation(date_string)
            qs = qs.filter(attendance_date=target)
        if classroom_id:
            try:
                qs = qs.filter(classroom_id=serializers.UUIDField().run_validation(classroom_id))
            except serializers.ValidationError as exc:
                raise ValidationError({'classroom_id':exc.detail})
        return Response([
            {'id':str(s.id),'classroom_id':str(s.classroom_id),'classroom_code':s.classroom.code,
             'attendance_date':s.attendance_date.isoformat(),'state':s.state}
            for s in qs if can_view_class(request.user,self.tenant,self.roles,s.classroom,s.attendance_date)
        ][:200])

    @transaction.atomic
    def post(self, request):
        lock_school(self.tenant)
        data = AttendanceStartSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        on_date = data.validated_data['attendance_date']
        today = timezone.localdate()
        if not today - timedelta(days=7) <= on_date <= today:
            raise ValidationError({'attendance_date':'Điểm danh chỉ được mở cho hôm nay hoặc 7 ngày trước.'})
        classroom = get_object_or_404(Classroom.objects.select_for_update(), tenant=self.tenant,
                                       id=data.validated_data['classroom_id'])
        if not classroom.year.starts_on <= on_date <= classroom.year.ends_on:
            raise ValidationError({'attendance_date':'Ngày không thuộc năm học của lớp.'})
        if not can_manage_class(request.user,self.tenant,self.roles,classroom,on_date):
            raise PermissionDenied('Không được điểm danh lớp này.')
        session, created = AttendanceSession.objects.get_or_create(
            tenant=self.tenant,classroom=classroom,attendance_date=on_date,
            defaults={'created_by':request.user})
        if created:
            self.audit(action='ATTENDANCE_SESSION_STARTED',instance=session)
        return Response({'id':str(session.id),'state':session.state,'created':created},
                        status=status.HTTP_201_CREATED if created else 200)

class AttendanceSessionDetail(TenantAPIView):
    def get(self, request, session_id):
        session = get_object_or_404(AttendanceSession.objects.select_related('classroom'), tenant=self.tenant,id=session_id)
        if not can_view_class(request.user,self.tenant,self.roles,session.classroom,session.attendance_date):
            raise PermissionDenied('Không được xem điểm danh lớp này.')
        roster_ids = eligible_roster(self.tenant,session.classroom,session.attendance_date) if session.state == 'DRAFT' else AttendanceRecord.objects.filter(tenant=self.tenant,session=session).values_list('student_id',flat=True)
        roster = list(Student.objects.filter(tenant=self.tenant,id__in=roster_ids)
                      .order_by('student_code').values('id','student_code','full_name'))
        records = {r.student_id:r for r in AttendanceRecord.objects.filter(tenant=self.tenant,session=session)}
        approved = set(LeaveRequest.objects.filter(tenant=self.tenant,state='APPROVED',student_id__in=[s['id'] for s in roster],
                     from_date__lte=session.attendance_date,through_date__gte=session.attendance_date).values_list('student_id',flat=True))
        approved_str = {str(v) for v in approved}
        for student in roster:
            record = records.get(student['id'])
            student['id'] = str(student['id'])
            student['mark'] = record.mark if record else None
            student['note'] = record.note if record else ''
            student['effective_status'] = effective_presence(record.mark,student['id'] in approved_str) if record else None
        return Response({'id':str(session.id),'classroom_id':str(session.classroom_id),'attendance_date':session.attendance_date.isoformat(),
                         'state':session.state,'roster':roster})

class AttendanceBatchWrite(TenantAPIView):
    @transaction.atomic
    def put(self, request, session_id):
        lock_school(self.tenant)
        session = get_object_or_404(AttendanceSession.objects.select_for_update().select_related('classroom'),
                                    tenant=self.tenant,id=session_id)
        if not can_manage_class(request.user,self.tenant,self.roles,session.classroom,session.attendance_date):
            raise PermissionDenied('Không được sửa điểm danh lớp này.')
        if not can_edit_attendance(session.state):
            raise ValidationError({'state':'Phiên điểm danh đã nộp/khóa; không được sửa.'})
        data = BatchSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        rows = data.validated_data['records']
        ids = [r['student_id'] for r in rows]
        if len(ids) != len(set(ids)):
            raise ValidationError({'records':'Trùng học sinh trong cùng một batch.'})
        eligible = set(eligible_roster(self.tenant,session.classroom,session.attendance_date))
        if not set(ids).issubset(eligible):
            raise ValidationError({'records':'Có học sinh không thuộc lớp vào ngày điểm danh.'})
        for row in rows:
            AttendanceRecord.objects.update_or_create(session=session,student_id=row['student_id'],
                defaults={'tenant':self.tenant,'mark':row['mark'],'note':row.get('note',''),'updated_by':request.user})
        self.audit(action='ATTENDANCE_RECORDS_SAVED',instance=session)
        return Response({'updated':len(rows),'state':session.state})

class AttendanceSubmit(TenantAPIView):
    @transaction.atomic
    def post(self, request, session_id):
        lock_school(self.tenant)
        session = get_object_or_404(AttendanceSession.objects.select_for_update().select_related('classroom'),
                                    tenant=self.tenant,id=session_id)
        if not can_manage_class(request.user,self.tenant,self.roles,session.classroom,session.attendance_date):
            raise PermissionDenied('Không được nộp điểm danh lớp này.')
        if session.state != 'DRAFT':
            raise ValidationError({'state':'Chỉ phiên DRAFT được nộp.'})
        eligible = set(eligible_roster(self.tenant,session.classroom,session.attendance_date))
        marked = set(AttendanceRecord.objects.filter(tenant=self.tenant,session=session).values_list('student_id',flat=True))
        if not eligible or marked != eligible:
            raise ValidationError({'records':f'Điểm danh chưa đủ: {len(marked & eligible)}/{len(eligible)} học sinh.'})
        session.state='SUBMITTED';session.submitted_at=timezone.now();session.save(update_fields=['state','submitted_at'])
        for record in AttendanceRecord.objects.filter(tenant=self.tenant,session=session,mark='ABSENT'):
            exists = LeaveRequest.objects.filter(tenant=self.tenant,student=record.student,state='APPROVED',
                from_date__lte=session.attendance_date,through_date__gte=session.attendance_date).exists()
            if not exists:
                for link in verified_guardians(self.tenant,record.student,timezone.localdate()):
                    emit_outbox(self.tenant,link.guardian,'UNEXCUSED_ABSENCE',record.id,
                                {'student_id':str(record.student_id),'attendance_date':session.attendance_date.isoformat()})
        self.audit(action='ATTENDANCE_SUBMITTED',instance=session)
        return Response({'id':str(session.id),'state':session.state})

class AttendanceLock(TenantAPIView):
    @transaction.atomic
    def post(self,request,session_id):
        lock_school(self.tenant)
        if 'SCHOOL_ADMIN' not in self.roles:
            raise PermissionDenied('Chỉ quản trị viên được khóa điểm danh.')
        session=get_object_or_404(AttendanceSession.objects.select_for_update(),tenant=self.tenant,id=session_id)
        if session.state!='SUBMITTED':
            raise ValidationError({'state':'Chỉ phiên SUBMITTED được khóa.'})
        session.state='LOCKED';session.locked_at=timezone.now();session.save(update_fields=['state','locked_at'])
        self.audit(action='ATTENDANCE_LOCKED',instance=session)
        return Response({'id':str(session.id),'state':session.state})

class StudentAttendance(TenantAPIView):
    def get(self,request,student_id):
        from apps.access.scopes import visible_students
        student=get_object_or_404(visible_students(request.user,self.tenant,self.roles),id=student_id)
        qs=AttendanceRecord.objects.filter(tenant=self.tenant,student=student,session__state__in=['SUBMITTED','LOCKED'])
        allowed = bool(SCHOOL_LEAVE_READ & self.roles) or parent_can_see_leave(request.user,self.tenant,self.roles,student)
        allowed = allowed or ('HOMEROOM_TEACHER' in self.roles and reviewer_can_see_leave(request.user,self.tenant,self.roles,student))
        allowed = allowed or ('STUDENT' in self.roles and StudentAccount.objects.filter(tenant=self.tenant,student=student,account=request.user).exists())
        if not allowed:
            raise PermissionDenied('Không được xem chuyên cần này.')
        data=[]
        for r in qs.select_related('session').order_by('-session__attendance_date')[:120]:
            date=r.session.attendance_date
            has_leave=LeaveRequest.objects.filter(tenant=self.tenant,student=student,state='APPROVED',
                                                  from_date__lte=date,through_date__gte=date).exists()
            data.append({'date':date.isoformat(),'mark':r.mark,'effective_status':effective_presence(r.mark,has_leave)})
        return Response(data)

class LeaveListCreate(TenantAPIView):
    def get(self,request):
        qs=LeaveRequest.objects.filter(tenant=self.tenant).select_related('student').order_by('-created_at')
        student_id=request.query_params.get('student_id')
        if student_id:
            try: qs=qs.filter(student_id=serializers.UUIDField().run_validation(student_id))
            except serializers.ValidationError as exc: raise ValidationError({'student_id':exc.detail})
        # School administration sees all; teachers only current homeroom; parents only verified links.
        items=[{'student_name':r.student.full_name,**serialize_leave(r)} for r in qs
               if (SCHOOL_LEAVE_READ & self.roles or (r.guardian_id == request.user.id and parent_can_see_leave(request.user,self.tenant,self.roles,r.student))
                   or reviewer_can_see_leave(request.user,self.tenant,self.roles,r.student))]
        return Response(items[:200])

    @transaction.atomic
    def post(self,request):
        lock_school(self.tenant)
        if 'PARENT' not in self.roles:
            raise PermissionDenied('Chỉ phụ huynh đã xác minh được gửi đơn.')
        data=LeaveCreateSerializer(data=request.data);data.is_valid(raise_exception=True)
        d=data.validated_data;today=timezone.localdate()
        student=get_object_or_404(Student.objects.select_for_update(),tenant=self.tenant,is_active=True,id=d['student_id'])
        if not has_guardian_link(request.user,self.tenant,student):
            raise PermissionDenied('Không có quyền gửi đơn cho học sinh này.')
        if not leave_range_valid(d['from_date'],d['through_date'],today):
            raise ValidationError({'date':'Khoảng ngày không hợp lệ theo chính sách thử nghiệm (<=14 ngày, -7/+90 ngày).'})
        if not Enrollment.objects.filter(tenant=self.tenant,student=student,is_active=True,
                                         starts_on__lte=d['from_date'], classroom__year__starts_on__lte=d['from_date'],
                                         classroom__year__ends_on__gte=d['through_date']).filter(
                        Q(ends_on__isnull=True)|Q(ends_on__gte=d['through_date'])).exists():
            raise ValidationError({'student_id':'Học sinh không có phân lớp có hiệu lực trong khoảng xin nghỉ.'})
        if LeaveRequest.objects.filter(tenant=self.tenant,student=student,state__in=['PENDING','APPROVED'],
               from_date__lte=d['through_date'],through_date__gte=d['from_date']).exists():
            raise ValidationError({'date':'Đã có đơn đang xử lý hoặc được duyệt trong khoảng ngày này.'})
        leave=LeaveRequest.objects.create(tenant=self.tenant,student=student,guardian=request.user,
            from_date=d['from_date'],through_date=d['through_date'],reason=d['reason'])
        self.audit(action='LEAVE_REQUEST_SUBMITTED',instance=leave)
        return Response(serialize_leave(leave),status=201)

class LeaveDecision(TenantAPIView):
    @transaction.atomic
    def post(self,request,leave_id):
        lock_school(self.tenant)
        leave=get_object_or_404(LeaveRequest.objects.select_for_update().select_related('student'),tenant=self.tenant,id=leave_id)
        if not ((SCHOOL_ATTENDANCE & self.roles) or ('HOMEROOM_TEACHER' in self.roles and reviewer_can_see_leave(
                request.user,self.tenant,self.roles,leave.student))):
            raise PermissionDenied('Không có quyền duyệt đơn này.')
        data=LeaveDecisionSerializer(data=request.data);data.is_valid(raise_exception=True)
        try: new_state=next_leave_state(leave.state,data.validated_data['action'],'reviewer')
        except ValueError as exc: raise ValidationError({'state':str(exc)})
        leave.state=new_state;leave.decided_by=request.user;leave.decision_note=data.validated_data.get('decision_note','')
        leave.decided_at=timezone.now();leave.save(update_fields=['state','decided_by','decision_note','decided_at','updated_at'])
        if leave.state == 'APPROVED':
            # Suppress un-delivered absence alerts when a late leave is approved.
            NotificationOutbox.objects.filter(tenant=self.tenant,
                event_type='UNEXCUSED_ABSENCE',state='QUEUED',
                subject_id__in=AttendanceRecord.objects.filter(tenant=self.tenant,student=leave.student,
                    mark='ABSENT',session__attendance_date__range=(leave.from_date,leave.through_date)).values('id')
            ).update(state='CANCELED')
        emit_outbox(self.tenant,leave.guardian,'LEAVE_DECIDED',leave.id,{'state':leave.state,'leave_id':str(leave.id)})
        self.audit(action='LEAVE_'+leave.state,instance=leave)
        return Response(serialize_leave(leave))

class LeaveWithdraw(TenantAPIView):
    @transaction.atomic
    def post(self,request,leave_id):
        lock_school(self.tenant)
        leave=get_object_or_404(LeaveRequest.objects.select_for_update().select_related('student'),tenant=self.tenant,id=leave_id)
        if 'PARENT' not in self.roles or leave.guardian_id!=request.user.id or not has_guardian_link(request.user,self.tenant,leave.student):
            raise PermissionDenied('Chỉ phụ huynh tạo đơn mới được rút đơn.')
        try: state=next_leave_state(leave.state,'withdraw','guardian')
        except ValueError as exc: raise ValidationError({'state':str(exc)})
        leave.state=state;leave.save(update_fields=['state','updated_at'])
        self.audit(action='LEAVE_WITHDRAWN',instance=leave)
        return Response(serialize_leave(leave))

class MyNotifications(TenantAPIView):
    def get(self,request):
        items=NotificationOutbox.objects.filter(tenant=self.tenant,recipient=request.user,state='QUEUED').order_by('-created_at')
        data=[]
        if 'PARENT' not in self.roles:
            return Response(data)
        for event in items:
            if event.event_type == 'UNEXCUSED_ABSENCE':
                record=AttendanceRecord.objects.filter(tenant=self.tenant,id=event.subject_id).select_related('student').first()
                student=record.student if record else None
            elif event.event_type == 'LEAVE_DECIDED':
                leave=LeaveRequest.objects.filter(tenant=self.tenant,id=event.subject_id,guardian=request.user).select_related('student').first()
                student=leave.student if leave else None
            else:
                continue
            if student and student.is_active and has_guardian_link(request.user,self.tenant,student):
                data.append({'id':str(event.id),'type':event.event_type,'payload':event.payload,'state':event.state,
                             'created_at':event.created_at.isoformat()})
            if len(data) == 100:
                break
        return Response(data)
