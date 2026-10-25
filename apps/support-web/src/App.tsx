import {useEffect,useRef,useState,type FormEvent} from 'react';
import {createApi,membershipsFor,type CurrentUser} from '@edusphere/api-client';
import {Communications} from '@edusphere/communications-ui';
import './style.css';
const base=import.meta.env.VITE_API_URL||'http://127.0.0.1:8000',api=createApi(base);
export default function App(){
 const [username,setUsername]=useState('support_a'),[password,setPassword]=useState(''),[token,setToken]=useState(''),[tenant,setTenant]=useState('');
 const [user,setUser]=useState<CurrentUser|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const pending=useRef(false);
 function logout(){setToken('');setUser(null);setTenant('');setPassword('');setError('');}
 function expire(){logout();setError('Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.');}
 useEffect(()=>{if(!user)return;const timer=setTimeout(expire,Math.max(0,user.session_expires_at*1000-Date.now()));return()=>clearTimeout(timer);},[user]);
 async function login(e:FormEvent){e.preventDefault();if(pending.current)return;pending.current=true;setBusy(true);setError('');
  try{const pair=await api.login(username,password),me=await api.me(pair.access),available=membershipsFor(me,['SUPPORT_STAFF']);
   if(!available.length)throw new Error('Tài khoản không có quyền nhân viên hỗ trợ.');setPassword('');setToken(pair.access);setUser(me);setTenant(available[0].tenant_id);
  }catch(e){setError(e instanceof Error?e.message:'Không thể đăng nhập');}finally{pending.current=false;setBusy(false);}}
 return <main className="page"><header><h1>EduSphere Support Desk</h1><p>Tiếp nhận và xử lý yêu cầu hỗ trợ của phụ huynh.</p></header>
 {!user?<form className="panel" onSubmit={login}><h2>Đăng nhập nhân viên hỗ trợ</h2><label>Tài khoản<input aria-label="Username" required value={username} onChange={e=>setUsername(e.target.value)}/></label><label>Mật khẩu<input aria-label="Password" required type="password" value={password} onChange={e=>setPassword(e.target.value)}/></label><button disabled={busy}>Đăng nhập</button></form>:
 <><section className="panel"><h2>{user.display_name||user.username}</h2><label>Trường<select value={tenant} onChange={e=>setTenant(e.target.value)}>{membershipsFor(user,['SUPPORT_STAFF']).map(m=><option key={m.tenant_id} value={m.tenant_id}>{m.tenant}</option>)}</select></label><button onClick={logout}>Đăng xuất</button></section>
 <Communications key={token+tenant} baseUrl={base} token={token} tenant={tenant} userId={user.id} mode="support" onExpired={expire}/></>}
 {!!error&&<p role="alert" className="error">{error}</p>}<footer>Prototype Sprint 5 · Dữ liệu demo</footer></main>;
}
