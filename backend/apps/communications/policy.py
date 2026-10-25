"""Live, role-specific authorization; a receipt or outbox row never grants access."""
from django.db.models import Q
from django.utils import timezone
from apps.access.scopes import active_roles
from apps.academics.models import Enrollment, GuardianLink, TeacherAssignment, StudentAccount, Classroom
from apps.schools.models import Membership
from .rules import NOTICE_BROADCAST, STAFF

TEACHERS={'SUBJECT_TEACHER','HOMEROOM_TEACHER','DEPARTMENT_HEAD'}

def current_classes(tenant):
    today=timezone.localdate()
    return Classroom.objects.filter(tenant=tenant,year__tenant=tenant,year__starts_on__lte=today,year__ends_on__gte=today)

def active_enrollments(tenant, **kwargs):
    today=timezone.localdate()
    return Enrollment.objects.filter(tenant=tenant,is_active=True,student__is_active=True,student__tenant=tenant,
        classroom__in=current_classes(tenant),starts_on__lte=today).filter(**kwargs).filter(Q(ends_on__isnull=True)|Q(ends_on__gte=today))

def active_members(tenant):
    today=timezone.localdate()
    return Membership.objects.filter(tenant=tenant,account__is_active=True,is_active=True,valid_from__lte=today).filter(Q(valid_to__isnull=True)|Q(valid_to__gte=today))

def verified_guardian(tenant,guardian,student):
    today=timezone.localdate()
    return (guardian.is_active and student.is_active and student.tenant_id==tenant.id and
        'PARENT' in active_roles(guardian,tenant) and GuardianLink.objects.filter(tenant=tenant,guardian=guardian,student=student,
        is_verified=True,is_active=True,can_view_academic=True,valid_from__lte=today).filter(Q(valid_to__isnull=True)|Q(valid_to__gte=today)).exists())

def teacher_assignments(tenant):
    today=timezone.localdate(); members=active_members(tenant)
    return TeacherAssignment.objects.filter(tenant=tenant,teacher__is_active=True,classroom__in=current_classes(tenant),
        is_active=True,starts_on__lte=today).filter(Q(ends_on__isnull=True)|Q(ends_on__gte=today)).filter(
        Q(kind='HOMEROOM',teacher_id__in=members.filter(role='HOMEROOM_TEACHER').values('account_id'))|
        Q(kind='SUBJECT',subject__tenant=tenant,teacher_id__in=members.filter(role__in=['SUBJECT_TEACHER','DEPARTMENT_HEAD']).values('account_id')))

def assigned_teacher(tenant,teacher,student):
    return teacher_assignments(tenant).filter(teacher=teacher,classroom_id__in=active_enrollments(tenant,student=student).values('classroom_id')).exists()

def thread_authorized(view,thread):
    return (thread.tenant_id==view.tenant.id and view.request.user.id in (thread.teacher_id,thread.guardian_id)
        and verified_guardian(view.tenant,thread.guardian,thread.student) and assigned_teacher(view.tenant,thread.teacher,thread.student))

def announcement_recipients(view,notice):
    tenant=view.tenant;members=active_members(tenant);classes=current_classes(tenant)
    if notice.scope=='CLASS':classes=classes.filter(id=notice.classroom_id)
    elif notice.scope=='GRADE':classes=classes.filter(grade_level=notice.grade_level)
    students=active_enrollments(tenant,classroom__in=classes).values('student_id')
    today=timezone.localdate()
    guardians=GuardianLink.objects.filter(tenant=tenant,student_id__in=students,is_verified=True,is_active=True,
        can_view_academic=True,valid_from__lte=today).filter(Q(valid_to__isnull=True)|Q(valid_to__gte=today)).values('guardian_id')
    pupils=StudentAccount.objects.filter(tenant=tenant,student_id__in=students).values('account_id')
    teachers=teacher_assignments(tenant).filter(classroom__in=classes).values('teacher_id')
    ids=set(members.filter(role='PARENT',account_id__in=guardians).values_list('account_id',flat=True))
    ids.update(members.filter(role='STUDENT',account_id__in=pupils).values_list('account_id',flat=True))
    ids.update(members.filter(role__in=TEACHERS,account_id__in=teachers).values_list('account_id',flat=True))
    ids.update(members.filter(role__in=NOTICE_BROADCAST | ({'SUPPORT_STAFF'} if notice.scope=='SCHOOL' else set())).values_list('account_id',flat=True))
    return ids

def can_publish(view,notice):
    if notice.scope=='CLASS' and not current_classes(view.tenant).filter(id=notice.classroom_id).exists():return False
    if view.roles & NOTICE_BROADCAST:return True
    return (notice.scope=='CLASS' and notice.author_id==view.request.user.id and 'HOMEROOM_TEACHER' in view.roles
        and teacher_assignments(view.tenant).filter(teacher=view.request.user,classroom=notice.classroom,kind='HOMEROOM').exists())

def notice_allowed(view,notice):
    from .models import AnnouncementRecipient
    return (notice.state=='PUBLISHED' and AnnouncementRecipient.objects.filter(tenant=view.tenant,announcement=notice,account=view.request.user).exists()
        and view.request.user.id in announcement_recipients(view,notice))

def ticket_allowed(view,ticket):
    return bool(view.roles & STAFF) or (ticket.requester_id==view.request.user.id and 'PARENT' in view.roles
        and (not ticket.student_id or verified_guardian(view.tenant,view.request.user,ticket.student)))

def event_allowed(view,event):
    from .models import Announcement,ConversationMessage,SupportTicket,TicketReply
    if event.tenant_id!=view.tenant.id or event.recipient_id!=view.request.user.id:return False
    if event.event_type=='ANNOUNCEMENT_PUBLISHED':
        obj=Announcement.objects.filter(tenant=view.tenant,id=event.subject_id).first()
        return bool(obj and notice_allowed(view,obj))
    if event.event_type=='MESSAGE_RECEIVED':
        obj=ConversationMessage.objects.filter(tenant=view.tenant,id=event.subject_id).select_related('conversation__student','conversation__teacher','conversation__guardian').first()
        return bool(obj and thread_authorized(view,obj.conversation))
    if event.event_type in {'TICKET_REPLY','TICKET_STATUS'}:
        obj=(TicketReply.objects.filter(tenant=view.tenant,id=event.subject_id).select_related('ticket__student').first()
             if event.event_type=='TICKET_REPLY' else SupportTicket.objects.filter(tenant=view.tenant,id=event.subject_id).select_related('student').first())
        return bool(obj and ticket_allowed(view,obj.ticket if event.event_type=='TICKET_REPLY' else obj))
    if event.event_type=='HOMEWORK_RETURNED':
        from apps.homework.models import HomeworkSubmission
        from apps.homework.views import enrollments,guardian,self_student
        sub=HomeworkSubmission.objects.filter(tenant=view.tenant,id=event.subject_id,state='RETURNED').select_related('student','assignment').first()
        return bool(sub and enrollments(view.tenant,student=sub.student,classroom=sub.assignment.classroom).exists()
            and (guardian(view,sub.student) or self_student(view,sub.student)))
    if 'PARENT' not in view.roles:return False
    from apps.attendance.models import AttendanceRecord,LeaveRequest
    from apps.grades.models import GradeEntry,GradeRevision
    students=[]
    if event.event_type=='UNEXCUSED_ABSENCE':
        obj=AttendanceRecord.objects.filter(tenant=view.tenant,id=event.subject_id).select_related('student').first()
        students=[obj.student] if obj else []
    elif event.event_type=='LEAVE_DECIDED':
        obj=LeaveRequest.objects.filter(tenant=view.tenant,id=event.subject_id,guardian=view.request.user).select_related('student').first()
        students=[obj.student] if obj else []
    elif event.event_type in {'GRADE_PUBLISHED','GRADE_CORRECTED'}:
        entries=GradeEntry.objects.filter(tenant=view.tenant,assessment__state='PUBLISHED')
        if event.event_type=='GRADE_PUBLISHED':entries=entries.filter(assessment_id=event.subject_id)
        else:
            revision=GradeRevision.objects.filter(tenant=view.tenant,id=event.subject_id,state='APPROVED').first()
            entries=entries.filter(id=revision.entry_id) if revision else entries.none()
        students=[entry.student for entry in entries.select_related('student')]
    return any(verified_guardian(view.tenant,view.request.user,s) for s in students)
