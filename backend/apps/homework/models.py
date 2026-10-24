import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.schools.models import Tenant
from apps.academics.models import Classroom, Subject, Student


class HomeworkAssignment(models.Model):
    class State(models.TextChoices):
        DRAFT = 'DRAFT', 'Nháp'
        PUBLISHED = 'PUBLISHED', 'Đã giao'
        CLOSED = 'CLOSED', 'Đã đóng'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    classroom = models.ForeignKey(Classroom, on_delete=models.PROTECT)
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    title = models.CharField(max_length=160)
    instructions = models.TextField(max_length=10000)
    due_at = models.DateTimeField()
    allow_late = models.BooleanField(default=False)
    state = models.CharField(max_length=12, choices=State.choices, default=State.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['tenant', 'classroom', 'state', 'due_at'])]
        constraints = [models.CheckConstraint(condition=~Q(title=''), name='ck_homework_title_nonempty')]


class HomeworkSubmission(models.Model):
    class State(models.TextChoices):
        DRAFT = 'DRAFT', 'Nháp học sinh'
        SUBMITTED = 'SUBMITTED', 'Đã nộp'
        RETURNED = 'RETURNED', 'Đã trả bài'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    assignment = models.ForeignKey(HomeworkAssignment, on_delete=models.PROTECT, related_name='submissions')
    student = models.ForeignKey(Student, on_delete=models.PROTECT)
    content_text = models.TextField(max_length=20000)
    state = models.CharField(max_length=12, choices=State.choices, default=State.DRAFT)
    version = models.PositiveIntegerField(default=1)
    submitted_at = models.DateTimeField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    feedback = models.TextField(max_length=3000, blank=True)
    score = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     related_name='+', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['assignment', 'student'], name='uq_homework_student_assignment'),
            models.CheckConstraint(condition=Q(score__isnull=True) | (Q(score__gte=0) & Q(score__lte=10)),
                                   name='ck_homework_feedback_score'),
        ]
        indexes = [models.Index(fields=['tenant', 'student', 'state'])]
