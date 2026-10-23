"""Framework-independent grading logic for the THCS pilot.

Under Circular 22/2021 grade average = (sum regular + 2*midterm + 3*final)/(count regular+5).
Do NOT infer annual grade, behavior grade, ranking, or digital transcript from this function.
"""
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation


def parse_score(value):
    """Reject booleans, NaN, Infinity, >1 decimal or out of [0,10]."""
    if isinstance(value, bool) or value is None or isinstance(value, (list, dict)):
        raise ValueError('Điểm phải là số từ 0 đến 10, tối đa 1 chữ số thập phân.')
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Điểm không hợp lệ.')
    if not number.is_finite() or number < 0 or number > 10 or number.as_tuple().exponent < -1:
        raise ValueError('Điểm phải từ 0 đến 10, tối đa 1 chữ số thập phân.')
    return number


def semester_average(regular, midterm, final, expected_regular):
    """Returns None until all specified assessments are present. Round half-up to 0.1."""
    if expected_regular not in (2, 3, 4):
        raise ValueError('Số điểm thường xuyên phải là 2, 3 hoặc 4.')
    if len(regular) != expected_regular or midterm is None or final is None:
        return None
    scores = [parse_score(x) for x in regular]
    m, f = parse_score(midterm), parse_score(final)
    numerator = sum(scores, Decimal('0')) + 2*m + 3*f
    return (numerator / Decimal(expected_regular + 5)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)


def qualitative_semester(values, expected_regular):
    """Only 'PASS' when all expected observations (regular + midterm + final) PASS."""
    if expected_regular != 2 or len(values) != 4:
        return None
    if any(value not in ('PASS','FAIL') for value in values):
        return None
    return 'PASS' if all(value == 'PASS' for value in values) else 'FAIL'


def can_transition(current, next_state):
    return (current, next_state) in {('DRAFT','LOCKED'), ('LOCKED','PUBLISHED')}
