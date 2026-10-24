"""Sprint 4 pure homework policies; independently testable without Django."""
from datetime import datetime
from decimal import Decimal, InvalidOperation

ASSIGNMENT_STATES = ('DRAFT', 'PUBLISHED', 'CLOSED')
SUBMISSION_STATES = ('DRAFT', 'SUBMITTED', 'RETURNED')


def assignment_transition(old: str, new: str) -> bool:
    return (old, new) in {('DRAFT','PUBLISHED'), ('PUBLISHED','CLOSED')}


def can_submit(*, assignment_state: str, deadline: datetime, now: datetime, allow_late: bool,
               submission_state: str | None = None) -> bool:
    if assignment_state != 'PUBLISHED' or submission_state == 'RETURNED':
        return False
    if deadline.tzinfo is None or now.tzinfo is None:
        raise ValueError('Timezone-aware dates required.')
    return bool(allow_late or now <= deadline)


def can_mark(submission_state: str) -> bool:
    return submission_state == 'SUBMITTED'


def parse_feedback_score(raw):
    if raw is None or raw == '':
        return None
    if isinstance(raw, bool):
        raise ValueError('Điểm phải là số thập phân 0-10.')
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError('Điểm không hợp lệ.')
    if not value.is_finite() or not (Decimal('0') <= value <= Decimal('10')):
        raise ValueError('Điểm phải nằm trong khoảng 0-10.')
    if value.as_tuple().exponent < -1:
        raise ValueError('Điểm chỉ được có 1 chữ số thập phân.')
    return value.quantize(Decimal('.1'))


def submission_status(*, state: str | None, due_at: datetime, now: datetime) -> str:
    if state == 'RETURNED': return 'RETURNED'
    if state == 'SUBMITTED': return 'SUBMITTED'
    if state == 'DRAFT': return 'DRAFT'
    return 'OVERDUE' if now > due_at else 'NOT_SUBMITTED'
