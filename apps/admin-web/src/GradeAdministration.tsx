import {useEffect,useState,useRef} from 'react';
import {ApiError,createGradesApi,type GradeBook,type GradeBookDetail,type GradeRevision,type Classroom,type Subject,type GradeMode} from '@edusphere/api-client';
const api=createGradesApi(import.meta.env.VITE_API_URL||'http://127.0.0.1:8000');
export function GradeAdministration({token,tenant,classrooms,subjects,onExpired}:{token:string;tenant:string;classrooms:Classroom[];subjects:Subject[];onExpired:()=>void}){
  const live=useRef(true), pending=useRef(false), selection=useRef(0);
  useEffect(()=>{live.current=true;return()=>{live.current=false;selection.current++;};},[]);
  function failed(e:unknown){if(!live.current)return;if(e instanceof ApiError&&e.status===401)onExpired();else setError(e instanceof Error?e.message:'Không thể tải dữ liệu.');}

  const [books,setBooks]=useState<GradeBook[]>([]),[revisions,setRevisions]=useState<GradeRevision[]>([]);
  const [cls,setCls]=useState(''),[subject,setSubject]=useState(''),[semester,setSemester]=useState<'1'|'2'>('1');
  const [mode,setMode]=useState<GradeMode>('SCORE'),[regular,setRegular]=useState(2);
  const [selected,setSelected]=useState(''),[detail,setDetail]=useState<GradeBookDetail|null>(null),[error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  async function reload(){const [books,revisions]=await Promise.all([api.books(token,tenant),api.revisions(token,tenant)]);setBooks(books);setRevisions(revisions);}
  useEffect(()=>{setBooks([]);setSelected('');setDetail(null);void reload().catch(failed);},[token,tenant]);
  useEffect(()=>{let active=true;setDetail(null);if(selected)void api.book(token,tenant,selected).then(d=>{if(active)setDetail(d);}).catch(e=>{if(active)failed(e);});return()=>{active=false;};},[selected,token,tenant]);
  async function action(run:()=>Promise<unknown>){if(pending.current)return;pending.current=true;setBusy(true);setError('');try{await run();await reload();if(selected)setDetail(await api.book(token,tenant,selected));}
    catch(e){failed(e);}finally{pending.current=false;if(live.current)setBusy(false);}}
  return <section className="panel"><h2>Học vụ · Quản lý sổ điểm</h2><p>Thiết lập số cột đánh giá thường xuyên theo kế hoạch môn học; không tự suy luận từ cấp lớp. Công bố điểm sau khi được giáo viên khóa.</p>
    <div className="form-grid"><label>Lớp<select aria-label="Chọn lớp" value={cls} onChange={e=>setCls(e.target.value)}><option value="">Chọn lớp</option>{classrooms.map(c=><option key={c.id} value={c.id}>{c.code}</option>)}</select></label>
      <label>Môn<select aria-label="Chọn môn" value={subject} onChange={e=>setSubject(e.target.value)}><option value="">Chọn môn</option>{subjects.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
      <label>Học kỳ<select aria-label="Học kỳ" value={semester} onChange={e=>setSemester(e.target.value as '1'|'2')}><option value="1">I</option><option value="2">II</option></select></label>
      <label>Hình thức<select aria-label="Hình thức đánh giá" value={mode} onChange={e=>{const m=e.target.value as GradeMode;setMode(m);if(m==='COMMENT')setRegular(2);}}>
        <option value="SCORE">Điểm số</option><option value="COMMENT">Nhận xét</option></select></label>
      <label>Số cột thường xuyên<select aria-label="Cột thường xuyên" value={regular} onChange={e=>setRegular(Number(e.target.value))} disabled={mode==='COMMENT'}>
        <option value={2}>2</option>{mode==='SCORE'&&<><option value={3}>3</option><option value={4}>4</option></>}</select></label></div>
      <button className="btn primary" disabled={busy||!cls||!subject} onClick={()=>void action(()=>api.createBook(token,tenant,{classroom_id:cls,subject_id:subject,semester,mode,regular_required:regular}))}>Tạo sổ điểm</button>
    <h3>Danh sách sổ điểm</h3><button className="btn secondary" disabled={busy} onClick={()=>void action(async()=>{})}>Làm mới</button><div className="table-wrap"><table><thead><tr><th>Lớp</th><th>Môn</th><th>HK</th><th>Hình thức</th><th>Thao tác</th></tr></thead><tbody>
      {books.map(b=><tr key={b.id}><td>{b.classroom_code}</td><td>{b.subject_name}</td><td>{b.semester}</td><td>{b.mode==='SCORE'?'Điểm':'Nhận xét'}</td><td>
        <button className="text-btn" disabled={busy} onClick={()=>setSelected(b.id)}>Xem/công bố</button></td></tr>)}</tbody></table></div>
    {detail&&<><h3>{detail.classroom_code} · {detail.subject_name} · HK{detail.semester}</h3>
      {detail.assessments.map(a=><div key={a.id} className="panel"><strong>{a.kind} {a.slot}: {a.title}</strong> · {a.state} · {a.entries?.length||0} học sinh
        {a.state==='LOCKED'&&<button className="btn primary" disabled={busy} onClick={()=>{if(window.confirm(`Công bố ${a.title} cho phụ huynh/học sinh?`))void action(()=>api.publish(token,tenant,a.id));}}>Công bố cho phụ huynh</button>}</div>)}</>}
    <h3>Yêu cầu điều chỉnh điểm</h3>
    {revisions.filter(r=>r.state==='PENDING').map(r=><div key={r.id} className="panel"><p><strong>{r.student_name} · {r.classroom_code} · {r.subject_name} · {r.assessment_title}</strong></p><p>Phiên bản {r.from_version} · {r.old_score??r.old_result??'—'} → {r.proposed_score??r.proposed_result}</p>
      <p>Lý do: {r.reason}</p><button className="btn primary" disabled={busy} onClick={()=>{if(window.confirm(`Duyệt sửa điểm ${r.student_name} — ${r.subject_name}, ${r.assessment_title}?`))void action(()=>api.decideRevision(token,tenant,r.id,'approve'));}}>Phê duyệt</button>
      <button className="btn secondary" disabled={busy} onClick={()=>void action(()=>api.decideRevision(token,tenant,r.id,'reject'))}>Từ chối</button></div>)}
    {error&&<p className="notice error" role="alert">{error}</p>}
  </section>;
}
