import {useEffect,useRef,useState} from 'react';
import {ApiError,createApi,createHomeworkApi,type Homework,type HomeworkRoster,type Classroom} from '@edusphere/api-client';
const origin=import.meta.env.VITE_API_URL||'http://127.0.0.1:8000';
const hw=createHomeworkApi(origin),core=createApi(origin);
type Subject={id:string;name:string};
const labels:Record<string,string>={DRAFT:'Nháp',PUBLISHED:'Đã giao',CLOSED:'Đã đóng',SUBMITTED:'Đã nộp',RETURNED:'Đã trả bài',NOT_SUBMITTED:'Chưa nộp',OVERDUE:'Quá hạn'};
function localDate(iso:string){const d=new Date(iso);return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16);}
export function HomeworkWeb({token,tenant,canCreate,onExpired}:{token:string;tenant:string;canCreate:boolean;onExpired:()=>void}){
  const live=useRef(true),pending=useRef(false),selection=useRef(0);
  const [tasks,setTasks]=useState<Homework[]>([]),[classes,setClasses]=useState<Classroom[]>([]),[subjects,setSubjects]=useState<Subject[]>([]);
  const [classId,setClassId]=useState(''),[subjectId,setSubjectId]=useState('');
  const [title,setTitle]=useState(''),[instructions,setInstructions]=useState(''),[dueAt,setDueAt]=useState(''),[allowLate,setAllowLate]=useState(false),[editing,setEditing]=useState('');
  const [roster,setRoster]=useState<HomeworkRoster|null>(null),[filter,setFilter]=useState('');
  const [feedback,setFeedback]=useState<Record<string,string>>({}),[scores,setScores]=useState<Record<string,string>>({});
  const [busy,setBusy]=useState(true),[notice,setNotice]=useState('');
  function failed(e:unknown){if(!live.current)return;if(e instanceof ApiError&&e.status===401)onExpired();else setNotice(e instanceof Error?e.message:'Không thể tải dữ liệu.');}
  useEffect(()=>{live.current=true;let active=true;
    Promise.all([hw.list(token,tenant),canCreate?core.classrooms(token,tenant):Promise.resolve([]),canCreate?core.adminGet<Subject[]>('/api/v1/subjects/',token,tenant):Promise.resolve([])])
      .then(([ts,cs,ss])=>{if(active){setTasks(ts);setClasses(cs);setSubjects(ss);setClassId(cs[0]?.id||'');setSubjectId(ss[0]?.id||'');}})
      .catch(e=>{if(active)failed(e);}).finally(()=>{if(active)setBusy(false);});
    return()=>{active=false;live.current=false;selection.current++;};},[token,tenant,canCreate]);
  async function run(action:()=>Promise<unknown>,rosterId=roster?.assignment.id){if(pending.current)return;pending.current=true;setBusy(true);setNotice('');++selection.current;
    try{await action();if(!live.current)return;const ts=await hw.list(token,tenant);if(!live.current)return;setTasks(ts);
      if(rosterId){const r=await hw.roster(token,tenant,rosterId);if(live.current)setRoster(r);}if(live.current)setNotice('Đã cập nhật.');
    }catch(e){if(live.current){setRoster(null);failed(e);}}finally{pending.current=false;if(live.current)setBusy(false);}}
  async function inspect(id:string){if(pending.current)return;const seq=++selection.current;setRoster(null);setNotice('');setBusy(true);
    try{const r=await hw.roster(token,tenant,id);if(live.current&&seq===selection.current){setRoster(r);setFeedback({});setScores({});}}
    catch(e){if(seq===selection.current)failed(e);}finally{if(live.current&&seq===selection.current)setBusy(false);}}
  function reset(){setEditing('');setTitle('');setInstructions('');setDueAt('');setAllowLate(false);}
  function edit(t:Homework){setEditing(t.id);setClassId(t.classroom_id);setSubjectId(t.subject_id);setTitle(t.title);setInstructions(t.instructions);setDueAt(localDate(t.due_at));setAllowLate(t.allow_late);}
  return <section className="card"><h2>Bài tập</h2><p className="hint">Điểm bài tập và nhận xét không tự cập nhật sổ điểm chính thức.</p>
    {canCreate&&<fieldset className="homework-compose" disabled={busy} style={{border:0,padding:0}}><legend>{editing?'Chỉnh sửa bài tập nháp':'Tạo bài tập'}</legend>
      <div className="row"><label>Lớp<select disabled={!!editing} value={classId} onChange={e=>setClassId(e.target.value)}>{classes.map(c=><option key={c.id} value={c.id}>{c.code}</option>)}</select></label>
        <label>Môn<select disabled={!!editing} value={subjectId} onChange={e=>setSubjectId(e.target.value)}>{subjects.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label></div>
      <label>Tiêu đề<input value={title} maxLength={160} onChange={e=>setTitle(e.target.value)}/></label>
      <label>Hạn nộp (giờ trên thiết bị)<input type="datetime-local" value={dueAt} onChange={e=>setDueAt(e.target.value)}/></label>
      <label>Hướng dẫn<textarea aria-label="Hướng dẫn" style={{width:'100%',minHeight:85}} value={instructions} maxLength={10000} onChange={e=>setInstructions(e.target.value)}/></label>
      <label className="homework-checkbox"><input type="checkbox" checked={allowLate} onChange={e=>setAllowLate(e.target.checked)}/> Cho phép nộp muộn trước khi đóng bài</label>
      <div className="row"><button disabled={!classId||!subjectId||!title.trim()||!instructions.trim()||!dueAt} onClick={()=>void run(async()=>{
        const data={title:title.trim(),instructions:instructions.trim(),due_at:new Date(dueAt).toISOString(),allow_late:allowLate};
        if(editing)await hw.edit(token,tenant,editing,data);else await hw.create(token,tenant,{...data,classroom_id:classId,subject_id:subjectId});
        if(live.current)reset();})}>{editing?'Lưu thay đổi':'Lưu nháp'}</button>{editing&&<button className="secondary" onClick={reset}>Hủy sửa</button>}</div>
    </fieldset>}
    {!canCreate&&<p>Chế độ theo dõi lớp: chỉ xem tiến độ và phản hồi.</p>}
    <div className="row"><label>Lọc trạng thái<select value={filter} onChange={e=>setFilter(e.target.value)}><option value="">Tất cả</option>{['DRAFT','PUBLISHED','CLOSED'].map(x=><option key={x} value={x}>{labels[x]}</option>)}</select></label>
      <button disabled={busy} className="secondary" onClick={()=>void run(async()=>{})}>Tải lại</button></div>
    {!busy&&!tasks.length&&<p>Chưa có bài tập được phép xem.</p>}
    <div style={{overflowX:'auto'}}><table><thead><tr><th>Bài tập</th><th>Lớp / môn</th><th>Hạn nộp</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>
      {tasks.filter(t=>!filter||t.state===filter).map(task=><tr key={task.id}><td>{task.title}</td><td>{task.classroom_code} · {task.subject_name}</td><td>{new Date(task.due_at).toLocaleString('vi-VN')}</td><td>{labels[task.state]}</td>
        <td><button disabled={busy} className="secondary" onClick={()=>void inspect(task.id)}>Xem bài nộp</button>
          {task.can_manage&&task.state==='DRAFT'&&<><button disabled={busy} className="secondary" onClick={()=>edit(task)}>Sửa nháp</button><button disabled={busy} onClick={()=>{if(window.confirm(`Giao “${task.title}” cho lớp ${task.classroom_code}?`))void run(()=>hw.publish(token,tenant,task.id));}}>Giao bài</button></>}
          {task.can_manage&&task.state==='PUBLISHED'&&<button disabled={busy} onClick={()=>{if(window.confirm(`Đóng “${task.title}”? Học sinh sẽ không thể sửa hoặc nộp thêm.`))void run(()=>hw.close(token,tenant,task.id));}}>Đóng bài</button>}</td></tr>)}</tbody></table></div>
    {roster&&<><h3>Tiến độ: {roster.assignment.title}</h3><p style={{whiteSpace:'pre-wrap'}}>{roster.assignment.instructions}</p><div style={{overflowX:'auto'}}><table><thead><tr><th>Học sinh</th><th>Trạng thái</th><th>Bài làm</th><th>Phản hồi</th></tr></thead><tbody>
      {roster.students.map(r=><tr key={r.student_id}><td>{r.student_code} · {r.full_name}</td><td>{labels[r.status]}{r.submission?.submitted_at&&<small><br/>{new Date(r.submission.submitted_at).toLocaleString('vi-VN')}{new Date(r.submission.submitted_at)>new Date(roster.assignment.due_at)?' · Nộp muộn':''}</small>}</td><td style={{whiteSpace:'pre-wrap',maxWidth:350,overflowWrap:'anywhere'}}>{r.submission?.content_text??'—'}</td><td>
        {roster.assignment.can_manage&&r.status==='SUBMITTED'&&r.submission&&<><input maxLength={3000} aria-label={'Nhận xét '+r.full_name} value={feedback[r.submission.id]||''} placeholder="Nhận xét" onChange={e=>setFeedback(v=>({...v,[r.submission!.id]:e.target.value}))}/>
          <input aria-label={'Điểm bài tập '+r.full_name} type="number" min={0} max={10} step="0.1" placeholder="0–10 (tùy chọn)" value={scores[r.submission.id]||''} onChange={e=>setScores(v=>({...v,[r.submission!.id]:e.target.value}))}/>
          <button disabled={busy||(!feedback[r.submission.id]?.trim()&&!scores[r.submission.id])} onClick={()=>{if(window.confirm(`Trả bài cho ${r.full_name}? Kết quả sẽ được khóa.`))void run(()=>hw.returnWork(token,tenant,r.submission!.id,feedback[r.submission!.id]||'',r.submission!.version,scores[r.submission!.id]));}}>Trả bài</button></>}
        {r.status==='RETURNED'&&<span>Điểm bài tập: {r.submission?.score??'—'} · {r.submission?.feedback||''}</span>}</td></tr>)}</tbody></table></div></>}
    {busy&&<p role="status">Đang tải…</p>}{notice&&<p role="status">{notice}</p>}</section>;
}
