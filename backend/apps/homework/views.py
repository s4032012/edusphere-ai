"""Sprint 4: tenant-safe text homework, submitted work and teacher feedback.

Not a file-storage service or an official student grade record.
"""
from uuid import UUID
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
from rest_framework.response import Response
from apps.access.views import TenantAPIView
from apps.academics.models import Classroom, Subject, Student, StudentAccount, GuardianLink, TeacherAssignment, Enrollment
from apps.attendance.models import NotificationOutbox
from apps.attendance.views import lock_school
from .models import HomeworkAssignment, HomeworkSubmission
from .rules import assignment_transition, can_submit, can_mark, parse_feedback_score, submission_status


def validate_fields(data, allowed):
    if not isinstance(data,dict) or set(data)-allowed:
        raise ValidationError({'detail':'Dữ liệu hoặc trường không hợp lệ.'})


def text_value(value):
    if not isinstance(value,str): raise ValidationError({'detail':'Nội dung phải là văn bản.'})
    return value.strip()


def uuid_value(value):
    try: return UUID(str(value))
    except (TypeError,ValueError,AttributeError): raise ValidationError({'detail':'ID không hợp lệ.'})


def version_value(value):
    if type(value) is not int or value<0: raise ValidationError({'expected_version':'Phiên bản phải là số nguyên không âm.'})
    return value


def parse_due(value):
    from django.utils.dateparse import parse_datetime
    if not isinstance(value,str): raise ValidationError({'due_at':'Ngày giờ không hợp lệ.'})
    try: return parse_datetime(value)
    except (ValueError,TypeError,OverflowError): raise ValidationError({'due_at':'Ngày giờ không hợp lệ.'})

ADMIN = {'SCHOOL_ADMIN', 'ACADEMIC_AFFAIRS', 'PRINCIPAL', 'VICE_PRINCIPAL'}


def enrollments(tenant, *, student=None, classroom=None):
    today = timezone.localdate()
    qs = Enrollment.objects.filter(tenant=tenant, student__tenant=tenant, classroom__tenant=tenant,
                                   is_active=True, starts_on__lte=today, classroom__year__tenant=tenant,
                                   classroom__year__starts_on__lte=today, classroom__year__ends_on__gte=today, student__is_active=True).filter(
        Q(ends_on__isnull=True) | Q(ends_on__gte=today))
    if student is not None: qs = qs.filter(student=student)
    if classroom is not None: qs = qs.filter(classroom=classroom)
    return qs


def teach(view, obj, kind='SUBJECT'):
    today = timezone.localdate()
    query = TeacherAssignment.objects.filter(tenant=view.tenant, teacher=view.request.user,
            classroom=obj.classroom, kind=kind, is_active=True, starts_on__lte=today,
            classroom__year__tenant=view.tenant, classroom__year__starts_on__lte=today, classroom__year__ends_on__gte=today).filter(
                Q(ends_on__isnull=True) | Q(ends_on__gte=today))
    if kind == 'SUBJECT': query = query.filter(subject=obj.subject)
    return query.exists()


def guardian(view, student):
    today = timezone.localdate()
    return ('PARENT' in view.roles and GuardianLink.objects.filter(
        tenant=view.tenant, student=student, guardian=view.request.user,
        is_verified=True, can_view_academic=True, is_active=True, valid_from__lte=today).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gte=today)).exists())


def self_student(view, student):
    return ('STUDENT' in view.roles and StudentAccount.objects.filter(
        tenant=view.tenant, student=student, account=view.request.user).exists())


def assigned_scope(view):
    today = timezone.localdate()
    valid = TeacherAssignment.objects.filter(tenant=view.tenant, teacher=view.request.user,
        is_active=True, starts_on__lte=today, classroom__tenant=view.tenant, classroom__year__tenant=view.tenant,
        classroom__year__starts_on__lte=today,classroom__year__ends_on__gte=today).filter(Q(ends_on__isnull=True)|Q(ends_on__gte=today))
    qs = HomeworkAssignment.objects.filter(tenant=view.tenant).select_related('classroom','subject')
    if ADMIN & view.roles: return qs
    subject_ids = valid.filter(kind='SUBJECT').values('classroom_id','subject_id')
    q = Q(pk__in=[])
    if 'SUBJECT_TEACHER' in view.roles or 'DEPARTMENT_HEAD' in view.roles:
        # Explicit row-level check below; no authorization purely from a broad role.
        sub = list(subject_ids)
        for item in sub: q |= Q(classroom_id=item['classroom_id'],subject_id=item['subject_id'])
    if 'HOMEROOM_TEACHER' in view.roles:
        q |= Q(classroom_id__in=valid.filter(kind='HOMEROOM').values('classroom_id'),state__in=['PUBLISHED','CLOSED'])
    if q: return qs.filter(q).filter(Q(state__in=['PUBLISHED','CLOSED'])|Q(teacher=view.request.user)).distinct()
    return qs.none()


def owner_or_assigned(view, task):
    return (task.teacher_id == view.request.user.id and
            bool({'SUBJECT_TEACHER','DEPARTMENT_HEAD'} & view.roles) and teach(view,task))


def subject_reader(view, task):
    return bool({'SUBJECT_TEACHER', 'DEPARTMENT_HEAD'} & view.roles) and teach(view, task)


def task_json(task, view):
    return {'can_manage':owner_or_assigned(view,task),'id':str(task.id),'classroom_id':str(task.classroom_id),
            'classroom_code':task.classroom.code,'subject_id':str(task.subject_id),
            'subject_name':task.subject.name,'teacher_id':str(task.teacher_id),
            'title':task.title,'instructions':task.instructions,'due_at':task.due_at.isoformat(),
            'allow_late':task.allow_late,'state':task.state,'created_at':task.created_at.isoformat()}


def submission_json(sub, *, detail=True):
    if sub is None: return None
    return {'id':str(sub.id),'student_id':str(sub.student_id),'state':sub.state,
        'version':sub.version,'submitted_at':sub.submitted_at.isoformat() if sub.submitted_at else None,
        'returned_at':sub.returned_at.isoformat() if sub.returned_at else None,
        'content_text':sub.content_text if detail else None,
        'feedback':sub.feedback if sub.state=='RETURNED' else None,
        'score':str(sub.score) if sub.score is not None and sub.state=='RETURNED' else None}


def notify(tenant, recipient, event, subject_id, dedupe_key, payload):
    NotificationOutbox.objects.get_or_create(dedupe_key=dedupe_key,defaults={
        'tenant':tenant,'recipient':recipient,'event_type':event,
        'subject_id':subject_id,'payload':payload})


class HomeworkListCreate(TenantAPIView):
    def get(self, request):
        if ADMIN & self.roles or {'SUBJECT_TEACHER','HOMEROOM_TEACHER','DEPARTMENT_HEAD'} & self.roles:
            qs = assigned_scope(self)
            return Response([task_json(x,self) for x in qs.order_by('-created_at')[:150]])
        if 'PARENT' in self.roles or 'STUDENT' in self.roles:
            if 'PARENT' in self.roles:
                today=timezone.localdate()
                student_ids=GuardianLink.objects.filter(tenant=self.tenant, guardian=request.user, is_active=True,
                    is_verified=True,can_view_academic=True,valid_from__lte=today).filter(
                    Q(valid_to__isnull=True)|Q(valid_to__gte=today)).values('student_id')
            else:
                student_ids=StudentAccount.objects.filter(tenant=self.tenant,account=request.user).values('student_id')
            qs=HomeworkAssignment.objects.filter(tenant=self.tenant,state__in=['PUBLISHED','CLOSED'],
                classroom__enrollments__in=enrollments(self.tenant).filter(student_id__in=student_ids)).distinct()
            return Response([task_json(x,self) for x in qs.select_related('classroom','subject').order_by('due_at')[:150]])
        raise PermissionDenied('Không có quyền xem bài tập.')

    @transaction.atomic
    def post(self, request):
        lock_school(self.tenant)
        if not ({'SUBJECT_TEACHER','DEPARTMENT_HEAD'} & self.roles):
            raise PermissionDenied('Chỉ giáo viên phụ trách môn được tạo bài tập.')
        d=request.data
        validate_fields(d, {'classroom_id','subject_id','title','instructions','due_at','allow_late'})
        clazz=get_object_or_404(Classroom, id=uuid_value(d.get('classroom_id')), tenant=self.tenant)
        subject=get_object_or_404(Subject, id=uuid_value(d.get('subject_id')), tenant=self.tenant)
        virtual=type('AssignmentScope',(),{'classroom':clazz,'subject':subject})()
        if not teach(self,virtual): raise PermissionDenied('Không được phân công môn/lớp này.')
        title=text_value(d.get('title')); instructions=text_value(d.get('instructions'))
        if not 1<=len(title)<=160 or not 1<=len(instructions)<=10000:
            raise ValidationError({'detail':'Tiêu đề và nội dung bắt buộc trong giới hạn cho phép.'})
        due_at=parse_due(d.get('due_at'))
        if due_at is None or timezone.is_naive(due_at) or due_at <= timezone.now():
            raise ValidationError({'due_at':'Hạn nộp phải là thời điểm tương lai có múi giờ.'})
        allow_late=d.get('allow_late',False)
        if type(allow_late) is not bool: raise ValidationError({'allow_late':'Giá trị boolean.'})
        task=HomeworkAssignment.objects.create(tenant=self.tenant,classroom=clazz,subject=subject,
            teacher=request.user,title=title,instructions=instructions,due_at=due_at,allow_late=allow_late)
        self.audit(action='HOMEWORK_CREATED',instance=task)
        return Response(task_json(task,self),status=status.HTTP_201_CREATED)


class HomeworkDetail(TenantAPIView):
    def get(self, request, task_id):
        task=get_object_or_404(HomeworkAssignment.objects.select_related('classroom','subject'),tenant=self.tenant,id=task_id)
        if ADMIN & self.roles or assigned_scope(self).filter(id=task.id).exists():
            return Response(task_json(task,self))
        if task.state != 'DRAFT' and (guardian_student_class(self,task) or self_student_class(self,task)):
            return Response(task_json(task,self))
        raise NotFound()

    @transaction.atomic
    def patch(self,request,task_id):
        lock_school(self.tenant)
        task=get_object_or_404(HomeworkAssignment.objects.select_for_update().select_related('classroom','subject'),tenant=self.tenant,id=task_id)
        if not owner_or_assigned(self,task): raise PermissionDenied()
        if task.state!='DRAFT': raise ValidationError({'detail':'Chỉ chỉnh sửa bài tập còn nháp.'})
        allowed={'title','instructions','due_at','allow_late'}
        validate_fields(request.data,allowed)
        if not request.data or set(request.data.keys())-allowed: raise ValidationError({'detail':'Trường chỉnh sửa không hợp lệ.'})
        for key in request.data:
            value=request.data[key]
            if key=='title':
                value=text_value(value)
                if not 1<=len(value)<=160: raise ValidationError({'title':'Tiêu đề không hợp lệ.'})
            elif key=='instructions':
                value=text_value(value)
                if not 1<=len(value)<=10000: raise ValidationError({'instructions':'Nội dung không hợp lệ.'})
            elif key=='due_at':
                value=parse_due(value)
                if value is None or timezone.is_naive(value) or value<=timezone.now():
                    raise ValidationError({'due_at':'Hạn nộp không hợp lệ.'})
            elif key=='allow_late' and type(value) is not bool:
                raise ValidationError({'allow_late':'Giá trị boolean.'})
            setattr(task,key,value)
        task.save();self.audit(action='HOMEWORK_UPDATED',instance=task)
        return Response(task_json(task,self))


def guardian_student_class(view,task):
    return any(guardian(view,s) for s in Student.objects.filter(
        tenant=view.tenant,enrollments__in=enrollments(view.tenant,classroom=task.classroom)).distinct())


def self_student_class(view,task):
    return StudentAccount.objects.filter(tenant=view.tenant,account=view.request.user,
        student__enrollments__in=enrollments(view.tenant,classroom=task.classroom)).exists() and 'STUDENT' in view.roles


class HomeworkTransition(TenantAPIView):
    @transaction.atomic
    def post(self,request,task_id,action):
        lock_school(self.tenant)
        task=get_object_or_404(HomeworkAssignment.objects.select_for_update().select_related('classroom','subject'),tenant=self.tenant,id=task_id)
        if not owner_or_assigned(self,task): raise PermissionDenied()
        desired={'publish':'PUBLISHED','close':'CLOSED'}.get(action)
        if not desired or not assignment_transition(task.state,desired):
            raise ValidationError({'detail':'Chuyển trạng thái không hợp lệ.'})
        if action=='publish':
            if task.due_at<=timezone.now(): raise ValidationError({'detail':'Hạn nộp phải sau thời điểm công bố.'})
            task.published_at=timezone.now()
        else: task.closed_at=timezone.now()
        task.state=desired;task.save()
        self.audit(action=f'HOMEWORK_{desired}',instance=task)
        return Response(task_json(task,self))


class StudentHomework(TenantAPIView):
    def get(self,request,student_id):
        student=get_object_or_404(Student,tenant=self.tenant,id=student_id,is_active=True)
        teacher_roles=({'SUBJECT_TEACHER','HOMEROOM_TEACHER','DEPARTMENT_HEAD'} & self.roles)
        is_guardian=guardian(self,student); is_self=self_student(self,student)
        if not (ADMIN & self.roles or teacher_roles or is_guardian or is_self): raise NotFound()
        valid_class_ids=list(enrollments(self.tenant,student=student).values_list('classroom_id',flat=True))
        qs=HomeworkAssignment.objects.filter(tenant=self.tenant,classroom_id__in=valid_class_ids,
            state__in=['PUBLISHED','CLOSED']).select_related('classroom','subject')
        if teacher_roles and not (ADMIN & self.roles or is_guardian or is_self):
            ids=assigned_scope(self).values('id')
            qs=qs.filter(id__in=ids)
        if not (ADMIN & self.roles or is_guardian or is_self or qs.exists()): raise NotFound()
        entries={s.assignment_id:s for s in HomeworkSubmission.objects.filter(tenant=self.tenant,student=student,
            assignment__in=qs)}
        now=timezone.now()
        results=[]
        for task in qs.order_by('due_at')[:150]:
            sub=entries.get(task.id)
            results.append({'assignment':task_json(task,self),'status':submission_status(
                state=sub.state if sub else None,due_at=task.due_at,now=now),
                'submission':submission_json(sub,detail=is_self or bool(ADMIN & self.roles) or subject_reader(self,task)) if sub else None})
        return Response({'student_id':str(student.id),'student_name':student.full_name,'items':results})


class MySubmission(TenantAPIView):
    def get_student(self,task):
        if 'STUDENT' not in self.roles: raise PermissionDenied('Chỉ tài khoản học sinh được nộp bài.')
        student=Student.objects.filter(tenant=self.tenant,studentaccount__tenant=self.tenant,
            studentaccount__account=self.request.user,is_active=True,
            enrollments__in=enrollments(self.tenant,classroom=task.classroom)).first()
        if not student: raise NotFound()
        return student

    def get(self,request,task_id):
        task=get_object_or_404(HomeworkAssignment,tenant=self.tenant,id=task_id,state__in=['PUBLISHED','CLOSED'])
        student=self.get_student(task)
        sub=HomeworkSubmission.objects.filter(tenant=self.tenant,assignment=task,student=student).first()
        return Response({'assignment':task_json(task,self),'submission':submission_json(sub)})

    @transaction.atomic
    def put(self,request,task_id):
        lock_school(self.tenant)
        task=get_object_or_404(HomeworkAssignment,tenant=self.tenant,id=task_id,state__in=['PUBLISHED','CLOSED'])
        student=self.get_student(task)
        validate_fields(request.data, {'action','content_text','expected_version'})
        action=request.data.get('action','submit')
        if action not in ('save','submit'): raise ValidationError({'action':'Chỉ nhận save hoặc submit.'})
        content=request.data.get('content_text','')
        if not isinstance(content,str) or len(content)>20000:
            raise ValidationError({'content_text':'Nội dung phải là văn bản tối đa 20.000 ký tự.'})
        if action=='submit' and not content.strip(): raise ValidationError({'content_text':'Không thể nộp bài trống.'})
        now=timezone.now()
        existing=HomeworkSubmission.objects.select_for_update().filter(tenant=self.tenant,
            assignment=task,student=student).first()
        if not can_submit(assignment_state=task.state,deadline=task.due_at,now=now,
                          allow_late=task.allow_late,submission_state=existing.state if existing else None):
            raise ValidationError({'detail':'Bài tập đã đóng/hết hạn hoặc đã trả kết quả.'})
        expected=version_value(request.data.get('expected_version',0))
        current=existing.version if existing else 0
        if expected!=current:
            return Response({'detail':'Bài nộp đã thay đổi; tải lại dữ liệu.','version':current},status=409)
        if existing and existing.state=='SUBMITTED' and action=='save':
            raise ValidationError({'detail':'Bài đã nộp: dùng Nộp lại để cập nhật, không chuyển về nháp.'})
        if existing:
            existing.version+=1;sub=existing
        else:
            sub=HomeworkSubmission(tenant=self.tenant,assignment=task,student=student)
        sub.content_text=content
        if action=='submit': sub.state='SUBMITTED';sub.submitted_at=now
        else: sub.state='DRAFT';sub.submitted_at=None
        sub.save();self.audit(action='HOMEWORK_SUBMITTED' if action=='submit' else 'HOMEWORK_SAVED',instance=sub)
        return Response(submission_json(sub),status=status.HTTP_200_OK)


class HomeworkRoster(TenantAPIView):
    def get(self,request,task_id):
        task=get_object_or_404(HomeworkAssignment.objects.select_related('classroom','subject'),tenant=self.tenant,id=task_id)
        teacher=subject_reader(self,task)
        homeroom=('HOMEROOM_TEACHER' in self.roles and teach(self,task,kind='HOMEROOM'))
        if not (teacher or homeroom or ADMIN & self.roles): raise NotFound()
        if not owner_or_assigned(self,task) and not ADMIN & self.roles and task.state=='DRAFT': raise NotFound()
        students=Student.objects.filter(tenant=self.tenant,is_active=True,
            enrollments__in=enrollments(self.tenant,classroom=task.classroom)).distinct().order_by('student_code')
        rows={s.student_id:s for s in HomeworkSubmission.objects.filter(tenant=self.tenant,assignment=task)}
        now=timezone.now()
        return Response({'assignment':task_json(task,self),'students':[
            {'student_id':str(stu.id),'student_code':stu.student_code,'full_name':stu.full_name,
             'status':submission_status(state=rows[stu.id].state if stu.id in rows else None,
                 due_at=task.due_at,now=now),
             'submission':submission_json(rows.get(stu.id),detail=teacher or bool(ADMIN & self.roles))}
            for stu in students]})


class ReturnHomework(TenantAPIView):
    @transaction.atomic
    def post(self,request,submission_id):
        lock_school(self.tenant)
        sub=get_object_or_404(HomeworkSubmission.objects.select_for_update().select_related('assignment'),
                              tenant=self.tenant,id=submission_id)
        task=sub.assignment
        if not owner_or_assigned(self,task): raise PermissionDenied()
        validate_fields(request.data, {'feedback','score','expected_version'})
        if not enrollments(self.tenant,student=sub.student,classroom=task.classroom).exists(): raise NotFound()
        if version_value(request.data.get('expected_version'))!=sub.version:
            return Response({'detail':'Bài nộp đã thay đổi; tải lại trước khi trả bài.','version':sub.version},status=409)
        if not can_mark(sub.state): raise ValidationError({'detail':'Chỉ chấm bài đang ở trạng thái SUBMITTED.'})
        feedback=request.data.get('feedback','')
        if not isinstance(feedback,str) or len(feedback)>3000: raise ValidationError({'feedback':'Nhận xét tối đa 3.000 ký tự.'})
        try: score=parse_feedback_score(request.data.get('score'))
        except ValueError as exc: raise ValidationError({'score':str(exc)})
        if score is None and not feedback.strip(): raise ValidationError({'detail':'Cần có điểm hoặc nhận xét.'})
        sub.feedback=feedback.strip();sub.score=score;sub.reviewed_by=request.user
        sub.state='RETURNED';sub.returned_at=timezone.now();sub.version+=1;sub.save()
        self.audit(action='HOMEWORK_RETURNED',instance=sub)
        ids=set(StudentAccount.objects.filter(tenant=self.tenant,student=sub.student).values_list('account_id',flat=True))
        today=timezone.localdate()
        ids.update(GuardianLink.objects.filter(tenant=self.tenant,student=sub.student,is_active=True,
            is_verified=True,can_view_academic=True,valid_from__lte=today).filter(
            Q(valid_to__isnull=True)|Q(valid_to__gte=today)).values_list('guardian_id',flat=True))
        from apps.identity.models import Account
        for account in Account.objects.filter(id__in=ids):
            notify(self.tenant,account,'HOMEWORK_RETURNED',sub.id,
                   f'homework-returned:{sub.id}:{account.id}',{'assignment_id':str(task.id),'student_id':str(sub.student_id)})
        return Response(submission_json(sub))
