export type Membership = {tenant_id: string; tenant: string; role: string};
export type CurrentUser = {id: string; username: string; display_name: string; session_expires_at: number; memberships: Membership[]};
export type Student = {id: string; student_code: string; full_name: string; date_of_birth?: string | null; is_active?: boolean};
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
    const brief = typeof payload === 'object' && payload !== null && 'detail' in payload
      ? String((payload as {detail: unknown}).detail) : `API error (${response.status})`;
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
    classrooms:(token:string,tenantId:string)=>request<unknown[]>('/api/v1/classrooms/',token,tenantId),
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
