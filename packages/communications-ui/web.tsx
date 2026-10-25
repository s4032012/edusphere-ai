import {communicationLabels as labels,ticketTransitions,type NoticeScope} from '@edusphere/api-client';
import {useCommunications,type Props} from './controller';
export function Communications(p:Props){
 const c=useCommunications(p),when=(s:string)=>new Date(s).toLocaleString('vi-VN');
 const action=(fn:()=>Promise<void>)=>()=>void c.run(fn);
 return <section className="card panel comms"><h2>Liên lạc & thông báo</h2>
 <p>{p.mode==='support'?'Theo dõi thông báo và xử lý yêu cầu của phụ huynh.':p.mode==='admin'?'Công bố thông báo và theo dõi yêu cầu hỗ trợ trong trường.':'Thông báo của trường và trao đổi với phụ huynh theo học sinh.'}</p>
 <button disabled={c.busy} onClick={action(c.refresh)}>Làm mới liên lạc</button>
 {c.busy&&<p role="status">Đang xử lý…</p>}{c.error&&<p role="alert" className="error">{c.error}</p>}{c.success&&<p role="status">{c.success}</p>}
 <fieldset disabled={c.busy} style={{border:0,padding:0,minWidth:0}}>
 {c.compose&&<section><h3>Soạn thông báo</h3><form onSubmit={e=>{e.preventDefault();void c.run(c.createNotice);}}>
 {p.mode==='admin'&&<label>Phạm vi<select value={c.scope} onChange={e=>c.setScope(e.target.value as NoticeScope)}>{['SCHOOL','GRADE','CLASS'].map(v=><option key={v} value={v}>{labels[v]}</option>)}</select></label>}
 {c.scope==='CLASS'&&<label>Lớp nhận thông báo<select required value={c.classId} onChange={e=>c.setClassId(e.target.value)}><option value="">Chọn lớp</option>{c.classes.map(x=><option key={x.id} value={x.id}>{x.code}</option>)}</select></label>}
 {c.scope==='GRADE'&&<label>Khối<select value={c.grade} onChange={e=>c.setGrade(e.target.value)}>{[6,7,8,9].map(x=><option key={x}>{x}</option>)}</select></label>}
 <label>Tiêu đề thông báo<input required maxLength={180} value={c.title} onChange={e=>c.setTitle(e.target.value)}/></label>
 <label>Nội dung thông báo<textarea required maxLength={12000} value={c.body} onChange={e=>c.setBody(e.target.value)}/></label><button>Lưu bản nháp</button></form></section>}
 <h3>Thông báo nhà trường</h3>{!c.notices.length&&<p>Chưa có thông báo trong phạm vi của bạn.</p>}
 {c.notices.map(n=><article key={n.id} style={{borderBottom:'1px solid #ddd',padding:'12px 0'}}><h4>{n.title} · {labels[n.state]}</h4>
 <small>{labels[n.scope]} · {when(n.published_at||n.created_at)}{n.recipient_count!==null&&` · ${n.read_count}/${n.recipient_count} đã đọc`}</small><p style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{n.body}</p>
 {n.can_publish&&<button onClick={()=>{if(window.confirm(`Công bố “${n.title}”? Nội dung sẽ được gửi đến phạm vi đã chọn và không thể chỉnh sửa.`))void c.run(()=>c.publish(n.id));}}>Công bố</button>}
 {n.state==='PUBLISHED'&&!n.read&&<button onClick={action(()=>c.readNotice(n.id))}>Đánh dấu thông báo đã đọc</button>}</article>)}
 {c.canChat&&<section><h3>Trao đổi phụ huynh – giáo viên</h3>
 <label>Học sinh liên hệ<select value={c.studentId} onChange={e=>void c.run(()=>c.pickStudent(e.target.value))}><option value="">Chọn học sinh</option>{c.students.map(s=><option key={s.id} value={s.id}>{s.full_name}</option>)}</select></label>
 {c.studentId&&!c.contacts.length&&<p>Không có liên hệ đang được xác minh.</p>}{c.contacts.map(x=><button key={x.id} onClick={action(()=>c.startThread(x.id))}>Trao đổi với {x.name}</button>)}
 {!c.threads.length&&<p>Chưa có hội thoại.</p>}{c.threads.map(t=><button style={{display:'block'}} key={t.id} onClick={action(()=>c.openThread(t.id))}>{t.student_name} · {p.mode==='parent'?t.teacher_name:t.guardian_name} · {t.unread_count} chưa đọc</button>)}
 {c.thread&&<article><h4>{c.thread.student_name} · {c.thread.teacher_name} ↔ {c.thread.guardian_name}</h4>
 {!c.messages.length&&<p>Chưa có tin nhắn.</p>}{c.messages.map(m=><p key={m.id} style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}><strong>{m.sender_id===p.userId?'Bạn':'Người liên hệ'}</strong> · {when(m.created_at)}<br/>{m.body}</p>)}
 <form onSubmit={e=>{e.preventDefault();void c.run(c.send);}}><label>Tin nhắn<textarea required maxLength={5000} value={c.draft} onChange={e=>c.setDraft(e.target.value)}/></label><button disabled={!c.draft.trim()}>Gửi tin nhắn</button></form></article>}</section>}
 {c.canTicket&&<section><h3>Yêu cầu hỗ trợ</h3>{!c.tickets.length&&<p>Chưa có yêu cầu hỗ trợ.</p>}
 {c.tickets.map(t=><button key={t.id} style={{display:'block'}} onClick={action(()=>c.openTicket(t.id))}>{t.subject} · {labels[t.state]}</button>)}
 {c.ticket&&<article><h4>{c.ticket.subject}</h4><p>{labels[c.ticket.category]} · {labels[c.ticket.state]} · {when(c.ticket.updated_at)}</p><p style={{whiteSpace:'pre-wrap'}}>{c.ticket.details}</p>
 {(c.ticket.replies||[]).map(r=><p key={r.id} style={{whiteSpace:'pre-wrap'}}><strong>{r.author_id===p.userId?'Bạn':r.author_id===c.ticket?.requester_id?'Người yêu cầu':'Nhân viên hỗ trợ'}</strong> · {when(r.created_at)}<br/>{r.body}</p>)}
 {c.ticket.state!=='CLOSED'&&<form onSubmit={e=>{e.preventDefault();void c.run(c.replyTicket);}}><label>Phản hồi hỗ trợ<textarea required maxLength={5000} value={c.reply} onChange={e=>c.setReply(e.target.value)}/></label><button disabled={!c.reply.trim()}>Gửi phản hồi</button></form>}
 {c.staff&&ticketTransitions[c.ticket.state].map(s=><button key={s} onClick={()=>{if(window.confirm(`Chuyển phiếu sang “${labels[s]}”?`))void c.run(()=>c.transition(s));}}>{labels[s]}</button>)}</article>}</section>}
 <h3>Hộp thông báo · {c.inbox.filter(n=>!n.read).length} chưa đọc</h3>{!c.inbox.length&&<p>Hộp thông báo trống.</p>}
 {c.inbox.map(n=><p key={n.id}>{labels[n.type]||'Cập nhật'} · {when(n.created_at)} · {n.read?'Đã đọc':'Chưa đọc'} {!n.read&&<button onClick={action(()=>c.readEvent(n.id))}>Đánh dấu đã đọc</button>}</p>)}
 </fieldset><small>Hiển thị tối đa 100 mục gần đây. Bấm làm mới để cập nhật; chưa có gửi push/email/SMS.</small></section>;
}
