"""Pure authorization decisions. Always combine with tenant-scoped database queries.

These functions are deliberately Django-free so Sprint 0 policy tests can run
without a database or external dependencies.
"""
from dataclasses import dataclass
from datetime import date
from enum import Enum


class Role(str, Enum):
    SCHOOL_ADMIN = 'SCHOOL_ADMIN'
    PRINCIPAL = 'PRINCIPAL'
    VICE_PRINCIPAL = 'VICE_PRINCIPAL'
    ACADEMIC_AFFAIRS = 'ACADEMIC_AFFAIRS'
    HOMEROOM_TEACHER = 'HOMEROOM_TEACHER'
    SUBJECT_TEACHER = 'SUBJECT_TEACHER'
    PARENT = 'PARENT'
    STUDENT = 'STUDENT'
    SUPPORT_STAFF = 'SUPPORT_STAFF'
    DEPARTMENT_HEAD = 'DEPARTMENT_HEAD'


@dataclass(frozen=True)
class Relation:
    tenant_id: str
    actor_id: str
    student_id: str
    kind: str
    active: bool = True
    verified: bool = False
    starts_on: date | None = None
    ends_on: date | None = None
    can_view_academic: bool = True


def currently_valid(starts_on: date | None, ends_on: date | None, *, today: date) -> bool:
    return (starts_on is None or starts_on <= today) and (ends_on is None or ends_on >= today)


def can_read_student(*, actor_id: str, tenant_id: str, student_id: str,
                     roles: set[str], relations: list[Relation], today: date) -> bool:
    """Default-deny: memberships are expected to be validated by caller."""
    if Role.SCHOOL_ADMIN.value in roles or Role.PRINCIPAL.value in roles or Role.VICE_PRINCIPAL.value in roles:
        return True
    if Role.ACADEMIC_AFFAIRS.value in roles:
        return True
    for rel in relations:
        if (rel.tenant_id != tenant_id or rel.actor_id != actor_id or
                rel.student_id != student_id or not rel.active or
                not currently_valid(rel.starts_on, rel.ends_on, today=today)):
            continue
        if rel.kind == 'HOMEROOM' and Role.HOMEROOM_TEACHER.value in roles:
            return True
        if rel.kind == 'SUBJECT' and Role.SUBJECT_TEACHER.value in roles:
            return True
        if rel.kind == 'GUARDIAN' and Role.PARENT.value in roles and rel.verified and rel.can_view_academic:
            return True
        if rel.kind == 'SELF' and Role.STUDENT.value in roles:
            return True
    return False
