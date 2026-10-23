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
