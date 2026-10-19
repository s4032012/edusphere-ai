import {useState,useRef,useEffect,type FormEvent} from 'react';
import {ApiError,createRequestScope,createApi,membershipsFor,ROLES,type CurrentUser,type Student} from '@edusphere/api-client';
const api=createApi(import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000');
const allowed=ROLES.admin;
export default function App() {
  const [username,setUsername]=useState('admin_a');
  const [password,setPassword]=useState('');const [token,setToken]=useState('');
  const [user,setUser]=useState<CurrentUser|null>(null);const [tenant,setTenant]=useState('');
  const [students,setStudents]=useState<Student[]>([]);const [busy,setBusy]=useState(false);const [error,setError]=useState('');
  const scope=useRef(createRequestScope());
  useEffect(()=>{
    if(!user)return;
    const timer=setTimeout(()=>{logout();setError('Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.');}, Math.max(0,user.session_expires_at*1000-Date.now()));
    return ()=>clearTimeout(timer);
  },[user]);
  const available=user?membershipsFor(user,allowed):[];
  async function login(e:FormEvent){e.preventDefault();setError('');setBusy(true);
    try{const pair=await api.login(username,password);const me=await api.me(pair.access);const roles=membershipsFor(me,allowed);
      if(!roles.length){setError('Tài khoản không có quyền vào ứng dụng này.');return;}
      scope.current.invalidate();setPassword('');setToken(pair.access);setUser(me);setTenant(roles[0].tenant_id);setStudents([]);
    }catch(err){setError(err instanceof Error?err.message:'Không thể đăng nhập');}finally{setBusy(false);}
  }
  async function load(){const current=scope.current.capture();setError('');setBusy(true);setStudents([]);
    try{const rows=await api.students(token,tenant);if(current())setStudents(rows);}
    catch(err){if(current()){if(err instanceof ApiError&&err.status===401)logout();setError(err instanceof ApiError&&err.status===401?'Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.':err instanceof Error?err.message:'Không thể tải dữ liệu');}}
    finally{if(current())setBusy(false);}}
  function logout(){scope.current.invalidate();setBusy(false);setToken('');setUser(null);setTenant('');setStudents([]);setPassword('');}
  return <div className="layout"><aside className="aside"><div className="brand">EduSphere <small>Admin Portal · Sprint 0 v2</small></div>
    <nav><div className="selected">Dashboard</div><div>Students · demo roster</div><div>Attendance · Phase 1</div><div>Grades · Phase 1</div><div>AI · Later</div></nav></aside>
    <main><div className="eyebrow">Pilot · One THCS · synthetic data</div><h1>Admin Portal</h1>
      <p>Prototype xác thực API và kiểm tra dữ liệu theo quan hệ thực tế. Không nhập dữ liệu học sinh thật.</p>
      {!user?<form className="card" onSubmit={login}><h2>Đăng nhập</h2>
        <div className="row"><label>Username<br/><input value={username} onChange={e=>setUsername(e.target.value)} required/></label>
        <label>Password<br/><input type="password" value={password} onChange={e=>setPassword(e.target.value)} required/></label>
        <button type="submit" disabled={busy}>Sign in</button></div>
        <p className="hint">Demo: admin_a / DemoOnly!ChangeMe123</p></form>
      :<><section className="card"><div className="row"><h2>Xin chào, {user.display_name}</h2><button className="secondary" onClick={logout}>Đăng xuất</button></div>
        <div className="row"><label>Trường học<br/><select value={tenant} onChange={e=>{scope.current.invalidate();setBusy(false);setError('');setTenant(e.target.value);setStudents([]);}}>
          {available.map(m=><option key={m.tenant_id+m.role} value={m.tenant_id}>{m.tenant} · {m.role}</option>)}</select></label>
          <button onClick={load} disabled={busy}>Xem danh sách học sinh</button></div>
      </section><section className="card"><h2>Student Roster · API scoped</h2>
        <div className="table-scroll"><table><thead><tr><th>Mã học sinh</th><th>Họ và tên</th><th>ID</th></tr></thead><tbody>
          {students.map(s=><tr key={s.id}><td><span className="tag">{s.student_code}</span></td><td>{s.full_name}</td><td className="hint">{s.id}</td></tr>)}
        </tbody></table></div>{students.length===0&&<p>Chưa tải danh sách hoặc lớp chưa có dữ liệu được phép xem.</p>}
      </section></>}
      {busy&&<p role="status">Đang tải…</p>}
      {error&&<p className="error" role="alert">{error}</p>}
      <p className="hint">Access token chỉ giữ trong bộ nhớ tab. Refresh token chưa được sử dụng; JWT/BFF production chưa hoàn thiện.</p>
    </main></div>;
}
