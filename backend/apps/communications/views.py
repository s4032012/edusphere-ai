"""Sprint 5 tenant-scoped API. All relationship authorization is server-side.

Important: check live guardian/teacher links on EVERY conversation request; the
thread identifier and the UI are NEVER sufficient authorization.
"""
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from apps.access.views import TenantAPIView
from apps.access.scopes import active_roles
from apps.academics.models import (Classroom, Student, Enrollment, GuardianLink,
                                   TeacherAssignment, StudentAccount)
from apps.schools.models import Membership
from apps.attendance.models import NotificationOutbox
from .models import (Announcement, AnnouncementRecipient, AnnouncementRead, Conversation, ConversationMessage,
                     ConversationRead, SupportTicket, TicketReply, NotificationReceipt)
from .rules import STAFF, NOTICE_BROADCAST, validate_body, validate_key, valid_notice, valid_ticket_transition


def fail_value(value, max_length=5000, field='body'):
    try: return validate_body(value,max_length,field)
    except ValueError as e: raise ValidationError({field:str(e)})


def utc_now(): return timezone.now()


from .policy import (active_enrollments, active_members, assigned_teacher, verified_guardian,
    announcement_recipients, can_publish, thread_authorized, notice_allowed, ticket_allowed, event_allowed, teacher_assignments)
from apps.attendance.views import lock_school
from rest_framework.throttling import UserRateThrottle
from rest_framework.exceptions import APIException
from uuid import UUID

class CommunicationThrottle(UserRateThrottle):
    rate='120/min'
    def get_cache_key(self,request,view):
        return 'comms:%s:%s' % (request.user.pk,request.headers.get('X-Tenant-ID',''))

class CommsView(TenantAPIView):
    throttle_classes=[CommunicationThrottle]
    def write(self,request,fields):
        lock_school(self.tenant)
        self.roles=active_roles(request.user,self.tenant)
        if not self.roles:raise PermissionDenied()
        if not isinstance(request.data,dict) or set(request.data)-set(fields):
            raise ValidationError({'detail':'JSON object chứa trường không hợp lệ.'})

def identifier(value,field):
    try:
        if not isinstance(value,str):raise ValueError()
        return UUID(value)
    except (ValueError,TypeError,AttributeError):raise ValidationError({field:'Cần UUID hợp lệ.'})

class Conflict(APIException):
    status_code=409
    default_detail='Phiếu đã thay đổi. Làm mới trước khi cập nhật.'

def notice_json(item,read=False,view=None):
    return {'id':str(item.id),'scope':item.scope,'classroom_id':str(item.classroom_id) if item.classroom_id else None,
        'grade_level':item.grade_level,'title':item.title,'body':item.body,'state':item.state,
        'created_at':item.created_at.isoformat(), 'published_at':item.published_at.isoformat() if item.published_at else None,
        'read':read,'can_publish': bool(view and item.state=='DRAFT' and can_publish(view,item)),
        'recipient_count':AnnouncementRecipient.objects.filter(announcement=item).count() if view and can_publish(view,item) else None,
        'read_count':AnnouncementRead.objects.filter(announcement=item).count() if view and can_publish(view,item) else None}


def notify(tenant, recipient, event_type, subject_id, suffix='',payload=None):
    key=f'comms:{tenant.id}:{event_type}:{subject_id}:{recipient.id}:{suffix}'
    NotificationOutbox.objects.get_or_create(dedupe_key=key,defaults={
        'tenant':tenant,'recipient':recipient,'event_type':event_type,
        'subject_id':subject_id,'payload':payload or {},'state':'QUEUED'})


class AnnouncementList(CommsView):
    def get(self,request):
        items=[]
        qs=Announcement.objects.filter(tenant=self.tenant).select_related('classroom','author').order_by('-created_at')[:300]
        # Pilot bounded read; policy must be checked on each item, not only by role.
        for obj in qs:
            if obj.state=='DRAFT':
                if not can_publish(self,obj):continue
            elif (not AnnouncementRecipient.objects.filter(tenant=self.tenant,announcement=obj,account=request.user).exists()
                  or request.user.id not in announcement_recipients(self,obj)):continue
            read=AnnouncementRead.objects.filter(tenant=self.tenant,announcement=obj,account=request.user).exists()
            items.append(notice_json(obj,read,self))
            if len(items)>=100:break
        return Response(items)

    @transaction.atomic
    def post(self,request):
        self.write(request,{'scope','classroom_id','grade_level','title','body'})
        scope=request.data.get('scope','')
        class_id=request.data.get('classroom_id')
        grade=request.data.get('grade_level')
        if not valid_notice(scope,class_id,grade):raise ValidationError({'scope':'Scope/target không hợp lệ (THCS 6–9).'})
        classroom=None
        if scope=='CLASS':classroom=get_object_or_404(Classroom,tenant=self.tenant,id=identifier(class_id,'classroom_id'))
        draft=Announcement(tenant=self.tenant,author=request.user,scope=scope,classroom=classroom,
            grade_level=grade,title=fail_value(request.data.get('title'),180,'title'),
            body=fail_value(request.data.get('body'),12000))
        if not can_publish(self,draft):raise PermissionDenied('Chỉ GVCN lớp hoặc người được ủy quyền mới tạo thông báo.')
        draft.save();self.audit(action='NOTICE_DRAFT_CREATED',instance=draft)
        return Response(notice_json(draft,view=self),status=status.HTTP_201_CREATED)


class AnnouncementPublish(CommsView):
    @transaction.atomic
    def post(self,request,notice_id):
        self.write(request,set())
        notice=get_object_or_404(Announcement.objects.select_for_update(),tenant=self.tenant,id=notice_id)
        if not can_publish(self,notice):raise PermissionDenied()
        if notice.state!='DRAFT':raise ValidationError({'detail':'Thông báo đã công bố.'})
        recipients=announcement_recipients(self,notice)
        if len(recipients)>2500:raise ValidationError({'detail':'Pilot giới hạn 2500 người nhận mỗi thông báo.'})
        notice.state='PUBLISHED';notice.published_at=utc_now();notice.save()
        from apps.identity.models import Account
        for user in Account.objects.filter(pk__in=recipients):
            AnnouncementRecipient.objects.get_or_create(tenant=self.tenant,announcement=notice,account=user)
            notify(self.tenant,user,'ANNOUNCEMENT_PUBLISHED',notice.id,payload={'notice_id':str(notice.id)})
        self.audit(action='NOTICE_PUBLISHED',instance=notice)
        return Response({'id':str(notice.id),'state':notice.state,'recipients':len(recipients)})


class AnnouncementReadView(CommsView):
    @transaction.atomic
    def post(self,request,notice_id):
        self.write(request,set())
        obj=get_object_or_404(Announcement,tenant=self.tenant,id=notice_id,state='PUBLISHED')
        if (not AnnouncementRecipient.objects.filter(tenant=self.tenant,announcement=obj,account=request.user).exists()
                or request.user.id not in announcement_recipients(self,obj)):raise NotFound()
        AnnouncementRead.objects.get_or_create(tenant=self.tenant,announcement=obj,account=request.user)
        return Response({'read':True})


def thread_json(obj,view):
    receipt=ConversationRead.objects.filter(tenant=view.tenant,conversation=obj,account=view.request.user).first()
    unread=obj.messages.exclude(sender=view.request.user)
    if receipt:unread=unread.filter(created_at__gt=receipt.read_at)
    return {'id':str(obj.id),'student_id':str(obj.student_id),'student_name':obj.student.full_name,
        'teacher_id':str(obj.teacher_id),'teacher_name':obj.teacher.display_name or obj.teacher.username,
        'guardian_id':str(obj.guardian_id),'guardian_name':obj.guardian.display_name or obj.guardian.username,
        'updated_at':obj.updated_at.isoformat(),'unread_count':unread.count()}


def message_json(obj):
    return {'id':str(obj.id),'sender_id':str(obj.sender_id),'body':obj.body,
        'created_at':obj.created_at.isoformat()}


class ConversationList(CommsView):
    def get(self,request):
        qs=Conversation.objects.filter(tenant=self.tenant).filter(Q(guardian=request.user)|Q(teacher=request.user)).select_related(
            'student','teacher','guardian').order_by('-updated_at')[:100]
        return Response([thread_json(c,self) for c in qs if thread_authorized(self,c)])

    @transaction.atomic
    def post(self,request):
        self.write(request,{'student_id','teacher_id','guardian_id'})
        student=get_object_or_404(Student,tenant=self.tenant,id=identifier(request.data.get('student_id'),'student_id'),is_active=True)
        from apps.identity.models import Account
        teacher=get_object_or_404(Account,id=identifier(request.data.get('teacher_id'),'teacher_id'),is_active=True)
        guardian=get_object_or_404(Account,id=identifier(request.data.get('guardian_id'),'guardian_id'),is_active=True)
        if teacher.id==guardian.id:raise ValidationError({'guardian_id':'Hai bên phải khác tài khoản.'})
        if request.user.id not in (teacher.id,guardian.id):raise PermissionDenied()
        if not verified_guardian(self.tenant,guardian,student) or not assigned_teacher(self.tenant,teacher,student):
            raise NotFound('Không có quan hệ đang được xác thực.')
        if request.user==guardian and 'PARENT' not in self.roles:raise PermissionDenied()
        if request.user==teacher and not (self.roles & {'SUBJECT_TEACHER','HOMEROOM_TEACHER','DEPARTMENT_HEAD'}):raise PermissionDenied()
        obj,created=Conversation.objects.get_or_create(tenant=self.tenant,student=student,teacher=teacher,
            guardian=guardian,defaults={'created_by':request.user})
        if created:self.audit(action='CONVERSATION_CREATED',instance=obj)
        return Response(thread_json(obj,self),status=status.HTTP_201_CREATED if created else 200)


class ConversationMessages(CommsView):
    def get_thread(self,thread_id):
        thread=get_object_or_404(Conversation.objects.select_related('student','guardian','teacher'),tenant=self.tenant,id=thread_id)
        if not thread_authorized(self,thread):raise NotFound()
        return thread

    def get(self,request,thread_id):
        thread=self.get_thread(thread_id)
        items=ConversationMessage.objects.filter(tenant=self.tenant,conversation=thread).order_by('-created_at','-id')[:100]
        return Response({'conversation':thread_json(thread,self),'messages':[message_json(m) for m in reversed(list(items))]})

    @transaction.atomic
    def post(self,request,thread_id):
        self.write(request,{'body','client_key'})
        thread=self.get_thread(thread_id)
        body=fail_value(request.data.get('body'))
        try:key=validate_key(request.data.get('client_key'))
        except ValueError as e:raise ValidationError({'client_key':str(e)})
        msg,created=ConversationMessage.objects.get_or_create(tenant=self.tenant,conversation=thread,
            sender=request.user,client_key=key,defaults={'body':body})
        if not created:
            if msg.body!=body:raise ValidationError({'client_key':'Khóa đã dùng với nội dung khác.'})
            return Response(message_json(msg))
        thread.save(update_fields=['updated_at'])
        other=thread.teacher if request.user.id==thread.guardian_id else thread.guardian
        notify(self.tenant,other,'MESSAGE_RECEIVED',msg.id,payload={'conversation_id':str(thread.id),'sender_id':str(request.user.id)})
        self.audit(action='MESSAGE_SENT',instance=msg)
        return Response(message_json(msg),status=status.HTTP_201_CREATED)


class ConversationMarkRead(ConversationMessages):
    @transaction.atomic
    def post(self,request,thread_id):
        self.write(request,{'last_message_id'})
        thread=self.get_thread(thread_id)
        if 'last_message_id' not in request.data:raise ValidationError({'last_message_id':'Cần tin nhắn cuối đã xem.'})
        if request.data['last_message_id'] is not None:
            message=get_object_or_404(ConversationMessage,tenant=self.tenant,conversation=thread,
                id=identifier(request.data['last_message_id'],'last_message_id'))
            receipt,created=ConversationRead.objects.get_or_create(tenant=self.tenant,conversation=thread,account=request.user,
                defaults={'read_at':message.created_at})
            if not created and receipt.read_at<message.created_at:
                receipt.read_at=message.created_at;receipt.save(update_fields=['read_at'])
        return Response({'read':True})



def ticket_json(t,include_details=False):
    item={'id':str(t.id),'version':t.version,'category':t.category,'subject':t.subject,'state':t.state,
        'student_id':str(t.student_id) if t.student_id else None,
        'requester_id':str(t.requester_id),'assignee_id':str(t.assignee_id) if t.assignee_id else None,
        'created_at':t.created_at.isoformat(),'updated_at':t.updated_at.isoformat()}
    if include_details:
        item['details']=t.details
        item['replies']=[{'id':str(r.id),'author_id':str(r.author_id),'body':r.body,
                          'created_at':r.created_at.isoformat()} for r in reversed(list(t.replies.order_by('-created_at','-id')[:150]))]
    return item


class TicketList(CommsView):
    def get(self,request):
        qs=SupportTicket.objects.filter(tenant=self.tenant)
        if not self.roles & STAFF:qs=qs.filter(requester=request.user) if 'PARENT' in self.roles else qs.none()
        return Response([ticket_json(t) for t in qs.select_related('student').order_by('-updated_at')[:100] if ticket_allowed(self,t)])

    @transaction.atomic
    def post(self,request):
        self.write(request,{'student_id','category','subject','details'})
        if 'PARENT' not in self.roles:raise PermissionDenied('Chỉ người giám hộ có quyền tạo yêu cầu.')
        student=None
        if request.data.get('student_id'):
            student=get_object_or_404(Student,tenant=self.tenant,id=identifier(request.data['student_id'],'student_id'),is_active=True)
            if not verified_guardian(self.tenant,request.user,student):raise NotFound()
        category=request.data.get('category','')
        if not isinstance(category,str):raise ValidationError({'category':'Cần chuỗi.'})
        if category not in {'ACCOUNT','ACADEMIC_RECORD','SCHEDULE','FEES','OTHER'}:
            raise ValidationError({'category':'Loại yêu cầu không hợp lệ.'})
        t=SupportTicket.objects.create(tenant=self.tenant,requester=request.user,student=student,
            category=category,subject=fail_value(request.data.get('subject'),180,'subject'),
            details=fail_value(request.data.get('details')))
        self.audit(action='TICKET_CREATED',instance=t)
        # Operational staff discover via scoped ticket queue; no multi-recipient blast of sensitive details.
        return Response(ticket_json(t,True),status=status.HTTP_201_CREATED)


class TicketDetail(CommsView):
    def get_ticket(self,ticket_id):
        ticket=get_object_or_404(SupportTicket,tenant=self.tenant,id=ticket_id)
        if not ticket_allowed(self,ticket):raise NotFound()
        return ticket

    def get(self,request,ticket_id):
        return Response(ticket_json(self.get_ticket(ticket_id),True))


class TicketReplyView(TicketDetail):
    @transaction.atomic
    def post(self,request,ticket_id):
        self.write(request,{'body'})
        ticket=self.get_ticket(ticket_id)
        if ticket.state=='CLOSED':raise ValidationError({'detail':'Ticket đã đóng.'})
        reply=TicketReply.objects.create(tenant=self.tenant,ticket=ticket,author=request.user,
            body=fail_value(request.data.get('body')))
        if self.roles & STAFF and not ticket.assignee_id:
            ticket.assignee=request.user
            if ticket.state=='OPEN':ticket.state='IN_PROGRESS'
        ticket.version+=1
        ticket.save()
        if request.user.id!=ticket.requester_id:
            notify(self.tenant,ticket.requester,'TICKET_REPLY',reply.id,payload={'ticket_id':str(ticket.id)})
        elif ticket.assignee_id:
            notify(self.tenant,ticket.assignee,'TICKET_REPLY',reply.id,payload={'ticket_id':str(ticket.id)})
        self.audit(action='TICKET_REPLIED',instance=reply)
        return Response(ticket_json(ticket,True),status=201)


class TicketTransition(TicketDetail):
    @transaction.atomic
    def post(self,request,ticket_id):
        self.write(request,{'state','expected_version'})
        ticket=get_object_or_404(SupportTicket.objects.select_for_update(),tenant=self.tenant,id=ticket_id)
        if not (self.roles & STAFF):raise PermissionDenied()
        if type(request.data.get('expected_version')) is not int:raise ValidationError({'expected_version':'Cần phiên bản hiện tại.'})
        if request.data['expected_version']!=ticket.version:raise Conflict()
        target=request.data.get('state','')
        if not isinstance(target,str):raise ValidationError({'state':'Cần chuỗi.'})
        if not valid_ticket_transition(ticket.state,target,True):raise ValidationError({'state':'Trạng thái không hợp lệ.'})
        ticket.state=target
        ticket.version+=1
        if target=='IN_PROGRESS' and not ticket.assignee_id:ticket.assignee=request.user
        ticket.save()
        notify(self.tenant,ticket.requester,'TICKET_STATUS',ticket.id,str(ticket.version),payload={'ticket_id':str(ticket.id),'state':target})
        self.audit(action='TICKET_'+target,instance=ticket)
        return Response(ticket_json(ticket,True))


class NotificationInbox(CommsView):
    def get(self,request):
        events=[e for e in NotificationOutbox.objects.filter(tenant=self.tenant,recipient=request.user).order_by('-created_at')[:300] if event_allowed(self,e)][:100]
        reads=set(NotificationReceipt.objects.filter(tenant=self.tenant,recipient=request.user,
            event_id__in=[e.id for e in events]).values_list('event_id',flat=True))
        return Response([{'id':str(e.id),'type':e.event_type,'payload':e.payload,
            'created_at':e.created_at.isoformat(),'read':e.id in reads,
            'delivery_state':e.state} for e in events])


class NotificationMarkRead(CommsView):
    @transaction.atomic
    def post(self,request,event_id):
        self.write(request,set())
        event=get_object_or_404(NotificationOutbox,tenant=self.tenant,id=event_id,recipient=request.user)
        if not event_allowed(self,event):raise NotFound()
        NotificationReceipt.objects.get_or_create(tenant=self.tenant,event=event,recipient=request.user)
        return Response({'read':True})

class StudentContacts(CommsView):
    """Contacts for ONE student; no directory and no unrelated school staff.
    A verified guardian may see active teachers; an assigned teacher may see
    verified guardians for that student. Staff use the independent ticket queue.
    """
    def get(self,request,student_id):
        student=get_object_or_404(Student,tenant=self.tenant,id=student_id,is_active=True)
        as_parent='PARENT' in self.roles and verified_guardian(self.tenant,request.user,student)
        as_teacher=bool(self.roles & {'HOMEROOM_TEACHER','SUBJECT_TEACHER','DEPARTMENT_HEAD'}) and assigned_teacher(
            self.tenant,request.user,student)
        if not(as_parent or as_teacher):raise NotFound()
        from apps.identity.models import Account
        teachers=Account.objects.filter(id__in=teacher_assignments(self.tenant).filter(
            classroom_id__in=active_enrollments(self.tenant,student=student).values('classroom_id')).values('teacher_id'))
        guardians=Account.objects.filter(id__in=GuardianLink.objects.filter(tenant=self.tenant,student=student).values('guardian_id'))
        return Response({'student_id':str(student.id),
            'teachers':[{'id':str(u.id),'name':u.display_name or u.username} for u in teachers if u.id!=request.user.id] if as_parent else [],
            'guardians':[{'id':str(u.id),'name':u.display_name or u.username} for u in guardians if u.id!=request.user.id and verified_guardian(self.tenant,u,student)] if as_teacher else []})
