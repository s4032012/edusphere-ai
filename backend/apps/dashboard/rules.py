"""Deterministic display rules. No model, prediction or third-party export."""
MAX_GRADES=8
MAX_HOMEWORK=8
MAX_NOTICES=5
MAX_EVENTS=5

def can_open_dashboard(roles):
    return bool({'PARENT','STUDENT'} & roles)

def attendance_summary(marks):
    counts={key:marks.count(key) for key in ('PRESENT','ABSENT','LATE')}
    return {**counts,'recorded_days':sum(counts.values())}

def homework_display(state,*,due_at,now):
    if state in {'RETURNED','SUBMITTED'}:return state
    if now>due_at:return 'OVERDUE'
    return 'IN_PROGRESS' if state=='DRAFT' else 'NOT_SUBMITTED'

def digest_sentences(*,attendance,homework,published_grade_count):
    if attendance['recorded_days']:
        attendance_text=(f"Có {attendance['recorded_days']} ngày được ghi nhận điểm danh trong 30 ngày gần đây; "
            f"{attendance['ABSENT']} ngày vắng và {attendance['LATE']} ngày đi muộn.")
    else:attendance_text='Chưa có dữ liệu điểm danh đã nộp trong 30 ngày gần đây; không suy ra có mặt hay vắng.'
    homework_text=(f"Có {homework['total']} bài tập đã công bố (kể cả bài đã đóng); "
        f"{homework['submitted_or_returned']} bài đã nộp hoặc được trả, "
        f"{homework['overdue']} bài chưa nộp và đã quá hạn.") if homework['total'] else 'Chưa có bài tập đã công bố trong phạm vi hiện tại.'
    return [
        {'kind':'attendance','text':attendance_text,'source':'submitted_or_locked_attendance'},
        {'kind':'homework','text':homework_text,'source':'published_homework_and_own_submissions'},
        {'kind':'grades','text':f'Có {published_grade_count} kết quả đánh giá trong danh sách gần đây (tối đa {MAX_GRADES}); đây không phải toàn bộ học bạ.','source':'published_assessments_only'},
    ]
