"""Sprint 5 communication domain. Each record belongs to exactly one tenant.

This prototype intentionally supports *text only*, no public attachments, no real-time
sockets, no outbound push, and no user-to-user open directory.
"""
import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.db.models import Q
from apps.schools.models import Tenant
from apps.academics.models import Student, Classroom
from apps.attendance.models import NotificationOutbox

class Announcement(models.Model):
    class Scope(models.TextChoices):
        SCHOOL = 'SCHOOL'
        GRADE = 'GRADE'
        CLASS = 'CLASS'
    class State(models.TextChoices):
        DRAFT = 'DRAFT'
        PUBLISHED = 'PUBLISHED'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    scope = models.CharField(max_length=10, choices=Scope.choices)
    classroom = models.ForeignKey(Classroom, on_delete=models.PROTECT, null=True, blank=True)
    grade_level = models.PositiveSmallIntegerField(null=True, blank=True)
    title = models.CharField(max_length=180)
    body = models.TextField(max_length=12000)
    state = models.CharField(max_length=12, choices=State.choices, default=State.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        indexes = [models.Index(fields=['tenant','state','published_at'])]
        constraints = [models.CheckConstraint(name='ck_announcement_scope_target', condition=(
            Q(scope='SCHOOL', classroom__isnull=True, grade_level__isnull=True) |
            Q(scope='GRADE', classroom__isnull=True, grade_level__isnull=False) |
            Q(scope='CLASS', classroom__isnull=False, grade_level__isnull=True)))]

class AnnouncementRecipient(models.Model):
    """Snapshot of audience at publication; current permissions are rechecked on read."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    announcement = models.ForeignKey(Announcement, on_delete=models.PROTECT)
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['announcement','account'],name='uq_notice_recipient')]

class AnnouncementRead(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    announcement = models.ForeignKey(Announcement, on_delete=models.PROTECT)
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    read_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['announcement','account'], name='uq_announcement_read')]

class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    student = models.ForeignKey(Student, on_delete=models.PROTECT)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    guardian = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['tenant','student','teacher','guardian'],name='uq_parent_teacher_thread')]
        indexes = [models.Index(fields=['tenant','teacher','updated_at']),models.Index(fields=['tenant','guardian','updated_at'])]

class ConversationMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    conversation = models.ForeignKey(Conversation, on_delete=models.PROTECT, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField(max_length=5000)
    client_key = models.CharField(max_length=72)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['conversation','sender','client_key'],name='uq_conversation_message_key')]
        indexes = [models.Index(fields=['tenant','conversation','created_at'])]

class ConversationRead(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    conversation = models.ForeignKey(Conversation, on_delete=models.PROTECT)
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    read_at = models.DateTimeField(default=timezone.now)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['conversation','account'],name='uq_conversation_read')]

class SupportTicket(models.Model):
    class State(models.TextChoices):
        OPEN = 'OPEN'
        IN_PROGRESS = 'IN_PROGRESS'
        RESOLVED = 'RESOLVED'
        CLOSED = 'CLOSED'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    student = models.ForeignKey(Student, on_delete=models.PROTECT, null=True, blank=True)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    version = models.PositiveIntegerField(default=1)
    category = models.CharField(max_length=32)
    subject = models.CharField(max_length=180)
    details = models.TextField(max_length=5000)
    state = models.CharField(max_length=16, choices=State.choices, default=State.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        indexes = [models.Index(fields=['tenant','state','updated_at']),models.Index(fields=['tenant','requester'])]

class TicketReply(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    ticket = models.ForeignKey(SupportTicket, on_delete=models.PROTECT, related_name='replies')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField(max_length=5000)
    created_at = models.DateTimeField(auto_now_add=True)

class NotificationReceipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    event = models.ForeignKey(NotificationOutbox, on_delete=models.PROTECT)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    read_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['event','recipient'], name='uq_notification_receipt')]
