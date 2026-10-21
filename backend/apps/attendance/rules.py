"""Pure domain rules: intentionally testable without importing Django."""
from datetime import date, timedelta

ATTENDANCE_STATES = ('DRAFT', 'SUBMITTED', 'LOCKED')
PRESENCE_CODES = ('PRESENT', 'ABSENT', 'LATE')
LEAVE_STATES = ('PENDING', 'APPROVED', 'REJECTED', 'WITHDRAWN')


def leave_range_valid(start: date, end: date, today: date) -> bool:
    """Pilot policy: <=14 calendar days, requests from <=7 days ago to <=90 days ahead."""
    return start <= end and 1 <= (end - start).days + 1 <= 14 and today - timedelta(days=7) <= start <= today + timedelta(days=90)


def next_leave_state(current: str, action: str, actor: str) -> str:
    transitions = {
        ('PENDING', 'approve', 'reviewer'): 'APPROVED',
        ('PENDING', 'reject', 'reviewer'): 'REJECTED',
        ('PENDING', 'withdraw', 'guardian'): 'WITHDRAWN',
    }
    key = (current, action, actor)
    if key not in transitions:
        raise ValueError('Chuyển trạng thái không hợp lệ hoặc thiếu quyền.')
    return transitions[key]


def effective_presence(mark: str, approved_leave: bool) -> str:
    """Keep actual roll-call unchanged; approved leave only affects derived status."""
    if mark not in PRESENCE_CODES:
        raise ValueError('Mã điểm danh không hợp lệ.')
    return 'EXCUSED_ABSENCE' if mark == 'ABSENT' and approved_leave else mark


def can_edit_attendance(session_state: str) -> bool:
    return session_state == 'DRAFT'
