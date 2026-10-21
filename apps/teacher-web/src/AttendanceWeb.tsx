import {useEffect,useState,useRef} from 'react';
import {ApiError,createApi,createAttendanceApi,type AttendanceSessionDetail,type AttendanceMark,type Classroom,type LeaveRequest} from '@edusphere/api-client';
const url=import.meta.env.VITE_API_URL||'http://127.0.0.1:8000';
const api=createApi(url);const at=createAttendanceApi(url);
const localDate=()=>{const d=new Date();return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');};
export default function AttendanceWeb({token,tenant,onExpired}:{token:string;tenant:string;onExpired:()=>void}){
  const live=useRef(true), pending=useRef(false);
  useEffect(()=>{live.current=true;return()=>{live.current=false;};},[]);

  const [classes,setClasses]=useState<Classroom[]>([]),[classId,setClassId]=useState('');const [day,setDay]=useState(localDate());
  const [session,setSession]=useState<AttendanceSessionDetail|null>(null),[marks,setMarks]=useState<Record<string,AttendanceMark>>({});
  const [leaves,setLeaves]=useState<LeaveRequest[]>([]),[working,setWorking]=useState(false),[info,setInfo]=useState('');
  useEffect(()=>{setSession(null);void run(async()=>{const v=await api.classrooms(token,tenant);if(live.current){setClasses(v);setClassId(v[0]?.id||'');}});},[token,tenant]);
  async function run(action:()=>Promise<void>){if(pending.current)return;pending.current=true;setWorking(true);setInfo('');try{await action();}catch(e){if(live.current){if(e instanceof ApiError&&e.status===401)onExpired();else setInfo(e instanceof Error?e.message:'Có lỗi xảy ra');}}finally{pending.current=false;if(live.current)setWorking(false);}}
  async function reload(id:string){const s=await at.detail(token,tenant,id);setSession(s);setMarks(Object.fromEntries(s.roster.filter(r=>r.mark!==null).map(r=>[r.id,r.mark])) as Record<string,AttendanceMark>);}
  return <section className="card"><h2>Điểm danh theo lớp · Sprint 2</h2>
    <div className="row"><label>Lớp<br/><select disabled={working} value={classId} onChange={e=>{setClassId(e.target.value);setSession(null);}}>
      {classes.map(c=><option key={c.id} value={c.id}>{c.code}</option>)}</select></label>
      <label>Ngày điểm danh<br/><input type="date" disabled={working} value={day} onChange={e=>{setDay(e.target.value);setSession(null);setMarks({});}}/></label>
      <button disabled={working||!classId} onClick={()=>run(async()=>{const v=await at.start(token,tenant,classId,day);await reload(v.id);})}>Mở phiên điểm danh</button>
      <button className="secondary" disabled={working} onClick={()=>run(async()=>setLeaves(await at.leaves(token,tenant)))}>Xem đơn xin nghỉ</button></div>
    {session&&<><p>Trạng thái: <strong>{session.state}</strong> · Ngày {session.attendance_date}</p>
      <div className="table-scroll"><table><thead><tr><th>Mã HS</th><th>Học sinh</th><th>Điểm danh</th></tr></thead><tbody>
      {session.roster.map(row=><tr key={row.id}><td>{row.student_code}</td><td>{row.full_name}</td><td>
        <select aria-label={`Điểm danh ${row.full_name}`} disabled={working||session.state!=='DRAFT'} value={marks[row.id]||''} onChange={e=>setMarks(prev=>({...prev,[row.id]:e.target.value as AttendanceMark}))}>
          <option value="">Chưa điểm danh</option><option value="PRESENT">Có mặt</option><option value="ABSENT">Vắng</option><option value="LATE">Đi muộn</option>
        </select>{row.effective_status==='EXCUSED_ABSENCE'&&<span> · Đã có đơn duyệt</span>}</td></tr>)}
      </tbody></table></div>
      {session.state==='DRAFT'&&<div className="row"><button disabled={working||!session.roster.some(r=>marks[r.id])} onClick={()=>run(async()=>{
        await at.save(token,tenant,session.id,session.roster.filter(r=>marks[r.id]).map(r=>({student_id:r.id,mark:marks[r.id],note:r.note})));await reload(session.id);setInfo('Đã lưu điểm danh.');})}>Lưu</button>
        <button disabled={working} onClick={()=>run(async()=>{if(!session.roster.length||session.roster.some(r=>!marks[r.id]))throw new Error('Cần điểm danh đủ học sinh trước khi nộp.');await at.save(token,tenant,session.id,session.roster.map(r=>({student_id:r.id,mark:marks[r.id],note:r.note})));await at.submit(token,tenant,session.id);await reload(session.id);setInfo('Đã nộp điểm danh.');})}>Nộp điểm danh</button></div>}
    </>}
    {leaves.filter(l=>l.state==='PENDING').map(l=><div className="row" key={l.id}><span>{l.student_name}: {l.from_date} → {l.through_date}. {l.reason}</span>
      <button disabled={working} onClick={()=>run(async()=>{await at.decide(token,tenant,l.id,'approve');setLeaves(await at.leaves(token,tenant));})}>Duyệt</button>
      <button disabled={working} onClick={()=>run(async()=>{await at.decide(token,tenant,l.id,'reject');setLeaves(await at.leaves(token,tenant));})}>Từ chối</button></div>)}
    {!!info&&<p role="alert">{info}</p>}
  </section>;
}
