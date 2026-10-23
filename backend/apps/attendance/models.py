import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q, F
from apps.schools.models import Tenant
from apps.academics.models import Classroom, Student, Enrollment

class AttendanceSession(models.Model):
    class State(models.TextChoices):
        DRAFT = 'DRAFT'
        SUBMITTED = 'SUBMITTED'
        LOCKED = 'LOCKED'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    classroom = models.ForeignKey(Classroom, on_delete=models.PROTECT)
    attendance_date = models.DateField()
    state = models.CharField(max_length=16, choices=State.choices, default=State.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    submitted_at = models.DateTimeField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['tenant','classroom','attendance_date'], name='uq_attendance_session_class_date')]
        indexes = [models.Index(fields=['tenant','attendance_date'])]

class AttendanceRecord(models.Model):
    class Mark(models.TextChoices):
        PRESENT = 'PRESENT'
        ABSENT = 'ABSENT'
        LATE = 'LATE'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    session = models.ForeignKey(AttendanceSession, on_delete=models.PROTECT, related_name='records')
    student = models.ForeignKey(Student, on_delete=models.PROTECT)
    mark = models.CharField(max_length=12, choices=Mark.choices)
    note = models.CharField(max_length=300, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['session','student'], name='uq_attendance_student_session')]
        indexes = [models.Index(fields=['tenant','student'])]

class LeaveRequest(models.Model):
    class State(models.TextChoices):
        PENDING = 'PENDING'
        APPROVED = 'APPROVED'
        REJECTED = 'REJECTED'
        WITHDRAWN = 'WITHDRAWN'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='leave_requests')
    guardian = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    from_date = models.DateField()
    through_date = models.DateField()
    reason = models.CharField(max_length=500)
    state = models.CharField(max_length=16, choices=State.choices, default=State.PENDING)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    decision_note = models.CharField(max_length=500, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(through_date__gte=F('from_date')), name='ck_leave_range')]
        indexes = [models.Index(fields=['tenant','student','state','from_date'])]

class NotificationOutbox(models.Model):
    """Durable intent to notify; no actual SMS/push service in Sprint 2."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    event_type = models.CharField(max_length=50)
    subject_id = models.UUIDField()
    dedupe_key = models.CharField(max_length=180, unique=True)
    payload = models.JSONField(default=dict)
    state = models.CharField(max_length=16, default='QUEUED')
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        indexes = [models.Index(fields=['tenant','recipient','state'])]
