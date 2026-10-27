export type Membership = {tenant_id: string; tenant: string; role: string};
export type CurrentUser = {id: string; username: string; display_name: string; session_expires_at: number; memberships: Membership[]};
export type Student = {id: string; student_code: string; full_name: string; date_of_birth?: string | null; is_active?: boolean};
export type AcademicYear = {id: string; label: string; starts_on: string; ends_on: string};
export type Subject = {id: string; code: string; name: string};
export type Classroom = {id: string; code: string; grade_level: number; year: string};
export type Staff = {id: string; username: string; display_name: string; role: string; invitation_status?: string};
export type Enrollment = {id: string; student_id: string; student_name: string; classroom_id: string; classroom_code: string; is_active: boolean};
export type Assignment = {id: string; teacher_id: string; teacher_name: string; classroom_id: string; classroom_code: string; kind: string; subject_id?: string | null; subject_name?: string | null; is_active: boolean};
export type SchoolDashboard = {students: number; classes: number; staff_memberships: number; academic_years: number; active_enrollments: number; active_assignments: number};
export type AuditEvent = {id: string; action: string; target_type: string; target_id: string; created_at: string};
export type TokenPair = {access: string; refresh: string};
export const ROLES = {
  admin: ['SCHOOL_ADMIN', 'PRINCIPAL','VICE_PRINCIPAL','ACADEMIC_AFFAIRS','SUPPORT_STAFF'],
  teacher: ['SUBJECT_TEACHER','HOMEROOM_TEACHER','DEPARTMENT_HEAD'],
  parent: ['PARENT'], student: ['STUDENT'],
} as const;

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); this.name = 'ApiError'; }
}
function trimBase(url: string) { return url.replace(/\/+$/, ''); }
async function jsonFetch<T>(url: string, init: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const raw = await response.text();
  let payload: unknown;
  try { payload = raw ? JSON.parse(raw) : null; } catch { payload = raw; }
  if (!response.ok) {
    const brief = response.status < 500 && typeof payload === 'object' && payload !== null
      ? Object.entries(payload).map(([field,value])=>`${field==='detail'?'':field+': '}${Array.isArray(value)?value.join(' '):String(value)}`).join(' · ')
      : `API error (${response.status})`;
    throw new ApiError(response.status, brief);
  }
  return payload as T;
}
export function createApi(baseUrl: string) {
  const base = trimBase(baseUrl);
  const login = async (username: string, password: string) => jsonFetch<TokenPair>(`${base}/api/v1/auth/token/`, {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username,password}),
  });
  const request = <T,>(path: string, token: string, tenantId?: string) => jsonFetch<T>(`${base}${path}`, {
    method:'GET', headers:{'Authorization':`Bearer ${token}`, ...(tenantId?{'X-Tenant-ID':tenantId}:{})},
  });
  return {
    login,
    me: (token:string)=>request<CurrentUser>('/api/v1/me/',token),
    students:(token:string,tenantId:string)=>request<Student[]>('/api/v1/students/',token,tenantId),
    classrooms:(token:string,tenantId:string)=>request<Classroom[]>('/api/v1/classrooms/',token,tenantId),
    adminGet: <T,>(path:string,token:string,tenantId:string)=>request<T>(path,token,tenantId),
    adminPost: <T,>(path:string,token:string,tenantId:string,payload:Record<string,unknown>={})=>jsonFetch<T>(`${base}${path}`,{
      method:'POST',headers:{'Content-Type':'application/json','Authorization':`Bearer ${token}`,'X-Tenant-ID':tenantId},body:JSON.stringify(payload),
    }),
    adminPatch: <T,>(path:string,token:string,tenantId:string,payload:Record<string,unknown>)=>jsonFetch<T>(`${base}${path}`,{
      method:'PATCH',headers:{'Content-Type':'application/json','Authorization':`Bearer ${token}`,'X-Tenant-ID':tenantId},body:JSON.stringify(payload),
    }),
  };
}
/** UI filtering only. Backend remains sole authority for authorization. */
export function membershipsFor(user: CurrentUser, allowed: readonly string[]) {
  return user.memberships.filter(m => allowed.includes(m.role));
}

/** Invalidates asynchronous responses when the selected school/session changes. */
export function createRequestScope() {
  let revision = 0;
  return {
    invalidate: () => { revision += 1; },
    capture: () => { const current = revision; return () => current === revision; },
  };
}

/** Sprint 2 domain contracts. Backend alone determines authorization. */
export type AttendanceMark = 'PRESENT'|'ABSENT'|'LATE';
export type AttendanceState = 'DRAFT'|'SUBMITTED'|'LOCKED';
export type AttendanceSessionSummary = {id:string; classroom_id:string; classroom_code:string; attendance_date:string; state:AttendanceState};
export type AttendanceRosterRow = {id:string;student_code:string;full_name:string;mark:AttendanceMark|null;note:string;effective_status:AttendanceMark|'EXCUSED_ABSENCE'|null};
export type AttendanceSessionDetail = {id:string;classroom_id:string;attendance_date:string;state:AttendanceState;roster:AttendanceRosterRow[]};
export type LeaveState = 'PENDING'|'APPROVED'|'REJECTED'|'WITHDRAWN';
export type LeaveRequest = {id:string;student_id:string;student_name?:string;from_date:string;through_date:string;reason:string;state:LeaveState;decision_note:string;created_at:string};
export type AttendanceHistory = {date:string;mark:AttendanceMark;effective_status:AttendanceMark|'EXCUSED_ABSENCE'};
export type NotificationEntry = {id:string;type:string;payload:Record<string,unknown>;state:string;created_at:string};
export function createAttendanceApi(baseUrl:string) {
  const base=baseUrl.replace(/\/+$/,'');
  const send=<T,>(path:string,token:string,tenantId:string,method:'GET'|'POST'|'PUT'='GET',body?:unknown):Promise<T> =>
    jsonFetch<T>(`${base}${path}`,{method,headers:{'Authorization':`Bearer ${token}`,'X-Tenant-ID':tenantId,
      ...(body===undefined?{}:{'Content-Type':'application/json'})},...(body===undefined?{}:{body:JSON.stringify(body)})});
  return {
    sessions:(token:string,tenant:string,date?:string)=>send<AttendanceSessionSummary[]>(`/api/v1/attendance/sessions/${date?`?date=${encodeURIComponent(date)}`:''}`,token,tenant),
    start:(token:string,tenant:string,classroom_id:string,attendance_date:string)=>send<{id:string;state:AttendanceState;created:boolean}>('/api/v1/attendance/sessions/',token,tenant,'POST',{classroom_id,attendance_date}),
    detail:(token:string,tenant:string,id:string)=>send<AttendanceSessionDetail>(`/api/v1/attendance/sessions/${id}/`,token,tenant),
    save:(token:string,tenant:string,id:string,records:{student_id:string;mark:AttendanceMark;note?:string}[])=>send<{updated:number;state:AttendanceState}>(`/api/v1/attendance/sessions/${id}/records/`,token,tenant,'PUT',{records}),
    submit:(token:string,tenant:string,id:string)=>send<{id:string;state:AttendanceState}>(`/api/v1/attendance/sessions/${id}/submit/`,token,tenant,'POST',{}),
    lock:(token:string,tenant:string,id:string)=>send<{id:string;state:AttendanceState}>(`/api/v1/attendance/sessions/${id}/lock/`,token,tenant,'POST',{}),
    studentAttendance:(token:string,tenant:string,id:string)=>send<AttendanceHistory[]>(`/api/v1/attendance/students/${id}/`,token,tenant),
    leaves:(token:string,tenant:string,studentId?:string)=>send<LeaveRequest[]>(`/api/v1/leave-requests/${studentId?`?student_id=${encodeURIComponent(studentId)}`:''}`,token,tenant),
    requestLeave:(token:string,tenant:string,student_id:string,from_date:string,through_date:string,reason:string)=>send<LeaveRequest>('/api/v1/leave-requests/',token,tenant,'POST',{student_id,from_date,through_date,reason}),
    decide:(token:string,tenant:string,id:string,action:'approve'|'reject',decision_note='')=>send<LeaveRequest>(`/api/v1/leave-requests/${id}/decision/`,token,tenant,'POST',{action,decision_note}),
    withdraw:(token:string,tenant:string,id:string)=>send<LeaveRequest>(`/api/v1/leave-requests/${id}/withdraw/`,token,tenant,'POST',{}),
    notifications:(token:string,tenant:string)=>send<NotificationEntry[]>('/api/v1/notifications/',token,tenant),
  };
}

/** Sprint 3: Grade Management & Academic Assessment. API enforces school and assignment scopes. */
export type GradeMode = 'SCORE'|'COMMENT';
export type AssessmentState = 'DRAFT'|'LOCKED'|'PUBLISHED';
export type AssessmentKind = 'TX'|'GK'|'CK';
export type GradeBook = {id:string;classroom_id:string;classroom_code:string;subject_id:string;subject_name:string;
  semester:'1'|'2';mode:GradeMode;regular_required:number};
export type GradeEntry = {id:string|null;student_id:string;student_code:string;full_name:string;
  score:string|null;result:string;version:number};
export type Assessment = {id:string;book_id:string;kind:AssessmentKind;slot:number;title:string;
  state:AssessmentState;entries?:GradeEntry[]};
export type GradeBookDetail = GradeBook & {can_edit:boolean;assessments:Assessment[]};
export type StudentGrades = {student_id:string;student_name:string;books:(GradeBook & {
  assessments:{kind:AssessmentKind;slot:number;title:string;score:string|null;result:string}[];
  semester_average:string|null;semester_result:string|null})[]};
export type GradeRevision = {id:string;entry_id:string;state:'PENDING'|'APPROVED'|'REJECTED';reason:string;
  from_version:number;student_name:string;classroom_code:string;subject_name:string;assessment_title:string;old_result:string;decision_note:string;old_score:string|null;proposed_score:string|null;proposed_result:string};
export function createGradesApi(baseUrl:string){
  const base=trimBase(baseUrl);
  const call=<T,>(path:string,token:string,tenant:string,method:'GET'|'POST'|'PUT'='GET',payload?:unknown):Promise<T>=>
    jsonFetch<T>(`${base}${path}`,{method,headers:{'Authorization':`Bearer ${token}`,'X-Tenant-ID':tenant,
      ...(payload===undefined?{}:{'Content-Type':'application/json'})},
      ...(payload===undefined?{}:{body:JSON.stringify(payload)})});
  return {
    books:(token:string,tenant:string)=>call<GradeBook[]>('/api/v1/gradebooks/',token,tenant),
    createBook:(token:string,tenant:string,payload:{classroom_id:string;subject_id:string;semester:'1'|'2';mode:GradeMode;regular_required:number})=>
      call<GradeBook>('/api/v1/gradebooks/',token,tenant,'POST',payload),
    book:(token:string,tenant:string,id:string)=>call<GradeBookDetail>(`/api/v1/gradebooks/${id}/`,token,tenant),
    createAssessment:(token:string,tenant:string,id:string,kind:AssessmentKind,slot:number,title:string)=>
      call<Assessment>(`/api/v1/gradebooks/${id}/assessments/`,token,tenant,'POST',{kind,slot,title}),
    saveGrades:(token:string,tenant:string,id:string,entries:{student_id:string;score?:string;result?:string}[])=>
      call<{updated:number;state:AssessmentState}>(`/api/v1/assessments/${id}/entries/`,token,tenant,'PUT',{entries}),
    lock:(token:string,tenant:string,id:string)=>call<Assessment>(`/api/v1/assessments/${id}/lock/`,token,tenant,'POST',{}),
    publish:(token:string,tenant:string,id:string)=>call<Assessment>(`/api/v1/assessments/${id}/publish/`,token,tenant,'POST',{}),
    student:(token:string,tenant:string,id:string)=>call<StudentGrades>(`/api/v1/students/${id}/grades/`,token,tenant),
    revisions:(token:string,tenant:string)=>call<GradeRevision[]>('/api/v1/grade-revisions/',token,tenant),
    requestRevision:(token:string,tenant:string,id:string,proposed:{score?:string;result?:string;reason:string})=>
      call<{id:string;state:string}>(`/api/v1/grade-entries/${id}/revision-requests/`,token,tenant,'POST',proposed),
    decideRevision:(token:string,tenant:string,id:string,action:'approve'|'reject',decision_note='')=>
      call<{id:string;state:string;entry_version:number}>(`/api/v1/grade-revisions/${id}/decision/`,token,tenant,'POST',{action,decision_note}),
  };
}

/** Sprint 4: Assignment & Homework. Feedback score is NOT a gradebook mark. */
export type HomeworkState = 'DRAFT'|'PUBLISHED'|'CLOSED';
export type SubmissionState = 'DRAFT'|'SUBMITTED'|'RETURNED';
export type HomeworkStatus = SubmissionState|'NOT_SUBMITTED'|'OVERDUE';
export type Homework = {id:string;classroom_id:string;classroom_code:string;subject_id:string;
  subject_name:string;teacher_id:string;title:string;instructions:string;due_at:string;
  allow_late:boolean;state:HomeworkState;created_at:string;can_manage:boolean};
export type HomeworkSubmission = {id:string;student_id:string;state:SubmissionState;
  version:number;submitted_at:string|null;returned_at:string|null;content_text:string|null;
  feedback:string|null;score:string|null};
export type HomeworkRow = {student_id:string;student_code:string;full_name:string;
  status:HomeworkStatus;submission:HomeworkSubmission|null};
export type HomeworkRoster = {assignment:Homework;students:HomeworkRow[]};
export type StudentHomeworkOverview = {student_id:string;student_name:string;
  items:{assignment:Homework;status:HomeworkStatus;submission:HomeworkSubmission|null}[]};
export function createHomeworkApi(baseUrl:string){
  const base=trimBase(baseUrl);
  const call=<T,>(path:string,token:string,tenant:string,method:'GET'|'POST'|'PUT'|'PATCH'='GET',payload?:unknown):Promise<T>=>
    jsonFetch<T>(`${base}${path}`,{method,headers:{'Authorization':`Bearer ${token}`,'X-Tenant-ID':tenant,
      ...(payload===undefined?{}:{'Content-Type':'application/json'})},
      ...(payload===undefined?{}:{body:JSON.stringify(payload)})});
  return {
    list:(token:string,tenant:string)=>call<Homework[]>('/api/v1/homework/',token,tenant),
    create:(token:string,tenant:string,data:{classroom_id:string;subject_id:string;title:string;
      instructions:string;due_at:string;allow_late:boolean})=>call<Homework>('/api/v1/homework/',token,tenant,'POST',data),
    detail:(token:string,tenant:string,id:string)=>call<Homework>(`/api/v1/homework/${id}/`,token,tenant),
    edit:(token:string,tenant:string,id:string,data:Partial<Pick<Homework,'title'|'instructions'|'due_at'|'allow_late'>>)=>
      call<Homework>(`/api/v1/homework/${id}/`,token,tenant,'PATCH',data),
    publish:(token:string,tenant:string,id:string)=>call<Homework>(`/api/v1/homework/${id}/publish/`,token,tenant,'POST',{}),
    close:(token:string,tenant:string,id:string)=>call<Homework>(`/api/v1/homework/${id}/close/`,token,tenant,'POST',{}),
    roster:(token:string,tenant:string,id:string)=>call<HomeworkRoster>(`/api/v1/homework/${id}/roster/`,token,tenant),
    student:(token:string,tenant:string,id:string)=>call<StudentHomeworkOverview>(`/api/v1/homework/students/${id}/`,token,tenant),
    mine:(token:string,tenant:string,id:string)=>call<{assignment:Homework;submission:HomeworkSubmission|null}>(`/api/v1/homework/${id}/my-submission/`,token,tenant),
    submit:(token:string,tenant:string,id:string,content_text:string,action:'save'|'submit',expected_version?:number)=>
      call<HomeworkSubmission>(`/api/v1/homework/${id}/my-submission/`,token,tenant,'PUT',{
        content_text,action,expected_version:expected_version??0}),
    returnWork:(token:string,tenant:string,submission_id:string,feedback:string,expected_version:number,score?:string)=>
      call<HomeworkSubmission>(`/api/v1/homework/submissions/${submission_id}/return/`,token,tenant,'POST',{
        feedback,expected_version,...(score?{score}:{})}),
  };
}

/** Sprint 5 — Communication, announcement, support, and notification contracts. */
export type NoticeScope='SCHOOL'|'GRADE'|'CLASS';
export type AnnouncementDto={id:string;scope:NoticeScope;classroom_id:string|null;grade_level:number|null;
 title:string;body:string;state:'DRAFT'|'PUBLISHED';created_at:string;published_at:string|null;read:boolean;can_publish:boolean;recipient_count:number|null;read_count:number|null};
export type ContactDto={id:string;name:string};
export type StudentContactsDto={student_id:string;teachers:ContactDto[];guardians:ContactDto[]};
export type ConversationDto={id:string;student_id:string;student_name:string;teacher_id:string;teacher_name:string;
 guardian_id:string;guardian_name:string;updated_at:string;unread_count:number};
export type ConversationMessageDto={id:string;sender_id:string;body:string;created_at:string};
export type TicketState='OPEN'|'IN_PROGRESS'|'RESOLVED'|'CLOSED';
export type TicketDto={id:string;version:number;category:string;subject:string;state:TicketState;student_id:string|null;
 requester_id:string;assignee_id:string|null;created_at:string;updated_at:string;details?:string;
 replies?:{id:string;author_id:string;body:string;created_at:string}[]};
export type InboxDto={id:string;type:string;payload:Record<string,unknown>;created_at:string;
 read:boolean;delivery_state:string};
export function createCommunicationsApi(baseUrl:string){
  const base=trimBase(baseUrl);
  const call=<T,>(path:string,token:string,tenant:string,method:'GET'|'POST'='GET',body?:unknown)=>
    jsonFetch<T>(`${base}/api/v1/comms${path}`,{method,headers:{'Authorization':`Bearer ${token}`,
      'X-Tenant-ID':tenant,...(body===undefined?{}:{'Content-Type':'application/json'})},
      ...(body===undefined?{}:{body:JSON.stringify(body)})});
  return {
    announcements:(token:string,tenant:string)=>call<AnnouncementDto[]>('/announcements/',token,tenant),
    createAnnouncement:(token:string,tenant:string,payload:{scope:NoticeScope;title:string;body:string;classroom_id?:string;grade_level?:number})=>
      call<AnnouncementDto>('/announcements/',token,tenant,'POST',payload),
    publishAnnouncement:(token:string,tenant:string,id:string)=>call<{id:string;state:string;recipients:number}>(`/announcements/${id}/publish/`,token,tenant,'POST',{}),
    readAnnouncement:(token:string,tenant:string,id:string)=>call<{read:boolean}>(`/announcements/${id}/read/`,token,tenant,'POST',{}),
    contacts:(token:string,tenant:string,studentId:string)=>call<StudentContactsDto>(`/students/${studentId}/contacts/`,token,tenant),
    conversations:(token:string,tenant:string)=>call<ConversationDto[]>('/conversations/',token,tenant),
    createConversation:(token:string,tenant:string,student_id:string,teacher_id:string,guardian_id:string)=>
      call<ConversationDto>('/conversations/',token,tenant,'POST',{student_id,teacher_id,guardian_id}),
    messages:(token:string,tenant:string,id:string)=>call<{conversation:ConversationDto;messages:ConversationMessageDto[]}>(`/conversations/${id}/messages/`,token,tenant),
    sendMessage:(token:string,tenant:string,id:string,body:string,client_key:string)=>
      call<ConversationMessageDto>(`/conversations/${id}/messages/`,token,tenant,'POST',{body,client_key}),
    readConversation:(token:string,tenant:string,id:string,last_message_id:string|null)=>call<{read:boolean}>(`/conversations/${id}/read/`,token,tenant,'POST',{last_message_id}),
    tickets:(token:string,tenant:string)=>call<TicketDto[]>('/tickets/',token,tenant),
    createTicket:(token:string,tenant:string,payload:{category:string;subject:string;details:string;student_id?:string})=>
      call<TicketDto>('/tickets/',token,tenant,'POST',payload),
    ticket:(token:string,tenant:string,id:string)=>call<TicketDto>(`/tickets/${id}/`,token,tenant),
    replyTicket:(token:string,tenant:string,id:string,body:string)=>call<TicketDto>(`/tickets/${id}/reply/`,token,tenant,'POST',{body}),
    changeTicketStatus:(token:string,tenant:string,id:string,state:TicketState,expected_version:number)=>call<TicketDto>(`/tickets/${id}/transition/`,token,tenant,'POST',{state,expected_version}),
    inbox:(token:string,tenant:string)=>call<InboxDto[]>('/notifications/',token,tenant),
    markInboxRead:(token:string,tenant:string,id:string)=>call<{read:boolean}>(`/notifications/${id}/read/`,token,tenant,'POST',{}),
  };
}

/** Non-secret retry identifier, retained by the composer until acknowledgement. */
export function messageKey():string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g,c=>{
    const r=Math.floor(Math.random()*16);return (c==='x'?r:(r&3)|8).toString(16);
  });
}
export const ticketTransitions:Record<TicketState,TicketState[]>={OPEN:['IN_PROGRESS','RESOLVED'],IN_PROGRESS:['OPEN','RESOLVED'],RESOLVED:['IN_PROGRESS','CLOSED'],CLOSED:[]};
export const communicationLabels:Record<string,string>={
  ANNOUNCEMENT_PUBLISHED:'Thông báo mới',MESSAGE_RECEIVED:'Tin nhắn mới',TICKET_REPLY:'Phản hồi hỗ trợ',TICKET_STATUS:'Trạng thái hỗ trợ',
  UNEXCUSED_ABSENCE:'Vắng không phép',LEAVE_DECIDED:'Kết quả xin nghỉ',GRADE_PUBLISHED:'Điểm đã công bố',GRADE_CORRECTED:'Điểm đã điều chỉnh',HOMEWORK_RETURNED:'Bài tập đã trả',
  OPEN:'Mới tiếp nhận',IN_PROGRESS:'Đang xử lý',RESOLVED:'Đã giải quyết',CLOSED:'Đã đóng',DRAFT:'Bản nháp',PUBLISHED:'Đã công bố',
  ACCOUNT:'Tài khoản',ACADEMIC_RECORD:'Hồ sơ học tập',SCHEDULE:'Lịch học',FEES:'Học phí',OTHER:'Khác',SCHOOL:'Toàn trường',GRADE:'Theo khối',CLASS:'Theo lớp'};

/** Sprint 6: only server-authorized, released educational information. */
export type DashboardChild = {id:string;full_name:string;student_code:string};
export type AttendanceDigest = {window_days:number;from_date:string;through_date:string;recorded_days:number;PRESENT:number;ABSENT:number;LATE:number};
export type DashboardGrade = {assessment_id:string;subject:string;title:string;semester:string;kind:'TX'|'GK'|'CK';
  score:string|null;result:string|null;note:string;published_at:string|null};
export type DashboardHomework = {id:string;title:string;subject:string;due_at:string;
  status:'NOT_SUBMITTED'|'OVERDUE'|'IN_PROGRESS'|'SUBMITTED'|'RETURNED';feedback_available:boolean;assignment_state:'PUBLISHED'|'CLOSED';actionable:boolean;allow_late:boolean};
export type DashboardNotice = {id:string;title:string;scope:'SCHOOL'|'GRADE'|'CLASS';published_at:string|null;read:boolean};
export type DashboardEvent = {id:string;event_type:string;created_at:string;read:boolean};
export type StudentDashboardSnapshot = {
  student:{id:string;full_name:string;student_code:string;classroom:{id:string;code:string;grade_level:number}|null};
  as_of:string;enrollment_status:'CURRENT'|'NONE'|'AMBIGUOUS';attendance:AttendanceDigest;
  grades:{items:DashboardGrade[];limited_to:number;released_only:true};
  homework:{summary:{total:number;submitted_or_returned:number;overdue:number;pending_action:number};items:DashboardHomework[];limited_to:number};
  announcements:DashboardNotice[];notifications:{scope:'ACCOUNT';items:DashboardEvent[]};data_limits:string[];
};
export type AiPreview = {student_id:string;as_of:string;enabled:false;mode:'RULE_BASED_PREVIEW';model_called:false;
  exported_to_provider:false;human_review_required:true;enrollment_status:'CURRENT'|'NONE'|'AMBIGUOUS';
  sentences:{kind:string;text:string;source:string}[];limitations:string[]};
export function createDashboardApi(baseUrl:string){
  const base=trimBase(baseUrl);
  const get=<T,>(path:string,token:string,tenantId:string)=>jsonFetch<T>(`${base}${path}`,{method:'GET',
    headers:{'Authorization':`Bearer ${token}`,'X-Tenant-ID':tenantId}});
  return {
    children:(token:string,tenant:string)=>get<{students:DashboardChild[]}>('/api/v1/dashboard/children/',token,tenant),
    student:(token:string,tenant:string,studentId:string)=>get<StudentDashboardSnapshot>(
      `/api/v1/dashboard/students/${encodeURIComponent(studentId)}/`,token,tenant),
    aiPreview:(token:string,tenant:string,studentId:string)=>get<AiPreview>(
      `/api/v1/dashboard/students/${encodeURIComponent(studentId)}/ai-preview/`,token,tenant),
  };
}
