"""Read existing source tables; never persist a second student profile."""
from datetime import timedelta
from django.db.models import Q,OuterRef,Subquery,Case,When,Value,CharField,BooleanField,IntegerField,Count
from django.utils import timezone
from apps.communications.policy import active_enrollments,notice_allowed,event_allowed
from apps.attendance.models import AttendanceRecord,NotificationOutbox
from apps.communications.models import Announcement,AnnouncementRecipient,AnnouncementRead,NotificationReceipt
from apps.grades.models import GradeEntry
from apps.homework.models import HomeworkAssignment,HomeworkSubmission
from .rules import attendance_summary,digest_sentences,MAX_GRADES,MAX_HOMEWORK,MAX_NOTICES,MAX_EVENTS


def homework_data(tenant,student,class_id,now):
    own=HomeworkSubmission.objects.filter(tenant=tenant,student=student,assignment_id=OuterRef('pk'))
    tasks=HomeworkAssignment.objects.filter(tenant=tenant,classroom_id=class_id,subject__tenant=tenant,
        state__in=['PUBLISHED','CLOSED']).annotate(own_state=Subquery(own.values('state')[:1]))
    tasks=tasks.annotate(display_status=Case(
        When(own_state='RETURNED',then=Value('RETURNED')),When(own_state='SUBMITTED',then=Value('SUBMITTED')),
        When(due_at__lt=now,then=Value('OVERDUE')),When(own_state='DRAFT',then=Value('IN_PROGRESS')),
        default=Value('NOT_SUBMITTED'),output_field=CharField()))
    tasks=tasks.annotate(actionable=Case(When(
        Q(state='PUBLISHED') & (Q(due_at__gte=now)|Q(allow_late=True)) & Q(display_status__in=['OVERDUE','NOT_SUBMITTED','IN_PROGRESS']),
        then=Value(True)),default=Value(False),output_field=BooleanField()))
    summary=tasks.aggregate(total=Count('pk'),submitted_or_returned=Count('pk',filter=Q(display_status__in=['SUBMITTED','RETURNED'])),
        overdue=Count('pk',filter=Q(display_status='OVERDUE')),pending_action=Count('pk',filter=Q(actionable=True)))
    rows=tasks.annotate(priority=Case(When(actionable=True,display_status='OVERDUE',then=Value(0)),
        When(actionable=True,then=Value(1)),When(display_status='OVERDUE',then=Value(2)),default=Value(3),output_field=IntegerField()))
    rows=rows.select_related('subject').order_by('priority','due_at','id')[:MAX_HOMEWORK]
    items=[{'id':str(t.id),'title':t.title,'subject':t.subject.name,'due_at':t.due_at.isoformat(),
        'status':t.display_status,'assignment_state':t.state,'actionable':t.actionable,'allow_late':t.allow_late,
        'feedback_available':t.own_state=='RETURNED'} for t in rows]
    return {'summary':summary,'items':items,'limited_to':MAX_HOMEWORK}


def build_student_dashboard(*,view,student):
    tenant=view.tenant;user=view.request.user;now=timezone.now();today=timezone.localdate(now);since=today-timedelta(days=29)
    # Multiple distinct current classes are a data-quality issue; do not guess the newest.
    classes=list(active_enrollments(tenant,student=student).order_by().values(
        'classroom_id','classroom__code','classroom__grade_level').distinct()[:2])
    enrollment_status='CURRENT' if len(classes)==1 else 'AMBIGUOUS' if classes else 'NONE'
    current=classes[0] if len(classes)==1 else None
    class_id=current['classroom_id'] if current else None
    class_info={'id':str(class_id),'code':current['classroom__code'],'grade_level':current['classroom__grade_level']} if current else None
    marks=list(AttendanceRecord.objects.filter(tenant=tenant,student=student,session__tenant=tenant,
        session__classroom_id=class_id,session__state__in=['SUBMITTED','LOCKED'],
        session__attendance_date__range=(since,today)).values_list('mark',flat=True)) if current else []
    grade_rows=GradeEntry.objects.filter(tenant=tenant,student=student,assessment__tenant=tenant,
        assessment__state='PUBLISHED',assessment__book__tenant=tenant,assessment__book__subject__tenant=tenant,
        assessment__book__classroom_id=class_id).select_related('assessment__book__subject').order_by(
            '-assessment__published_at','-updated_at','id')[:MAX_GRADES] if current else []
    grades=[{'assessment_id':str(g.assessment_id),'subject':g.assessment.book.subject.name,'title':g.assessment.title,
        'semester':g.assessment.book.semester,'kind':g.assessment.kind,'score':str(g.score) if g.score is not None else None,
        'result':g.result or None,'note':g.note,'published_at':g.assessment.published_at.isoformat() if g.assessment.published_at else None} for g in grade_rows]
    homework=homework_data(tenant,student,class_id,now) if current else {
        'summary':{'total':0,'submitted_or_returned':0,'overdue':0,'pending_action':0},'items':[],'limited_to':MAX_HOMEWORK}
    notices=[]
    if current:
        audience=AnnouncementRecipient.objects.filter(tenant=tenant,account=user).values('announcement_id')
        scope=Q(scope='SCHOOL')|Q(scope='GRADE',grade_level=current['classroom__grade_level'])|Q(scope='CLASS',classroom_id=class_id)
        candidates=Announcement.objects.filter(tenant=tenant,state='PUBLISHED',id__in=audience).filter(scope).order_by('-published_at','id')[:100]
        for notice in candidates:
            if notice_allowed(view,notice):notices.append(notice)
            if len(notices)==MAX_NOTICES:break
    reads=set(AnnouncementRead.objects.filter(tenant=tenant,account=user,announcement__in=notices).values_list('announcement_id',flat=True))
    events=[]
    for event in NotificationOutbox.objects.filter(tenant=tenant,recipient=user).order_by('-created_at','id')[:300]:
        if event_allowed(view,event):events.append(event)
        if len(events)==MAX_EVENTS:break
    receipts=set(NotificationReceipt.objects.filter(tenant=tenant,recipient=user,event__in=events).values_list('event_id',flat=True))
    return {
        'student':{'id':str(student.id),'full_name':student.full_name,'student_code':student.student_code,'classroom':class_info},
        'enrollment_status':enrollment_status,'as_of':now.isoformat(),
        'attendance':{'window_days':30,'from_date':since.isoformat(),'through_date':today.isoformat(),**attendance_summary(marks)},
        'grades':{'items':grades,'limited_to':MAX_GRADES,'released_only':True},'homework':homework,
        'announcements':[{'id':str(n.id),'title':n.title,'scope':n.scope,'published_at':n.published_at.isoformat() if n.published_at else None,'read':n.id in reads} for n in notices],
        'notifications':{'scope':'ACCOUNT','items':[{'id':str(e.id),'event_type':e.event_type,'created_at':e.created_at.isoformat(),'read':e.id in receipts} for e in events]},
        'data_limits':['Chỉ lớp đang ghi danh trong năm học hiện tại; không tổng hợp lớp cũ.',
            'Điểm danh 30 ngày đã nộp/khóa; ngày trống không được coi là có mặt.',
            'Tối đa 8 kết quả gần đây; không tự tính trung bình học kỳ.',
            'Tối đa 8 bài tập ưu tiên; số tổng hợp tính tất cả bài đã công bố, kể cả bài đã đóng.',
            'Tối đa 5 thông báo đúng phạm vi con; 5 sự kiện tài khoản có thể liên quan nhiều con.',
            'Làm mới để xem thay đổi; không gửi dữ liệu sang nhà cung cấp AI.'],
    }


def build_ai_preview(snapshot):
    return {'enabled':False,'mode':'RULE_BASED_PREVIEW','model_called':False,'exported_to_provider':False,
        'human_review_required':True,'enrollment_status':snapshot['enrollment_status'],
        'sentences':digest_sentences(attendance=snapshot['attendance'],homework=snapshot['homework']['summary'],
            published_grade_count=len(snapshot['grades']['items'])),
        'limitations':['Tóm tắt theo quy tắc, không phải đánh giá năng lực hay chẩn đoán.',
            'Chỉ phạm vi lớp hiện tại và danh sách có giới hạn; cần đối chiếu dữ liệu gốc.']}
