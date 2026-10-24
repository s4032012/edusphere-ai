import {useEffect,useRef,useState} from 'react';
import {ActivityIndicator,Alert,Pressable,StyleSheet,Text,TextInput,View} from 'react-native';
import {ApiError,createHomeworkApi,type Student,type StudentHomeworkOverview,type Homework,type HomeworkSubmission} from '@edusphere/api-client';
const api=createHomeworkApi(process.env.EXPO_PUBLIC_API_URL||'http://127.0.0.1:8000');
const labels:Record<string,string>={DRAFT:'Đang làm nháp',SUBMITTED:'Đã nộp',RETURNED:'Đã trả bài',NOT_SUBMITTED:'Chưa nộp',OVERDUE:'Quá hạn'};
export function HomeworkStudent({token,tenant,students,onExpired}:{token:string;tenant:string;students:Student[];onExpired:()=>void}){
  const live=useRef(true),pending=useRef(false),selection=useRef(0);
  const [overview,setOverview]=useState<StudentHomeworkOverview|null>(null),[reload,setReload]=useState(0);
  const [chosen,setChosen]=useState<Homework|null>(null),[draft,setDraft]=useState(''),[submission,setSubmission]=useState<HomeworkSubmission|null>(null),[conflict,setConflict]=useState(false);
  const [busy,setBusy]=useState(false),[message,setMessage]=useState('');
  const studentId=students.length===1?students[0].id:'';
  function failed(e:unknown){if(!live.current)return;if(e instanceof ApiError&&e.status===401)onExpired();else setMessage(e instanceof Error?e.message:'Không thể tải dữ liệu.');}
  useEffect(()=>{live.current=true;return()=>{live.current=false;selection.current++;};},[]);
  useEffect(()=>{let active=true;selection.current++;setChosen(null);setSubmission(null);setDraft('');setOverview(null);setMessage('');setConflict(false);
    if(!studentId)return;setBusy(true);api.student(token,tenant,studentId).then(data=>{if(active)setOverview(data);}).catch(e=>{if(active)failed(e);}).finally(()=>{if(active)setBusy(false);});
    return()=>{active=false;};},[token,tenant,studentId,reload]);
  async function pick(id:string){if(pending.current)return;const seq=++selection.current;setChosen(null);setSubmission(null);setDraft('');setConflict(false);setMessage('');setBusy(true);
    try{const result=await api.mine(token,tenant,id);if(live.current&&seq===selection.current){setChosen(result.assignment);setSubmission(result.submission);setDraft(result.submission?.content_text||'');}}
    catch(e){if(seq===selection.current)failed(e);}finally{if(live.current&&seq===selection.current)setBusy(false);}}
  async function send(action:'save'|'submit'){if(!chosen||pending.current||conflict)return;pending.current=true;setBusy(true);setMessage('');const seq=selection.current;
    try{const result=await api.submit(token,tenant,chosen.id,draft,action,submission?.version??0);if(!live.current||seq!==selection.current)return;setSubmission(result);
      const data=await api.student(token,tenant,studentId);if(live.current&&seq===selection.current){setOverview(data);setMessage(action==='submit'?'Đã nộp bài.':'Đã lưu nháp.');}
    }catch(e){if(live.current&&seq===selection.current){if(e instanceof ApiError&&e.status===409)setConflict(true);failed(e);}}
    finally{pending.current=false;if(live.current&&seq===selection.current)setBusy(false);}}
  const writable=!!chosen&&chosen.state==='PUBLISHED'&&submission?.state!=='RETURNED'&&(chosen.allow_late||Date.now()<=new Date(chosen.due_at).getTime());
  return <View style={s.card}><Text style={s.heading}>Bài tập của em</Text>
    <Pressable accessibilityRole="button" disabled={busy} style={s.item} onPress={()=>{if(draft!== (submission?.content_text||''))Alert.alert('Tải lại?','Bản sửa chưa lưu sẽ bị bỏ.',[{text:'Hủy',style:'cancel'},{text:'Tải lại',onPress:()=>setReload(v=>v+1)}]);else setReload(v=>v+1);}}><Text>Tải lại danh sách</Text></Pressable>
    {!studentId&&<Text style={s.muted}>{students.length?'Tài khoản cần liên kết duy nhất một hồ sơ học sinh để nộp bài. Liên hệ nhà trường.':'Chưa có hồ sơ học sinh được phép xem.'}</Text>}
    {!busy&&overview?.items.length===0&&<Text style={s.muted}>Chưa có bài tập được giao.</Text>}
    {overview?.items.map(row=><Pressable accessibilityRole="button" disabled={busy} key={row.assignment.id} style={s.item} onPress={()=>{
      if(draft!==(submission?.content_text||''))Alert.alert('Đổi bài tập?','Bản sửa chưa lưu sẽ bị bỏ.',[{text:'Hủy',style:'cancel'},{text:'Tiếp tục',onPress:()=>{if(live.current)void pick(row.assignment.id);}}]);else void pick(row.assignment.id);
    }}><Text style={s.title}>{chosen?.id===row.assignment.id?'✓ ':''}{row.assignment.title}</Text><Text style={s.muted}>{row.assignment.subject_name} · {labels[row.status]} · Hạn: {new Date(row.assignment.due_at).toLocaleString('vi-VN')}</Text></Pressable>)}
    {chosen&&<View style={s.item}><Text style={s.title}>{chosen.title}</Text><Text style={s.muted}>{chosen.instructions}</Text><Text style={s.muted}>{chosen.allow_late?'Cho phép nộp muộn khi bài còn mở.':'Không nhận bài sau hạn.'}</Text>
      <TextInput accessibilityLabel="Nội dung bài nộp" maxLength={20000} style={s.input} multiline editable={writable&&!busy&&!conflict} value={draft} onChangeText={setDraft} placeholder="Viết câu trả lời tại đây"/>
      {submission?.state==='RETURNED'?<Text style={s.muted}>Nhận xét: {submission.feedback||'Không có'} · Điểm bài tập: {submission.score??'—'} (không phải điểm học bạ)</Text>
        :!writable?<Text style={s.muted}>Bài đã đóng hoặc hết hạn nộp.</Text>
        :<>{submission?.state!=='SUBMITTED'&&<Pressable accessibilityRole="button" disabled={busy||conflict} style={s.button} onPress={()=>void send('save')}><Text style={s.buttonText}>Lưu nháp</Text></Pressable>}
          <Pressable accessibilityRole="button" disabled={busy||conflict||!draft.trim()} style={s.button} onPress={()=>Alert.alert('Nộp bài?',`Gửi bài làm “${chosen.title}” cho giáo viên.`,[{text:'Hủy',style:'cancel'},{text:'Nộp bài',onPress:()=>{if(live.current)void send('submit');}}])}><Text style={s.buttonText}>{submission?.state==='SUBMITTED'?'Nộp lại bản sửa':'Nộp bài'}</Text></Pressable></>}
      {conflict&&<><Text style={s.muted}>Bài đã thay đổi ở phiên khác. Sao chép phần sửa cần giữ trước khi tải lại.</Text><Pressable disabled={busy} style={s.button} onPress={()=>void pick(chosen.id)}><Text style={s.buttonText}>Tải phiên bản mới nhất</Text></Pressable></>}
    </View>}
    {busy&&<ActivityIndicator/>}{message&&<Text accessibilityRole="alert" style={s.muted}>{message}</Text>}
  </View>;
}
const s=StyleSheet.create({card:{backgroundColor:'#fff',padding:20,borderRadius:16,marginTop:20},heading:{fontWeight:'800',fontSize:18,color:'#192B46'},
 item:{marginTop:12,borderTopWidth:1,borderColor:'#E7ECF3',paddingTop:12},title:{fontWeight:'700',fontSize:15,color:'#192B46'},
 muted:{color:'#65748A',fontSize:13,marginTop:7},input:{marginTop:12,minHeight:100,borderWidth:1,borderColor:'#D5DEEA',borderRadius:10,padding:12,textAlignVertical:'top'},
 button:{backgroundColor:'#146D79',padding:14,borderRadius:9,alignItems:'center',marginTop:12,minHeight:44},buttonText:{color:'white',fontWeight:'800'}});
