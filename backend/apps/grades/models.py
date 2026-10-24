import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.academics.models import Classroom, Subject, Student
from apps.schools.models import Tenant


class GradeBook(models.Model):
    class Mode(models.TextChoices):
        SCORE = 'SCORE', 'Điểm'
        COMMENT = 'COMMENT', 'Nhận xét'
    class Semester(models.TextChoices):
        FIRST = '1', 'Học kỳ I'
        SECOND = '2', 'Học kỳ II'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    classroom = models.ForeignKey(Classroom, on_delete=models.PROTECT)
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT)
    semester = models.CharField(max_length=1, choices=Semester.choices)
    mode = models.CharField(max_length=8, choices=Mode.choices)
    regular_required = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tenant','classroom','subject','semester'], name='uq_gradebook_per_semester'),
            models.CheckConstraint(condition=Q(regular_required__gte=2) & Q(regular_required__lte=4), name='ck_gradebook_regular_count'),
        ]
        indexes = [models.Index(fields=['tenant','classroom','semester'])]


class Assessment(models.Model):
    class Kind(models.TextChoices):
        REGULAR = 'TX', 'Thường xuyên'
        MIDTERM = 'GK', 'Giữa kỳ'
        FINAL = 'CK', 'Cuối kỳ'
    class State(models.TextChoices):
        DRAFT = 'DRAFT'
        LOCKED = 'LOCKED'
        PUBLISHED = 'PUBLISHED'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    book = models.ForeignKey(GradeBook, on_delete=models.PROTECT, related_name='assessments')
    kind = models.CharField(max_length=2, choices=Kind.choices)
    slot = models.PositiveSmallIntegerField(default=1)
    title = models.CharField(max_length=140)
    state = models.CharField(max_length=12, choices=State.choices, default=State.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    locked_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['book','kind','slot'], name='uq_assessment_kind_slot'),
            models.CheckConstraint(condition=Q(slot__gte=1) & Q(slot__lte=4), name='ck_assessment_slot_range')]
        indexes = [models.Index(fields=['tenant','book','state'])]


class GradeEntry(models.Model):
    class Result(models.TextChoices):
        PASS = 'PASS', 'Đạt'
        FAIL = 'FAIL', 'Chưa đạt'
        EXEMPT = 'EXEMPT', 'Miễn'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    assessment = models.ForeignKey(Assessment, on_delete=models.PROTECT, related_name='entries')
    student = models.ForeignKey(Student, on_delete=models.PROTECT)
    score = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    result = models.CharField(max_length=8, choices=Result.choices, blank=True)
    note = models.CharField(max_length=300, blank=True)
    version = models.PositiveIntegerField(default=1)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['assessment','student'], name='uq_grade_assessment_student'),
            models.CheckConstraint(condition=Q(score__isnull=True) | (Q(score__gte=0) & Q(score__lte=10)), name='ck_grade_score_range')]
        indexes = [models.Index(fields=['tenant','student'])]


class GradeRevision(models.Model):
    class State(models.TextChoices):
        PENDING = 'PENDING'
        APPROVED = 'APPROVED'
        REJECTED = 'REJECTED'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    entry = models.ForeignKey(GradeEntry, on_delete=models.PROTECT, related_name='revision_requests')
    from_version = models.PositiveIntegerField()
    old_score = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    old_result = models.CharField(max_length=8, blank=True)
    proposed_score = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    proposed_result = models.CharField(max_length=8, blank=True)
    reason = models.CharField(max_length=500)
    state = models.CharField(max_length=12, choices=State.choices, default=State.PENDING)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        indexes = [models.Index(fields=['tenant','state','created_at'])]
