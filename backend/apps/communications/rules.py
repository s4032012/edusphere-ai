"""Pure validation helpers reusable in service layer and offline tests."""
import uuid

STAFF = frozenset({'SCHOOL_ADMIN','SUPPORT_STAFF','ACADEMIC_AFFAIRS'})
NOTICE_BROADCAST = frozenset({'SCHOOL_ADMIN','PRINCIPAL','VICE_PRINCIPAL','ACADEMIC_AFFAIRS'})

def validate_body(value, limit=5000, field='body'):
    if not isinstance(value,str) or not value.strip() or '\x00' in value or len(value)>limit:
        raise ValueError(f'{field}: cần 1–{limit} ký tự')
    return value.strip()

def validate_key(value):
    if not isinstance(value,str) or len(value)>72 or not value.strip():
        raise ValueError('client_key required (max 72 chars)')
    try: uuid.UUID(value)
    except (ValueError,TypeError,AttributeError): raise ValueError('client_key must be UUID')
    return str(uuid.UUID(value))

def valid_ticket_transition(current, target, is_staff):
    if current==target: return False
    return bool(is_staff and target in {
        'OPEN':{'IN_PROGRESS','RESOLVED'},
        'IN_PROGRESS':{'RESOLVED','OPEN'},
        'RESOLVED':{'IN_PROGRESS','CLOSED'},
        'CLOSED':set(),
    }.get(current,set()))

def valid_notice(scope, classroom_id, grade_level):
    return ((scope=='SCHOOL' and not classroom_id and grade_level is None) or
        (scope=='CLASS' and bool(classroom_id) and grade_level is None) or
        (scope=='GRADE' and not classroom_id and type(grade_level) is int and 6<=grade_level<=9))
