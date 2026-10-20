"""Mandatory school-scoped queryset builders. Never filter only by object UUID."""
from django.db.models import Q
from django.utils import timezone
from apps.academics.models import Student, Enrollment, TeacherAssignment, GuardianLink, StudentAccount, Classroom
from apps.schools.models import Membership

BROAD_STUDENT_READ = {'SCHOOL_ADMIN', 'PRINCIPAL', 'VICE_PRINCIPAL', 'ACADEMIC_AFFAIRS'}
BROAD_CLASS_READ = BROAD_STUDENT_READ


def active_roles(user, tenant):
    today = timezone.localdate()
    return set(Membership.objects.filter(
        tenant=tenant, account=user, is_active=True, valid_from__lte=today
    ).filter(Q(valid_to__isnull=True) | Q(valid_to__gte=today)).values_list('role', flat=True))


def visible_students(user, tenant, roles):
    """Union of valid relationships, always scoped to the requested tenant."""
    base = Student.objects.filter(tenant=tenant, is_active=True)
    if BROAD_STUDENT_READ & roles:
        return base
    today = timezone.localdate()
    eligible = Q(pk__in=[])
    if 'HOMEROOM_TEACHER' in roles or 'SUBJECT_TEACHER' in roles:
        kinds = []
        if 'HOMEROOM_TEACHER' in roles:
            kinds.append('HOMEROOM')
        if 'SUBJECT_TEACHER' in roles:
            kinds.append('SUBJECT')
        classrooms = TeacherAssignment.objects.filter(
            tenant=tenant, teacher=user, kind__in=kinds, is_active=True,
            classroom__year__starts_on__lte=today, classroom__year__ends_on__gte=today,
            starts_on__lte=today
        ).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today)).values('classroom_id')
        student_ids = Enrollment.objects.filter(
            tenant=tenant, classroom_id__in=classrooms, is_active=True,
            starts_on__lte=today
        ).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today)).values('student_id')
        eligible |= Q(pk__in=student_ids)
    if 'PARENT' in roles:
        linked = GuardianLink.objects.filter(
            tenant=tenant, guardian=user, is_active=True,
            is_verified=True, can_view_academic=True, valid_from__lte=today
        ).filter(Q(valid_to__isnull=True) | Q(valid_to__gte=today)).values('student_id')
        eligible |= Q(pk__in=linked)
    if 'STUDENT' in roles:
        self_students = StudentAccount.objects.filter(tenant=tenant, account=user).values('student_id')
        eligible |= Q(pk__in=self_students)
    return base.filter(eligible).distinct()


def visible_classrooms(user, tenant, roles):
    base = Classroom.objects.filter(tenant=tenant)
    if BROAD_CLASS_READ & roles:
        return base
    today = timezone.localdate()
    eligible = Q(pk__in=[])
    kinds = []
    if 'HOMEROOM_TEACHER' in roles:
        kinds.append('HOMEROOM')
    if 'SUBJECT_TEACHER' in roles:
        kinds.append('SUBJECT')
    assigned = TeacherAssignment.objects.filter(
        tenant=tenant, teacher=user, kind__in=kinds, is_active=True,
            classroom__year__starts_on__lte=today, classroom__year__ends_on__gte=today,
        starts_on__lte=today
    ).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today)).values('classroom_id')
    eligible |= Q(pk__in=assigned)
    # A teacher's roster must not grant access to other classes of those pupils.
    family_roles = roles & {'PARENT', 'STUDENT'}
    ids = Enrollment.objects.filter(
        tenant=tenant, student__in=visible_students(user, tenant, family_roles),
        is_active=True, starts_on__lte=today
    ).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today)).values('classroom_id')
    eligible |= Q(pk__in=ids)
    return base.filter(eligible).distinct()


def student_profile_detail_level(user, tenant, roles, student):
    """Subject-teacher visibility is minimal even when relationship allows listing."""
    if BROAD_STUDENT_READ & roles:
        return 'full'
    today = timezone.localdate()
    if 'PARENT' in roles and GuardianLink.objects.filter(
        tenant=tenant, guardian=user, student=student, is_active=True,
        is_verified=True, can_view_academic=True, valid_from__lte=today
    ).filter(Q(valid_to__isnull=True) | Q(valid_to__gte=today)).exists():
        return 'full'
    if 'STUDENT' in roles and StudentAccount.objects.filter(
        tenant=tenant, account=user, student=student).exists():
        return 'full'
    today = timezone.localdate()
    enrolled = Enrollment.objects.filter(tenant=tenant, student=student, is_active=True,
                                         starts_on__lte=today).filter(
        Q(ends_on__isnull=True) | Q(ends_on__gte=today))
    if 'HOMEROOM_TEACHER' in roles and TeacherAssignment.objects.filter(
        tenant=tenant, teacher=user, kind='HOMEROOM', is_active=True,
        classroom__year__starts_on__lte=today, classroom__year__ends_on__gte=today,
        classroom_id__in=enrolled.values('classroom_id'), starts_on__lte=today
    ).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today)).exists():
        return 'full'
    return 'minimal'
