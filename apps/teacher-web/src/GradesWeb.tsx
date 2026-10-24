import {useEffect,useState,useRef} from 'react';
import {ApiError,createGradesApi,type GradeBook,type GradeBookDetail,type GradeRevision,type AssessmentKind} from '@edusphere/api-client';
const api=createGradesApi(import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000');
const states:Record<string,string>={DRAFT:'Đang nhập',LOCKED:'Đã khóa',PUBLISHED:'Đã công bố'};
const kinds:Record<string,string>={TX:'Thường xuyên',GK:'Giữa kỳ',CK:'Cuối kỳ'};
export function GradesWeb({token,tenant,onExpired}:{token:string;tenant:string;onExpired:()=>void}){
  const live=useRef(true), pending=useRef(false), selection=useRef(0);
  useEffect(()=>{live.current=true;return()=>{live.current=false;selection.current++;};},[]);
  function failed(e:unknown){if(!live.current)return;if(e instanceof ApiError&&e.status===401)onExpired();else setInfo(e instanceof Error?e.message:'Không thể tải dữ liệu.');}

  const [books,setBooks]=useState<GradeBook[]>([]),[selected,setSelected]=useState('');
  const [book,setBook]=useState<GradeBookDetail|null>(null),[revisions,setRevisions]=useState<GradeRevision[]>([]);
  const [kind,setKind]=useState<AssessmentKind>('TX'),[slot,setSlot]=useState(1),[title,setTitle]=useState('');
  const [values,setValues]=useState<Record<string,string>>({}),[reason,setReason]=useState(''),[editEntry,setEditEntry]=useState('');
  const [busy,setBusy]=useState(false),[info,setInfo]=useState('');
  async function loadBooks(){const result=await api.books(token,tenant);setBooks(result);setSelected(id=>id||result[0]?.id||'');}
  async function loadBook(id:string){const ticket=++selection.current;if(!id){setBook(null);return;} const result=await api.book(token,tenant,id);if(!live.current||ticket!==selection.current)return;setBook(result);
    const next:Record<string,string>={};for(const a of result.assessments)for(const e of a.entries||[])next[a.id+':'+e.student_id]=result.mode==='SCORE'?e.score||'':e.result||'';
    setValues(next);}
  useEffect(()=>{setBooks([]);setBook(null);setSelected('');void loadBooks().catch(failed);},[token,tenant]);
  useEffect(()=>{void loadBook(selected).catch(failed);},[selected,token,tenant]);
  async function exec(fn:()=>Promise<unknown>){if(pending.current)return;pending.current=true;setBusy(true);setInfo('');try{await fn();setInfo('Đã cập nhật.');await loadBook(selected);setRevisions(await api.revisions(token,tenant));}
    catch(e){failed(e);}finally{pending.current=false;if(live.current)setBusy(false);}}
  return <section className="card"><h2>Sổ điểm · Sprint 3</h2>
    <p className="hint">Chỉ hiển thị môn/lớp đang được phân công. Công bố điểm là quyền của giáo vụ/quản trị trường.</p>
    <div className="row"><label>Sổ điểm<br/><select value={selected} disabled={busy} onChange={e=>{selection.current++;setBook(null);setEditEntry('');setReason('');setValues({});setSelected(e.target.value);}}>
      {books.map(b=><option value={b.id} key={b.id}>{b.classroom_code} · {b.subject_name} · Học kỳ {b.semester}</option>)}
    </select></label><button onClick={()=>void exec(loadBooks)} disabled={busy}>Làm mới</button></div>
    {book&&<>{book.can_edit&&<div className="row"><label>Loại đánh giá<br/><select disabled={busy} value={kind} onChange={e=>{setKind(e.target.value as AssessmentKind);setSlot(1);}}>
      <option value="TX">Thường xuyên</option><option value="GK">Giữa kỳ</option><option value="CK">Cuối kỳ</option></select></label>
      <label>Slot<br/><input disabled={busy} type="number" min={1} max={kind==='TX'?book.regular_required:1} value={slot} onChange={e=>setSlot(Number(e.target.value))}/></label>
      <label>Tên đánh giá<br/><input disabled={busy} value={title} onChange={e=>setTitle(e.target.value)}/></label>
      <button disabled={busy||title.trim().length<2} onClick={()=>void exec(async()=>{await api.createAssessment(token,tenant,book.id,kind,slot,title);setTitle('');})}>Tạo cột điểm</button></div>}
      {book.assessments.map(a=><section key={a.id} className="card"><div className="row"><h3>{kinds[a.kind]} {a.slot} · {a.title} ({states[a.state]})</h3>
        {book.can_edit&&a.state==='DRAFT'&&<button disabled={busy} onClick={()=>{if(window.confirm('Lưu các giá trị hiện tại và khóa cột? Sau khi khóa, sửa điểm cần yêu cầu điều chỉnh.'))void exec(async()=>{await api.saveGrades(token,tenant,a.id,(a.entries||[]).map(e=>({student_id:e.student_id,...(book.mode==='SCORE'?{score:values[a.id+':'+e.student_id]}:{result:values[a.id+':'+e.student_id]})})));await api.lock(token,tenant,a.id);});}}>Khóa cột</button>}</div>
        <div style={{overflowX:'auto'}}><table><thead><tr><th>Học sinh</th><th>{book.mode==='SCORE'?'Điểm (0–10)':'Nhận xét'}</th><th>Điều chỉnh</th></tr></thead><tbody>
        {(a.entries||[]).map(e=><tr key={e.student_id}><td>{e.student_code} · {e.full_name}</td><td>
          {book.can_edit&&a.state==='DRAFT'?(book.mode==='SCORE'?<input disabled={busy} type="number" min="0" max="10" step="0.1" aria-label={'Điểm '+e.full_name}
            value={values[a.id+':'+e.student_id]??''} onChange={ev=>setValues(v=>({...v,[a.id+':'+e.student_id]:ev.target.value}))}/>:
          <select disabled={busy} aria-label={'Nhận xét '+e.full_name} value={values[a.id+':'+e.student_id]??''} onChange={ev=>setValues(v=>({...v,[a.id+':'+e.student_id]:ev.target.value}))}>
            <option value="">Chọn...</option><option value="PASS">Đạt</option><option value="FAIL">Chưa đạt</option></select>)
          :book.mode==='SCORE'?e.score||'—':e.result||'—'}</td><td>
          {book.can_edit&&e.id&&a.state!=='DRAFT'&&<button className="secondary" disabled={busy} onClick={()=>{setEditEntry(e.id||'');setReason('');}}>Đề nghị sửa</button>}</td></tr>)}</tbody></table></div>
        {book.can_edit&&a.state==='DRAFT'&&<button disabled={busy} onClick={()=>void exec(()=>api.saveGrades(token,tenant,a.id,(a.entries||[]).map(e=>({student_id:e.student_id,
          ...(book.mode==='SCORE'?{score:values[a.id+':'+e.student_id]}:{result:values[a.id+':'+e.student_id]})}))))}>Lưu cả lớp</button>}
      </section>)}
      {editEntry&&<div className="card"><h3>Đề nghị điều chỉnh điểm đã khóa</h3><input disabled={busy} aria-label="Điểm/kết quả đề xuất" placeholder={book.mode==='SCORE'?'Điểm mới 0–10':'PASS / FAIL / EXEMPT'} value={values['rev:'+editEntry]||''} onChange={e=>setValues(v=>({...v,['rev:'+editEntry]:e.target.value}))}/>
        <input disabled={busy} aria-label="Lý do" placeholder="Lý do điều chỉnh (ít nhất 10 ký tự)" value={reason} onChange={e=>setReason(e.target.value)}/>
        <button disabled={busy||reason.trim().length<10} onClick={()=>void exec(async()=>{await api.requestRevision(token,tenant,editEntry,
          {...(book.mode==='SCORE'?{score:values['rev:'+editEntry]}:{result:values['rev:'+editEntry]}),reason});setEditEntry('');})}>Gửi yêu cầu</button>
        <button className="secondary" onClick={()=>setEditEntry('')}>Hủy</button></div>}
      <button className="secondary" disabled={busy} onClick={()=>void exec(async()=>{setRevisions(await api.revisions(token,tenant));})}>Xem yêu cầu chỉnh sửa</button>
      {revisions.map(r=><p key={r.id} className="hint">{r.state} · {r.reason} · {r.old_score??'—'} → {r.proposed_score??r.proposed_result}</p>)}
    </>}
    {!books.length&&<p className="hint">Chưa có sổ điểm được cấu hình hoặc chưa được phân công môn.</p>}
    {info&&<p role="status">{info}</p>}</section>;
}
