import {useEffect,useRef,useState} from 'react';
import {ActivityIndicator,Alert,Platform,Pressable,StyleSheet,Switch,Text,TextInput,View} from 'react-native';
import DateTimePicker from '@react-native-community/datetimepicker';
import {ApiError,createApi,createHomeworkApi,type Homework,type HomeworkRoster,type Classroom} from '@edusphere/api-client';
const base=process.env.EXPO_PUBLIC_API_URL||'http://127.0.0.1:8000';
const api=createHomeworkApi(base),core=createApi(base);
type Subject={id:string;name:string};
const labels:Record<string,string>={DRAFT:'Nháp',PUBLISHED:'Đã giao',CLOSED:'Đã đóng',SUBMITTED:'Đã nộp',RETURNED:'Đã trả bài',NOT_SUBMITTED:'Chưa nộp',OVERDUE:'Quá hạn'};
export function HomeworkManager({token,tenant,canCreate,onExpired}:{token:string;tenant:string;canCreate:boolean;onExpired:()=>void}){
  const live=useRef(true),pending=useRef(false);
  const [tasks,setTasks]=useState<Homework[]>([]),[classes,setClasses]=useState<Classroom[]>([]),[subjects,setSubjects]=useState<Subject[]>([]);
  const [classId,setClassId]=useState(''),[subjectId,setSubjectId]=useState('');
  const [title,setTitle]=useState(''),[instructions,setInstructions]=useState(''),[due,setDue]=useState(new Date(Date.now()+86400000)),[picker,setPicker]=useState<'date'|'time'|null>(null);
  const [editing,setEditing]=useState(''),[allowLate,setAllowLate]=useState(false);
  const [roster,setRoster]=useState<HomeworkRoster|null>(null),[feedback,setFeedback]=useState<Record<string,string>>({}),[scores,setScores]=useState<Record<string,string>>({});
  const [busy,setBusy]=useState(true),[message,setMessage]=useState('');
  function failed(e:unknown){if(!live.current)return;if(e instanceof ApiError&&e.status===401)onExpired();else setMessage(e instanceof Error?e.message:'Không thể tải dữ liệu.');}
  useEffect(()=>{live.current=true;let active=true;
    Promise.all([api.list(token,tenant),canCreate?core.classrooms(token,tenant):Promise.resolve([]),canCreate?core.adminGet<Subject[]>('/api/v1/subjects/',token,tenant):Promise.resolve([])])
      .then(([ts,cs,ss])=>{if(active){setTasks(ts);setClasses(cs);setSubjects(ss);setClassId(cs[0]?.id||'');setSubjectId(ss[0]?.id||'');}})
      .catch(e=>{if(active)failed(e);}).finally(()=>{if(active)setBusy(false);});return()=>{active=false;live.current=false;};},[tenant,token,canCreate]);
  async function act(callback:()=>Promise<unknown>,rosterId=roster?.assignment.id){if(pending.current)return;pending.current=true;setBusy(true);setMessage('');
    try{await callback();if(!live.current)return;const ts=await api.list(token,tenant);if(!live.current)return;setTasks(ts);
      if(rosterId){const r=await api.roster(token,tenant,rosterId);if(live.current)setRoster(r);}if(live.current)setMessage('Đã cập nhật.');}
    catch(e){if(live.current){setRoster(null);failed(e);}}finally{pending.current=false;if(live.current)setBusy(false);}}
  function confirm(message:string,callback:()=>Promise<unknown>){Alert.alert('Xác nhận',message,[{text:'Hủy',style:'cancel'},{text:'Đồng ý',onPress:()=>{if(live.current)void act(callback);}}]);}
  function reset(){setEditing('');setTitle('');setInstructions('');setAllowLate(false);setDue(new Date(Date.now()+86400000));}
  return <View style={s.card}><Text style={s.heading}>Bài tập</Text><Text style={s.hint}>Điểm bài tập không tự nhập vào sổ điểm chính thức.</Text>
    {canCreate?<><Text style={s.label}>{editing?'Chỉnh sửa nháp':'Tạo bài tập'}</Text>
      <Text style={s.label}>Lớp</Text>{classes.map(c=><Pressable accessibilityRole="button" disabled={busy||!!editing} style={s.option} key={c.id} onPress={()=>setClassId(c.id)}><Text>{classId===c.id?'✓ ':''}{c.code}</Text></Pressable>)}
      <Text style={s.label}>Môn</Text>{subjects.map(sub=><Pressable accessibilityRole="button" disabled={busy||!!editing} style={s.option} key={sub.id} onPress={()=>setSubjectId(sub.id)}><Text>{subjectId===sub.id?'✓ ':''}{sub.name}</Text></Pressable>)}
      <TextInput editable={!busy} maxLength={160} style={s.input} accessibilityLabel="Tiêu đề bài tập" placeholder="Tiêu đề" value={title} onChangeText={setTitle}/>
      <TextInput editable={!busy} maxLength={10000} style={s.input} accessibilityLabel="Nội dung bài tập" multiline placeholder="Hướng dẫn" value={instructions} onChangeText={setInstructions}/>
      <Text style={s.label}>Hạn nộp: {due.toLocaleString('vi-VN')} (giờ thiết bị)</Text>
      <Pressable accessibilityRole="button" disabled={busy} style={s.option} onPress={()=>setPicker('date')}><Text>Chọn ngày</Text></Pressable>
      <Pressable accessibilityRole="button" disabled={busy} style={s.option} onPress={()=>setPicker('time')}><Text>Chọn giờ</Text></Pressable>
      {picker&&<><DateTimePicker value={due} mode={picker} display={Platform.OS==='ios'?'spinner':'default'} onChange={(_,date)=>{if(Platform.OS!=='ios')setPicker(null);if(date)setDue(date);}}/>
        {Platform.OS==='ios'&&<Pressable style={s.option} onPress={()=>setPicker(null)}><Text>Xong</Text></Pressable>}</>}
      <Text style={s.label}>Cho phép nộp muộn trước khi đóng bài</Text><Switch accessibilityLabel="Cho phép nộp muộn" disabled={busy} value={allowLate} onValueChange={setAllowLate}/>
      <Pressable accessibilityRole="button" style={s.button} disabled={busy||!classId||!subjectId||!title.trim()||!instructions.trim()} onPress={()=>void act(async()=>{
        const data={title:title.trim(),instructions:instructions.trim(),due_at:due.toISOString(),allow_late:allowLate};
        if(editing)await api.edit(token,tenant,editing,data);else await api.create(token,tenant,{...data,classroom_id:classId,subject_id:subjectId});if(live.current)reset();
      })}><Text style={s.buttonText}>{editing?'Lưu thay đổi':'Lưu bài tập nháp'}</Text></Pressable>
      {editing&&<Pressable disabled={busy} style={s.option} onPress={reset}><Text>Hủy sửa</Text></Pressable>}
    </>:<Text style={s.hint}>Chế độ theo dõi lớp: chỉ xem tiến độ và phản hồi.</Text>}
    <Pressable accessibilityRole="button" disabled={busy} style={s.option} onPress={()=>void act(async()=>{})}><Text>Tải lại</Text></Pressable>
    {!busy&&!tasks.length&&<Text style={s.hint}>Chưa có bài tập được phép xem.</Text>}
    {tasks.map(task=><View key={task.id} style={s.item}><Text style={s.headingSmall}>{task.title}</Text>
      <Text style={s.hint}>{task.classroom_code} · {task.subject_name} · {labels[task.state]}</Text><Text style={s.hint}>Hạn: {new Date(task.due_at).toLocaleString('vi-VN')}</Text>
      <Pressable accessibilityRole="button" disabled={busy} style={s.option} onPress={()=>{setRoster(null);setFeedback({});setScores({});void act(async()=>{},task.id);}}><Text>Xem bài nộp</Text></Pressable>
      {task.can_manage&&task.state==='DRAFT'&&<><Pressable disabled={busy} style={s.option} onPress={()=>{setEditing(task.id);setClassId(task.classroom_id);setSubjectId(task.subject_id);setTitle(task.title);setInstructions(task.instructions);setDue(new Date(task.due_at));setAllowLate(task.allow_late);}}><Text>Sửa nháp</Text></Pressable>
        <Pressable disabled={busy} style={s.option} onPress={()=>confirm(`Giao “${task.title}” cho lớp ${task.classroom_code}?`,()=>api.publish(token,tenant,task.id))}><Text>Giao bài cho lớp</Text></Pressable></>}
      {task.can_manage&&task.state==='PUBLISHED'&&<Pressable disabled={busy} style={s.option} onPress={()=>confirm(`Đóng “${task.title}”? Học sinh sẽ không thể sửa hoặc nộp thêm.`,()=>api.close(token,tenant,task.id))}><Text>Đóng bài tập</Text></Pressable>}</View>)}
    {roster&&<View style={s.item}><Text style={s.headingSmall}>Bài nộp: {roster.assignment.title}</Text><Text>{roster.assignment.instructions}</Text>
      {roster.students.map(r=><View key={r.student_id} style={s.item}><Text style={s.label}>{r.full_name} · {labels[r.status]}</Text>
        {r.submission?.submitted_at&&<Text style={s.hint}>Nộp: {new Date(r.submission.submitted_at).toLocaleString('vi-VN')}{new Date(r.submission.submitted_at)>new Date(roster.assignment.due_at)?' · Nộp muộn':''}</Text>}
        {!!r.submission?.content_text&&<Text>{r.submission.content_text}</Text>}
        {roster.assignment.can_manage&&r.status==='SUBMITTED'&&r.submission&&<><TextInput editable={!busy} maxLength={3000} style={s.input} accessibilityLabel={'Nhận xét '+r.full_name} placeholder="Nhận xét" value={feedback[r.submission.id]||''} onChangeText={v=>setFeedback(old=>({...old,[r.submission!.id]:v}))}/>
          <TextInput editable={!busy} style={s.input} accessibilityLabel={'Điểm bài tập '+r.full_name} keyboardType="decimal-pad" placeholder="Điểm 0–10 (tùy chọn)" value={scores[r.submission.id]||''} onChangeText={v=>setScores(old=>({...old,[r.submission!.id]:v}))}/>
          <Pressable style={s.button} disabled={busy||(!feedback[r.submission.id]?.trim()&&!scores[r.submission.id])} onPress={()=>confirm(`Trả bài cho ${r.full_name}? Kết quả sẽ được khóa.`,()=>api.returnWork(token,tenant,r.submission!.id,feedback[r.submission!.id]||'',r.submission!.version,scores[r.submission!.id]?.replace(',','.')))}><Text style={s.buttonText}>Trả bài</Text></Pressable></>}
        {r.status==='RETURNED'&&<Text style={s.hint}>Nhận xét: {r.submission?.feedback||'—'} · Điểm bài tập: {r.submission?.score??'—'}</Text>}
      </View>)}</View>}
    {busy&&<ActivityIndicator/>}{message&&<Text accessibilityRole="alert" style={s.hint}>{message}</Text>}
  </View>;
}
const s=StyleSheet.create({card:{padding:18,marginTop:20,borderRadius:16,backgroundColor:'#fff'},heading:{fontWeight:'800',fontSize:19,color:'#192B46'},
 headingSmall:{fontSize:16,fontWeight:'700',color:'#192B46'},hint:{color:'#67758D',fontSize:12,marginTop:7},label:{fontSize:14,fontWeight:'600',marginTop:9},
 input:{borderWidth:1,borderColor:'#DDE4EF',borderRadius:8,padding:12,marginTop:10,minHeight:44},option:{minHeight:44,borderWidth:1,borderColor:'#DDE4EF',borderRadius:8,padding:10,marginTop:8},
 button:{backgroundColor:'#146D79',borderRadius:8,padding:13,marginTop:12,minHeight:44,alignItems:'center'},buttonText:{color:'#fff',fontWeight:'800'},
 item:{marginTop:12,paddingTop:12,borderTopWidth:1,borderColor:'#E3EAF0'}});
