import {useCallback,useEffect,useMemo,useState,useRef,type FormEvent,type ReactNode} from 'react';
import {ApiError,createRequestScope,createApi,membershipsFor,type CurrentUser,type Student,type AcademicYear,type Classroom,
  type Subject,type Staff,type Enrollment,type Assignment,type SchoolDashboard,type AuditEvent} from '@edusphere/api-client';
import './style.css';

const api=createApi(import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000');
type Page='overview'|'years'|'subjects'|'staff'|'classrooms'|'students'|'enrollments'|'assignments'|'guardians'|'audit';
type FormValues=Record<string,string>;
type Entry={id:string;label:string;subtitle?:string};
const sections:{key:Page;label:string;icon:string}[]=[
  {key:'overview',label:'Tổng quan',icon:'▦'},
  {key:'years',label:'Năm học',icon:'▤'},
  {key:'subjects',label:'Môn học',icon:'◇'},
  {key:'staff',label:'Giáo viên & nhân sự',icon:'♙'},
  {key:'classrooms',label:'Lớp học',icon:'▣'},
  {key:'students',label:'Học sinh',icon:'♧'},
  {key:'enrollments',label:'Phân lớp',icon:'⇄'},
  {key:'assignments',label:'Phân công giáo viên',icon:'⌁'},
  {key:'guardians',label:'Phụ huynh',icon:'♡'},
  {key:'audit',label:'Audit log',icon:'◷'},
];
const prettyRole:Record<string,string>={SUBJECT_TEACHER:'Giáo viên bộ môn',HOMEROOM_TEACHER:'Giáo viên chủ nhiệm',
  ACADEMIC_AFFAIRS:'Giáo vụ',DEPARTMENT_HEAD:'Tổ trưởng chuyên môn'};

function Field({label,name,type='text',value,onChange,placeholder,options,required=true}:{label:string;name:string;type?:string;value:string;
  onChange:(name:string,val:string)=>void;placeholder?:string;options?:Entry[];required?:boolean}){
  return <label className="field"><span>{label}</span>{options?<select aria-label={label} name={name} value={value} required={required} onChange={e=>onChange(name,e.target.value)}>
  <option value="">Chọn...</option>{options.map(o=><option key={o.id} value={o.id}>{o.label}</option>)}</select>:
  <input name={name} type={type} value={value} placeholder={placeholder} required={required} onChange={e=>onChange(name,e.target.value)}/>}</label>;
}

function Tag({text,tone='neutral'}:{text:string;tone?:'neutral'|'green'|'amber'}){return <span className={`tag tag-${tone}`}>{text}</span>}
function Notice({text,kind}:{text:string;kind:'success'|'error'}){return <p className={`notice ${kind}`} role={kind==='error'?'alert':'status'}>{text}</p>}

export default function App(){
  const [username,setUsername]=useState('admin_a');const [password,setPassword]=useState('');
  const [token,setToken]=useState('');const [user,setUser]=useState<CurrentUser|null>(null);
  const [tenant,setTenant]=useState('');const [page,setPage]=useState<Page>('overview');
  const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [success,setSuccess]=useState('');
  const [search,setSearch]=useState('');const [form,setForm]=useState<FormValues>({});const [showForm,setShowForm]=useState(false);
  const [dashboard,setDashboard]=useState<SchoolDashboard|null>(null);
  const [years,setYears]=useState<AcademicYear[]>([]);const [subjects,setSubjects]=useState<Subject[]>([]);
  const [staff,setStaff]=useState<Staff[]>([]);const [classrooms,setClassrooms]=useState<Classroom[]>([]);
  const [students,setStudents]=useState<Student[]>([]);const [enrollments,setEnrollments]=useState<Enrollment[]>([]);
  const [assignments,setAssignments]=useState<Assignment[]>([]);const [audit,setAudit]=useState<AuditEvent[]>([]);
  const [guardians,setGuardians]=useState<{id:string;username:string;display_name:string;invitation_status?:string}[]>([]);
  const [guardianLinks,setGuardianLinks]=useState<{id:string;student_id:string;student_name:string;guardian_id:string;guardian_name:string;is_verified:boolean;is_active:boolean;relation:string}[]>([]);
  const scope=useRef(createRequestScope());
  const loadSequence=useRef(0);
  const saving=useRef(false);
  const clearData=useCallback(()=>{
    setDashboard(null);setYears([]);setSubjects([]);setStaff([]);setClassrooms([]);setStudents([]);
    setEnrollments([]);setAssignments([]);setAudit([]);setGuardians([]);setGuardianLinks([]);
    setForm({});setShowForm(false);setSearch('');setSuccess('');setError('');
  },[]);
  const logout=useCallback(()=>{
    scope.current.invalidate();loadSequence.current+=1;setBusy(false);clearData();
    setToken('');setUser(null);setTenant('');setPassword('');
  },[clearData]);
  const reportError=useCallback((err:unknown)=>{
    if(err instanceof ApiError&&err.status===401){logout();setError('Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.');}
    else setError(err instanceof Error?err.message:'Không thể kết nối máy chủ. Vui lòng thử lại.');
  },[logout]);
  useEffect(()=>{
    if(!user)return;
    const timer=setTimeout(()=>{logout();setError('Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.');},Math.max(0,user.session_expires_at*1000-Date.now()));
    return ()=>clearTimeout(timer);
  },[user,logout]);
  useEffect(()=>()=>{scope.current.invalidate();},[]);
  const membership=user?membershipsFor(user,['SCHOOL_ADMIN']):[];
  const currentTenant=membership.find(m=>m.tenant_id===tenant);
  const change=(name:string,value:string)=>setForm(f=>({...f,[name]:value,...(name==='kind'?{teacher_id:'',subject_id:''}:{})}));

  const reload=useCallback(async()=>{
    if(!token||!tenant)return;
    const current=scope.current.capture();const sequence=++loadSequence.current;
    const latest=()=>current()&&sequence===loadSequence.current;
    setBusy(true);setError('');
    try{
      // The v1 API has a 200-row list limit; pilot must not exceed that without pagination.
      const result=await Promise.all([
        api.adminGet<SchoolDashboard>('/api/v1/admin/dashboard/',token,tenant),
        api.adminGet<AcademicYear[]>('/api/v1/academic-years/',token,tenant),
        api.adminGet<Subject[]>('/api/v1/subjects/',token,tenant),
        api.adminGet<Staff[]>('/api/v1/staff/',token,tenant),
        api.classrooms(token,tenant),api.students(token,tenant),
        api.adminGet<Enrollment[]>('/api/v1/enrollments/list/',token,tenant),
        api.adminGet<Assignment[]>('/api/v1/teacher-assignments/list/',token,tenant),
        api.adminGet<AuditEvent[]>('/api/v1/audit-events/',token,tenant),
        api.adminGet<{id:string;username:string;display_name:string;invitation_status?:string}[]>('/api/v1/guardian-accounts/',token,tenant),
        api.adminGet<{id:string;student_id:string;student_name:string;guardian_id:string;guardian_name:string;is_verified:boolean;is_active:boolean;relation:string}[]>('/api/v1/guardian-links/list/',token,tenant),
      ]);
      if(!latest())return;
      setDashboard(result[0]);setYears(result[1]);setSubjects(result[2]);setStaff(result[3]);
      setClassrooms(result[4]);setStudents(result[5]);setEnrollments(result[6]);setAssignments(result[7]);setAudit(result[8]);setGuardians(result[9]);setGuardianLinks(result[10]);
    }catch(err){if(latest()){clearData();reportError(err);}}
    finally{if(latest())setBusy(false);}
  },[token,tenant,clearData,reportError]);
  useEffect(()=>{void reload()},[reload]);

  async function login(e:FormEvent){e.preventDefault();setBusy(true);setError('');
    try{const auth=await api.login(username,password);const me=await api.me(auth.access);
      const scoped=membershipsFor(me,['SCHOOL_ADMIN']);
      if(!scoped.length){setError('Tài khoản chưa được cấp quyền SCHOOL_ADMIN.');return;}
      scope.current.invalidate();clearData();setToken(auth.access);setUser(me);setTenant(scoped[0].tenant_id);setPage('overview');setPassword('');
    }catch(err){setError(err instanceof Error?err.message:'Đăng nhập thất bại.');}
    finally{setBusy(false);}
  }
  function navigate(next:Page){setPage(next);setSearch('');setError('');setSuccess('');setForm({});setShowForm(false);}
  async function create(path:string,payload:Record<string,unknown>,message:string){
    if(saving.current)return;
    saving.current=true;const current=scope.current.capture();
    setBusy(true);setError('');setSuccess('');
    try{
      await api.adminPost(path,token,tenant,payload);
      if(!current())return;
      setSuccess(message);setForm({});setShowForm(false);await reload();
    }catch(err){if(current())reportError(err);}
    finally{saving.current=false;if(current())setBusy(false);}
  }
  async function finish(path:string,message:string){
    if(!window.confirm('Xác nhận kết thúc quyền/phân lớp này? Thao tác sẽ được ghi audit.'))return;
    await create(path,{},message);
  }
  const choose=(items:Entry[]):Entry[]=>items;
  const yearOptions=useMemo(()=>choose(years.map(y=>({id:y.id,label:y.label}))),[years]);
  const classOptions=useMemo(()=>choose(classrooms.map(c=>({id:c.id,label:`${c.code} · ${years.find(y=>y.id===c.year)?.label||''}`}))),[classrooms,years]);
  const studentOptions=useMemo(()=>choose(students.map(s=>({id:s.id,label:`${s.student_code} — ${s.full_name}`}))),[students]);
  const staffOptions=useMemo(()=>choose(staff.filter(s=>s.role===(form.kind==='HOMEROOM'?'HOMEROOM_TEACHER':form.kind==='SUBJECT'?'SUBJECT_TEACHER':'')).map(s=>({id:s.id,label:`${s.display_name} · ${prettyRole[s.role]||s.role}`}))),[staff,form.kind]);
  const subjectOptions=useMemo(()=>choose(subjects.map(s=>({id:s.id,label:`${s.code} · ${s.name}`}))),[subjects]);
  const currentTitle=sections.find(x=>x.key===page)?.label||'Tổng quan';
  const show=(str:string)=>str.toLocaleLowerCase('vi').includes(search.toLocaleLowerCase('vi'));
  const rowMatches=(...parts:unknown[])=>parts.some(x=>show(String(x??'')));

  async function submit(e:FormEvent){e.preventDefault();switch(page){
    case 'years':return create('/api/v1/academic-years/',form,'Đã tạo năm học.');
    case 'subjects':return create('/api/v1/subjects/',form,'Đã tạo môn học.');
    case 'staff':return create('/api/v1/staff/',form,'Đã tạo hồ sơ nhân sự. Tài khoản CHƯA đăng nhập được cho đến khi hoàn thành quy trình mời/kích hoạt.');
    case 'classrooms':return create('/api/v1/classrooms/',{...form,grade_level:Number(form.grade_level)},'Đã tạo lớp học.');
    case 'students':return create('/api/v1/students/',{...form,date_of_birth:form.date_of_birth||null},'Đã tạo hồ sơ học sinh.');
    case 'enrollments':return create('/api/v1/enrollments/',{student_id:form.student_id,classroom_id:form.classroom_id},'Đã phân lớp học sinh.');
    case 'guardians': return form.mode==='link'
      ? create('/api/v1/guardian-links/',{student_id:form.student_id,guardian_id:form.guardian_id,relation:form.relation||'GUARDIAN'},'Đã tạo liên kết chờ xác minh.')
      : create('/api/v1/guardian-accounts/',{username:form.username,display_name:form.display_name},'Đã tạo tài khoản phụ huynh chưa kích hoạt.');
    case 'assignments':return create('/api/v1/teacher-assignments/',{teacher_id:form.teacher_id,classroom_id:form.classroom_id,
        kind:form.kind, ...(form.kind==='SUBJECT'?{subject_id:form.subject_id}:{})},'Đã phân công giáo viên.');
    default:return;
  }}

  function createForm(){return <form className="create-form" onSubmit={submit}><fieldset disabled={busy}><div className="form-grid">
    {page==='years'&&<><Field label="Tên năm học" name="label" value={form.label||''} onChange={change} placeholder="2026–2027"/>
      <Field label="Ngày bắt đầu" name="starts_on" type="date" value={form.starts_on||''} onChange={change}/>
      <Field label="Ngày kết thúc" name="ends_on" type="date" value={form.ends_on||''} onChange={change}/></>}
    {page==='subjects'&&<><Field label="Mã môn học" name="code" value={form.code||''} onChange={change} placeholder="MATH"/>
      <Field label="Tên môn học" name="name" value={form.name||''} onChange={change} placeholder="Toán"/></>}
    {page==='staff'&&<><Field label="Username mới" name="username" value={form.username||''} onChange={change} placeholder="gv_nguyenvana"/>
      <Field label="Họ và tên" name="display_name" value={form.display_name||''} onChange={change}/>
      <Field label="Email (nếu có)" name="email" type="email" value={form.email||''} onChange={change} required={false}/>
      <Field label="Vai trò" name="role" value={form.role||''} onChange={change} options={Object.entries(prettyRole).map(([id,label])=>({id,label}))}/></>}
    {page==='classrooms'&&<><Field label="Năm học" name="year" value={form.year||''} onChange={change} options={yearOptions}/>
      <Field label="Mã lớp" name="code" value={form.code||''} onChange={change} placeholder="8A2"/>
      <Field label="Khối lớp" name="grade_level" value={form.grade_level||''} onChange={change} options={[6,7,8,9].map(n=>({id:String(n),label:`Khối ${n}`}))}/></>}
    {page==='students'&&<><Field label="Mã học sinh" name="student_code" value={form.student_code||''} onChange={change} placeholder="HS002"/>
      <Field label="Họ và tên" name="full_name" value={form.full_name||''} onChange={change}/>
      <Field label="Ngày sinh (nếu có)" name="date_of_birth" type="date" value={form.date_of_birth||''} onChange={change} required={false}/></>}
    {page==='enrollments'&&<><Field label="Học sinh" name="student_id" value={form.student_id||''} onChange={change} options={studentOptions}/>
      <Field label="Lớp" name="classroom_id" value={form.classroom_id||''} onChange={change} options={classOptions}/></>}
    {page==='guardians'&&<><Field label="Nghiệp vụ" name="mode" value={form.mode||''} onChange={change} options={[
      {id:'account',label:'Tạo tài khoản phụ huynh'},{id:'link',label:'Liên kết phụ huynh với học sinh'}]}/>
      {form.mode==='account'&&<><Field label="Tên đăng nhập" name="username" value={form.username||''} onChange={change}/>
      <Field label="Họ và tên phụ huynh" name="display_name" value={form.display_name||''} onChange={change}/></>}
      {form.mode==='link'&&<><Field label="Học sinh" name="student_id" value={form.student_id||''} onChange={change} options={studentOptions}/>
      <Field label="Phụ huynh" name="guardian_id" value={form.guardian_id||''} onChange={change} options={guardians.map(x=>({id:x.id,label:x.display_name}))}/>
      <Field label="Quan hệ" name="relation" value={form.relation||''} onChange={change} options={[
      {id:'MOTHER',label:'Mẹ'},{id:'FATHER',label:'Bố'},{id:'GUARDIAN',label:'Người giám hộ'}]}/></>}</>}
    {page==='assignments'&&<><Field label="Giáo viên" name="teacher_id" value={form.teacher_id||''} onChange={change} options={staffOptions}/>
      <Field label="Lớp" name="classroom_id" value={form.classroom_id||''} onChange={change} options={classOptions}/>
      <Field label="Loại phân công" name="kind" value={form.kind||''} onChange={change} options={[{id:'HOMEROOM',label:'Chủ nhiệm'}, {id:'SUBJECT',label:'Bộ môn'}]}/>
      {form.kind==='SUBJECT'&&<Field label="Môn học" name="subject_id" value={form.subject_id||''} onChange={change} options={subjectOptions}/>}</>}
    </div><div className="form-actions"><button type="button" className="btn secondary" onClick={()=>setShowForm(false)}>Hủy</button>
      <button type="submit" className="btn primary" disabled={busy}>Lưu thông tin</button></div></fieldset></form>}

  function table(headings:string[],rows:ReactNode[][]){return <div className="table-wrap"><table><thead><tr>{headings.map(h=><th key={h}>{h}</th>)}</tr></thead>
    <tbody>{rows.length?rows.map((cells,i)=><tr key={i}>{cells.map((cell,j)=><td key={j}>{cell}</td>)}</tr>):
    <tr><td colSpan={headings.length} className="empty">Chưa có dữ liệu phù hợp.</td></tr>}</tbody></table></div>}
  function listing(){switch(page){
    case 'years':return table(['Năm học','Bắt đầu','Kết thúc'],years.filter(x=>rowMatches(x.label)).map(x=>[<strong>{x.label}</strong>,x.starts_on,x.ends_on]));
    case 'subjects':return table(['Mã môn','Tên môn'],subjects.filter(x=>rowMatches(x.code,x.name)).map(x=>[<code>{x.code}</code>,x.name]));
    case 'staff':return table(['Họ tên','Username','Vai trò','Tài khoản'],staff.filter(x=>rowMatches(x.username,x.display_name,x.role)).map(x=>[<strong>{x.display_name}</strong>,x.username,<Tag text={prettyRole[x.role]||x.role}/>,<Tag text={x.invitation_status==='NOT_SENT'?'Chưa kích hoạt':'Đã có mật khẩu'}/>]));
    case 'classrooms':return table(['Lớp','Khối','Năm học'],classrooms.filter(x=>rowMatches(x.code,x.grade_level)).map(x=>[<strong>{x.code}</strong>,`Khối ${x.grade_level}`,years.find(y=>y.id===x.year)?.label||'—']));
    case 'students':return table(['Mã học sinh','Họ và tên','Ngày sinh'],students.filter(x=>rowMatches(x.student_code,x.full_name)).map(x=>[<code>{x.student_code}</code>,<strong>{x.full_name}</strong>,x.date_of_birth||'—']));
    case 'enrollments':return table(['Học sinh','Lớp','Trạng thái','Thao tác'],enrollments.filter(x=>rowMatches(x.student_name,x.classroom_code)).map(x=>[x.student_name,x.classroom_code,
      <Tag text={x.is_active?'Chưa kết thúc':'Đã kết thúc'} tone={x.is_active?'green':'neutral'}/>, x.is_active?<button type="button" className="text-btn" disabled={busy} onClick={()=>void finish(`/api/v1/enrollments/${x.id}/end/`,'Đã kết thúc phân lớp.')}>Kết thúc</button>:'—']));
    case 'assignments':return table(['Giáo viên','Lớp','Phân công','Trạng thái','Thao tác'],assignments.filter(x=>rowMatches(x.teacher_name,x.classroom_code,x.subject_name)).map(x=>[
      x.teacher_name,x.classroom_code,x.kind==='HOMEROOM'?'Chủ nhiệm':`Bộ môn · ${x.subject_name||''}`,
      <Tag text={x.is_active?'Chưa kết thúc':'Đã kết thúc'} tone={x.is_active?'green':'neutral'}/>,x.is_active?<button type="button" className="text-btn" disabled={busy} onClick={()=>void finish(`/api/v1/teacher-assignments/${x.id}/end/`,'Đã kết thúc phân công.')}>Kết thúc</button>:'—']));
    case 'guardians':return <><div className="subsection-head">Liên kết phụ huynh - học sinh (cần kiểm tra giấy tờ trước khi xác minh)</div>
      {table(['Phụ huynh','Học sinh','Quan hệ','Xác minh','Thao tác'],guardianLinks.filter(x=>rowMatches(x.guardian_name,x.student_name)).map(x=>[
      x.guardian_name,x.student_name,x.relation,<Tag text={!x.is_active?'Đã ngừng':x.is_verified?'Đã xác minh':'Chờ xác minh'} tone={x.is_verified?'green':'amber'}/>,
      x.is_verified||!x.is_active?'—':<button type="button" className="text-btn" disabled={busy} onClick={()=>{
        if(window.confirm('Bạn xác nhận đã kiểm tra bằng chứng giám hộ ngoài hệ thống?'))void create(`/api/v1/guardian-links/${x.id}/verify/`,{evidence_checked:true},'Đã xác minh quan hệ giám hộ.');
      }}>Xác minh</button>] ))}
      <div className="subsection-head">Tài khoản phụ huynh</div>
      {table(['Họ tên','Username','Tài khoản'],guardians.filter(x=>rowMatches(x.display_name,x.username)).map(x=>[x.display_name,x.username,<Tag text={x.invitation_status==='NOT_SENT'?'Chưa kích hoạt':'Đã có mật khẩu'}/>]))}</>;
    case 'audit':return table(['Thời gian','Thao tác','Đối tượng'],audit.filter(x=>rowMatches(x.action,x.target_type)).map(x=>[new Date(x.created_at).toLocaleString('vi-VN'),<code>{x.action}</code>,x.target_type]));
    default:return null;
  }}

  if(!user)return <div className="auth-page"><div className="auth-art"><div className="logo large">✦ <span>EduSphere<span className="accent">AI</span></span></div>
    <span className="caps">School Administration</span><h1>Một nơi để quản lý<br/>cả hành trình giáo dục.</h1>
    <p>School Administration Core · Sprint 1</p><div className="auth-pill">Pilot THCS · Dữ liệu giả lập</div></div>
    <main className="auth-panel"><form className="auth-card" onSubmit={login}><span className="caps">Chào mừng quay lại</span><h2>Đăng nhập Admin</h2>
      <p>Chỉ tài khoản School Admin mới có quyền quản lý dữ liệu của trường.</p>
      <Field label="Tên đăng nhập" name="username" value={username} onChange={(_,v)=>setUsername(v)}/>
      <Field label="Mật khẩu" name="password" type="password" value={password} onChange={(_,v)=>setPassword(v)}/>
      <button className="btn primary full" disabled={busy}>{busy?'Đang xác thực...':'Đăng nhập →'}</button>
      {error&&<Notice text={error} kind="error"/>}<p className="demo-hint">Demo: <strong>admin_a</strong> / <strong>DemoOnly!ChangeMe123</strong></p>
      <p className="hint">JWT chỉ lưu trong bộ nhớ tab. Phiên đăng nhập sẽ kết thúc khi tải lại trang.</p></form></main></div>;

  return <div className="shell"><aside className="sidebar"><div className="logo">✦ <span>EduSphere<span className="accent">AI</span></span></div>
    <span className="side-overline">SCHOOL WORKSPACE</span><div className="tenant-card"><div className="avatar">TH</div><div className="tenant-text">
      <span>Đang quản lý</span><select aria-label="Chọn trường" value={tenant} onChange={e=>{scope.current.invalidate();loadSequence.current+=1;clearData();setBusy(false);setTenant(e.target.value);}}>
      {membership.map(m=><option key={m.tenant_id} value={m.tenant_id}>{m.tenant}</option>)}</select></div></div>
    <nav aria-label="Điều hướng quản trị">{sections.map(s=><button type="button" key={s.key} disabled={busy} onClick={()=>navigate(s.key)} aria-current={page===s.key?'page':undefined} className={page===s.key?'nav-item active':'nav-item'}>
      <span className="nav-icon">{s.icon}</span>{s.label}</button>)}</nav>
    <div className="side-footer"><div className="status-indicator"/><span>Development · Sprint 1</span></div></aside>
    <div className="workspace"><header className="topbar"><span>EduSphere / <strong>{currentTitle}</strong></span><div className="top-right"><Tag text="PILOT" tone="amber"/>
      <span className="user-avatar">{(user.display_name||user.username).slice(0,1).toUpperCase()}</span><button className="logout" onClick={logout}>Đăng xuất</button></div></header>
      <main className="content"><div className="page-header"><div><span className="caps">QUẢN TRỊ NHÀ TRƯỜNG</span><h1>{currentTitle}</h1>
      <p>{currentTenant?.tenant||''} · Quản lý dữ liệu có phân quyền</p></div><div className="header-actions">
      <button type="button" onClick={()=>void reload()} className="btn secondary" disabled={busy}>↻ Làm mới</button>
      {!['overview','audit'].includes(page)&&<button type="button" className="btn primary" disabled={busy} onClick={()=>{setForm({});setShowForm(!showForm);}}>＋ Thêm mới</button>}</div></div>
      {busy&&<p role="status">Đang xử lý dữ liệu…</p>}
      {error&&<Notice kind="error" text={error}/>} {success&&<Notice kind="success" text={success}/>}
      {page==='overview'?<><div className="stat-grid">{[
        ['Học sinh',dashboard?.students,'♧'],['Lớp học',dashboard?.classes,'▣'],
        ['Phân công giáo viên',dashboard?.active_assignments,'⌁'],['Năm học',dashboard?.academic_years,'▤'],
      ].map(([label,count,icon])=><article className="stat-card" key={String(label)}><span className="stat-icon">{icon}</span>
        <div className="stat-number">{count??'—'}</div><div className="stat-label">{label}</div></article>)}</div>
      <div className="overview-grid"><section className="panel"><h2>Khởi động trường THCS</h2><p>Thứ tự cấu hình đề xuất để dữ liệu luôn nhất quán.</p>
        <ol className="checklist"><li>Tạo năm học hiện hành</li><li>Thêm danh mục môn học</li><li>Khởi tạo tài khoản giáo viên</li><li>Tạo lớp theo từng khối</li>
        <li>Nhập danh sách học sinh</li><li>Phân lớp và phân công giáo viên</li></ol></section>
      <section className="panel muted-panel"><div className="round-icon">◎</div><h2>Quy tắc bảo mật</h2>
        <p>Mọi dữ liệu đều gắn với tenant. Admin chỉ được thao tác trên trường đã được cấp membership hợp lệ.</p>
        <Tag text="RBAC + ReBAC"/><p className="small-note">Tài khoản nhân sự mới cần quy trình kích hoạt an toàn trước khi sử dụng.</p></section></div></>:
        <section className="panel data-panel">{showForm&&<div className="form-wrapper"><h2>Tạo {currentTitle.toLowerCase()}</h2>{createForm()}</div>}
        <div className="table-header"><div><h2>Danh sách {currentTitle.toLowerCase()}</h2><p>Kết quả theo phạm vi trường được chọn.</p></div>
        <label className="search"><span>⌕</span><input aria-label="Tìm kiếm" placeholder="Tìm kiếm..." value={search} onChange={e=>setSearch(e.target.value)}/></label></div>
        {listing()}<p className="pagination-note">Danh sách API hiện giới hạn 100–500 bản ghi tùy module. Phân trang server-side sẽ cần bổ sung trước pilot quy mô toàn trường.</p></section>}
      <footer className="content-footer">EduSphere AI · Phase 1 / Sprint 1 · Không sử dụng dữ liệu học sinh thật</footer></main></div></div>;
}
