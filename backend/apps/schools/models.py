import uuid
from django.conf import settings
from django.db import models

class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Membership(models.Model):
    class Role(models.TextChoices):
        SCHOOL_ADMIN = 'SCHOOL_ADMIN'
        PRINCIPAL = 'PRINCIPAL'
        VICE_PRINCIPAL = 'VICE_PRINCIPAL'
        ACADEMIC_AFFAIRS = 'ACADEMIC_AFFAIRS'
        HOMEROOM_TEACHER = 'HOMEROOM_TEACHER'
        SUBJECT_TEACHER = 'SUBJECT_TEACHER'
        SUPPORT_STAFF = 'SUPPORT_STAFF'
        PARENT = 'PARENT'
        STUDENT = 'STUDENT'
        DEPARTMENT_HEAD = 'DEPARTMENT_HEAD'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name='memberships')
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='memberships')
    role = models.CharField(max_length=32, choices=Role.choices)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=['tenant','account','role','is_active'])]

    def __str__(self):
        return f'{self.account} · {self.tenant} · {self.role}'

class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=80)
    target_id = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['tenant','created_at'])]
