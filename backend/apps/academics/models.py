import uuid
from django.conf import settings
from django.db import models
from apps.schools.models import Tenant

class AcademicYear(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    label = models.CharField(max_length=30)
    starts_on = models.DateField()
    ends_on = models.DateField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['tenant','label'], name='uq_year_tenant_label')]

class Subject(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=150)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['tenant','code'], name='uq_subject_tenant_code')]

class Classroom(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT)
    code = models.CharField(max_length=40)
    grade_level = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['tenant','year','code'], name='uq_class_tenant_year_code')]

class Student(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    student_code = models.CharField(max_length=40)
    full_name = models.CharField(max_length=200)
    date_of_birth = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['tenant','student_code'], name='uq_student_tenant_code')]

class Enrollment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='enrollments')
    classroom = models.ForeignKey(Classroom, on_delete=models.PROTECT, related_name='enrollments')
    starts_on = models.DateField()
    ends_on = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

class TeacherAssignment(models.Model):
    class Kind(models.TextChoices):
        HOMEROOM = 'HOMEROOM'
        SUBJECT = 'SUBJECT'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    classroom = models.ForeignKey(Classroom, on_delete=models.PROTECT, related_name='teacher_assignments')
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, null=True, blank=True)
    kind = models.CharField(max_length=12, choices=Kind.choices)
    starts_on = models.DateField()
    ends_on = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=(models.Q(kind='HOMEROOM', subject__isnull=True) | models.Q(kind='SUBJECT',subject__isnull=False)),
            name='ck_assignment_role_subject')]
        indexes = [models.Index(fields=['tenant','teacher','is_active','starts_on','ends_on'])]

class GuardianLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='guardians')
    guardian = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    relation = models.CharField(max_length=40)
    is_verified = models.BooleanField(default=False)
    can_view_academic = models.BooleanField(default=True)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+', null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['tenant','guardian','is_verified','is_active'])]

class StudentAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    student = models.ForeignKey(Student, on_delete=models.PROTECT)
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['tenant','student'], name='uq_student_account')]
