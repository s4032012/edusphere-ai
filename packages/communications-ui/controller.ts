import {useEffect,useRef,useState} from 'react';
import {ApiError,createApi,createCommunicationsApi,messageKey,type Student,type Classroom,type AnnouncementDto,type ConversationDto,type ConversationMessageDto,type TicketDto,type InboxDto,type ContactDto,type NoticeScope,type TicketState} from '@edusphere/api-client';
export type Props={baseUrl:string;token:string;tenant:string;userId:string;mode:'teacher'|'parent'|'student'|'admin'|'support';canAnnounce?:boolean;onExpired:()=>void};
export function useCommunications(p:Props){
 const api=createCommunicationsApi(p.baseUrl),core=createApi(p.baseUrl);
 const alive=useRef(true),pending=useRef(false),expired=useRef(p.onExpired);expired.current=p.onExpired;
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[success,setSuccess]=useState('');
 const [notices,setNotices]=useState<AnnouncementDto[]>([]),[inbox,setInbox]=useState<InboxDto[]>([]);
 const [threads,setThreads]=useState<ConversationDto[]>([]),[messages,setMessages]=useState<ConversationMessageDto[]>([]),[thread,setThread]=useState<ConversationDto|null>(null);
 const [tickets,setTickets]=useState<TicketDto[]>([]),[ticket,setTicket]=useState<TicketDto|null>(null);
 const [students,setStudents]=useState<Student[]>([]),[classes,setClasses]=useState<Classroom[]>([]),[contacts,setContacts]=useState<ContactDto[]>([]);
 const [studentId,setStudentId]=useState(''),[draft,setDraft]=useState(''),[reply,setReply]=useState('');
 const [scope,setScope]=useState<NoticeScope>(p.mode==='admin'?'SCHOOL':'CLASS'),[classId,setClassId]=useState(''),[grade,setGrade]=useState('8');
 const [title,setTitle]=useState(''),[body,setBody]=useState('');
 const [category,setCategory]=useState('OTHER'),[subject,setSubject]=useState(''),[details,setDetails]=useState(''),[ticketStudent,setTicketStudent]=useState('');
 const retry=useRef<{thread:string;body:string;key:string}|null>(null);
 const canChat=p.mode==='teacher'||p.mode==='parent',canTicket=['admin','support','parent'].includes(p.mode),staff=p.mode==='admin'||p.mode==='support';
 const compose=p.mode==='admin'||(p.mode==='teacher'&&p.canAnnounce===true);
 function commit(f:()=>void){if(alive.current)f();}
 async function run(f:()=>Promise<void>){
  if(pending.current||!alive.current)return;pending.current=true;setBusy(true);setError('');setSuccess('');
  try{await f();}catch(e){commit(()=>{setError(e instanceof Error?e.message:'Không thể kết nối. Vui lòng thử lại.');
   if(e instanceof ApiError&&[401,403,404].includes(e.status)){setNotices([]);setInbox([]);setThreads([]);setMessages([]);setThread(null);setTickets([]);setTicket(null);setContacts([]);setStudents([]);setClasses([]);}
   if(e instanceof ApiError&&e.status===401)expired.current();
  });}finally{pending.current=false;commit(()=>setBusy(false));}
 }
 async function refresh(){
  const [a,b,c,d,e,f]=await Promise.all([api.announcements(p.token,p.tenant),api.inbox(p.token,p.tenant),
   canChat?api.conversations(p.token,p.tenant):Promise.resolve([]),canTicket?api.tickets(p.token,p.tenant):Promise.resolve([]),
   canChat?core.students(p.token,p.tenant):Promise.resolve([]),compose?core.classrooms(p.token,p.tenant):Promise.resolve([])]);
  commit(()=>{setNotices(a);setInbox(b);setThreads(c);setTickets(d);setStudents(e);setClasses(f);setContacts([]);setStudentId('');setThread(null);setMessages([]);setTicket(null);setReply('');});
 }
 useEffect(()=>{alive.current=true;void run(refresh);return()=>{alive.current=false;};},[]);
 async function openThread(id:string){
  commit(()=>{setThread(null);setMessages([]);setDraft('');});
  const data=await api.messages(p.token,p.tenant,id);if(!alive.current)return;
  await api.readConversation(p.token,p.tenant,id,data.messages.at(-1)?.id??null);
  commit(()=>{setThread({...data.conversation,unread_count:0});setMessages(data.messages);setThreads(rows=>rows.map(t=>t.id===id?{...t,unread_count:0}:t));});
 }
 async function pickStudent(id:string){
  setContacts([]);setStudentId(id);if(!id)return;
  const data=await api.contacts(p.token,p.tenant,id);commit(()=>setContacts(p.mode==='parent'?data.teachers:data.guardians));
 }
 async function startThread(id:string){
  const t=await api.createConversation(p.token,p.tenant,studentId,p.mode==='parent'?id:p.userId,p.mode==='parent'?p.userId:id);
  if(!alive.current)return;await refresh();if(alive.current)await openThread(t.id);
 }
 async function send(){
  if(!thread||!draft.trim())return;
  if(!retry.current||retry.current.thread!==thread.id||retry.current.body!==draft)retry.current={thread:thread.id,body:draft,key:messageKey()};
  const attempt=retry.current;
  await api.sendMessage(p.token,p.tenant,attempt.thread,attempt.body,attempt.key);
  retry.current=null;commit(()=>{setDraft('');setSuccess('Đã gửi tin nhắn.');});if(alive.current)await openThread(attempt.thread);
 }
 async function createNotice(){
  const n=await api.createAnnouncement(p.token,p.tenant,{scope,title,body,...(scope==='CLASS'?{classroom_id:classId}:{}),...(scope==='GRADE'?{grade_level:Number(grade)}:{})});
  commit(()=>{setTitle('');setBody('');setNotices(rows=>[n,...rows]);setSuccess('Đã lưu bản nháp. Xem lại nội dung rồi công bố.');});
 }
 async function publish(id:string){await api.publishAnnouncement(p.token,p.tenant,id);if(alive.current)await refresh();commit(()=>setSuccess('Đã công bố thông báo.'));}
 async function readNotice(id:string){await api.readAnnouncement(p.token,p.tenant,id);commit(()=>setNotices(rows=>rows.map(n=>n.id===id?{...n,read:true}:n)));}
 async function readEvent(id:string){await api.markInboxRead(p.token,p.tenant,id);commit(()=>setInbox(rows=>rows.map(n=>n.id===id?{...n,read:true}:n)));}
 async function createTicket(){
  const t=await api.createTicket(p.token,p.tenant,{category,subject,details,...(ticketStudent?{student_id:ticketStudent}:{})});
  commit(()=>{setTickets(rows=>[t,...rows]);setTicket(t);setSubject('');setDetails('');setSuccess('Đã gửi yêu cầu hỗ trợ.');});
 }
 async function openTicket(id:string){setTicket(null);setReply('');const t=await api.ticket(p.token,p.tenant,id);commit(()=>setTicket(t));}
 function updateTicket(t:TicketDto){commit(()=>{setTicket(t);setTickets(rows=>rows.map(x=>x.id===t.id?t:x));});}
 async function replyTicket(){if(!ticket||!reply.trim())return;const t=await api.replyTicket(p.token,p.tenant,ticket.id,reply);updateTicket(t);commit(()=>setReply(''));}
 async function transition(state:TicketState){if(!ticket)return;const t=await api.changeTicketStatus(p.token,p.tenant,ticket.id,state,ticket.version);updateTicket(t);}
 return {busy,error,success,notices,inbox,threads,messages,thread,tickets,ticket,students,classes,contacts,studentId,draft,reply,scope,classId,grade,title,body,category,subject,details,ticketStudent,
  setDraft,setReply,setScope,setClassId,setGrade,setTitle,setBody,setCategory,setSubject,setDetails,setTicketStudent,canChat,canTicket,staff,compose,
  run,refresh,openThread,pickStudent,startThread,send,createNotice,publish,readNotice,readEvent,createTicket,openTicket,replyTicket,transition};
}
