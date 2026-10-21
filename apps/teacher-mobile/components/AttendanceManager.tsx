import {useEffect,useState,useRef} from 'react';
import {ActivityIndicator,Pressable,StyleSheet,Text,TextInput,View} from 'react-native';
import {ApiError,createApi,createAttendanceApi,type AttendanceMark,type AttendanceSessionDetail,type Classroom,type LeaveRequest} from '@edusphere/api-client';
const endpoint=process.env.EXPO_PUBLIC_API_URL||'http://127.0.0.1:8000';
const api=createApi(endpoint);const at=createAttendanceApi(endpoint);
const palette={green:'#146D79',dark:'#162440',border:'#DDE4EF',red:'#BC3745'};
const status:Record<AttendanceMark,string>={PRESENT:'Có mặt',ABSENT:'Vắng',LATE:'Đi muộn'};
function localToday(){const d=new Date();const z=(n:number)=>String(n).padStart(2,'0');return `${d.getFullYear()}-${z(d.getMonth()+1)}-${z(d.getDate())}`;}
export function AttendanceManager({token,tenant,onExpired}:{token:string;tenant:string;onExpired:()=>void}) {
  const live=useRef(true), pending=useRef(false);
  useEffect(()=>{live.current=true;return()=>{live.current=false;};},[]);

  const [classrooms,setClassrooms]=useState<Classroom[]>([]),[classId,setClassId]=useState('');
  const [date,setDate]=useState(localToday()),[session,setSession]=useState<AttendanceSessionDetail|null>(null);
  const [marks,setMarks]=useState<Record<string,AttendanceMark>>({}),[leaves,setLeaves]=useState<LeaveRequest[]>([]);
  const [message,setMessage]=useState(''),[working,setWorking]=useState(false);
  useEffect(()=>{void run(async()=>{const classes=await api.classrooms(token,tenant);if(live.current){setClassrooms(classes);setClassId(classes[0]?.id||'');}});},[token,tenant]);
  async function run(action:()=>Promise<void>){if(pending.current)return;pending.current=true;setWorking(true);setMessage('');try{await action();}catch(e){if(live.current){if(e instanceof ApiError&&e.status===401)onExpired();else setMessage(e instanceof Error?e.message:'Có lỗi xảy ra');}}finally{pending.current=false;if(live.current)setWorking(false);}}
  async function refreshLeaves(){await run(async()=>{setLeaves(await at.leaves(token,tenant));});}
  async function decide(id:string,action:'approve'|'reject') {await run(async()=>{await at.decide(token,tenant,id,action);
    setLeaves(await at.leaves(token,tenant));if(session){const data=await at.detail(token,tenant,session.id);setSession(data);}});}
  return <View style={s.panel}>
    <Text style={s.title}>Điểm danh lớp</Text><Text style={s.sub}>Điểm danh theo ngày · giáo viên chủ nhiệm</Text>
    <Text style={s.label}>Chọn lớp</Text>
    {classrooms.map(c=><Pressable key={c.id} disabled={working} onPress={()=>{setClassId(c.id);setSession(null);}} style={[s.choice,classId===c.id&&s.active]}><Text>{c.code} · Khối {c.grade_level}</Text></Pressable>)}
    <Text style={s.label}>Ngày điểm danh (YYYY-MM-DD)</Text><TextInput style={s.input} accessibilityLabel="Ngày điểm danh" editable={!working} value={date} onChangeText={value=>{setDate(value);setSession(null);setMarks({});}}/>
    <Pressable disabled={working||!classId} style={s.button} onPress={()=>run(async()=>{const result=await at.start(token,tenant,classId,date);
      const detail=await at.detail(token,tenant,result.id);setSession(detail);
      setMarks(Object.fromEntries(detail.roster.filter(r=>r.mark!==null).map(r=>[r.id,r.mark])) as Record<string,AttendanceMark>);})}><Text style={s.buttonText}>Mở / xem phiên điểm danh</Text></Pressable>
    {session&&<View><Text style={s.title}>Danh sách lớp · {session.attendance_date} · {session.state}</Text>
      {session.roster.map(r=><View style={s.row} key={r.id}><Text style={s.name}>{r.full_name}</Text><Text style={s.sub}>{r.student_code} {r.effective_status==='EXCUSED_ABSENCE'?'· Nghỉ có phép':''}</Text>
        <View style={s.options}>{(['PRESENT','ABSENT','LATE'] as AttendanceMark[]).map(mark=><Pressable key={mark} accessibilityLabel={`${r.full_name}: ${status[mark]}`} disabled={working||session.state!=='DRAFT'} onPress={()=>setMarks(prev=>({...prev,[r.id]:mark}))} style={[s.option,marks[r.id]===mark&&s.active]}><Text>{status[mark]}</Text></Pressable>)}</View></View>)}
      {session.state==='DRAFT'&&<><Pressable disabled={working||!session.roster.length||!session.roster.some(r=>marks[r.id])} style={s.button} onPress={()=>run(async()=>{await at.save(token,tenant,session.id,session.roster.filter(r=>marks[r.id]).map(r=>({student_id:r.id,mark:marks[r.id],note:r.note})));
        setSession(await at.detail(token,tenant,session.id));setMessage('Đã lưu điểm danh.');})}><Text style={s.buttonText}>Lưu điểm danh</Text></Pressable>
        <Pressable disabled={working} style={s.buttonOutline} onPress={()=>run(async()=>{if(!session.roster.length||session.roster.some(r=>!marks[r.id]))throw new Error('Cần điểm danh đủ học sinh trước khi nộp.');await at.save(token,tenant,session.id,session.roster.map(r=>({student_id:r.id,mark:marks[r.id],note:r.note})));await at.submit(token,tenant,session.id);setSession(await at.detail(token,tenant,session.id));setMessage('Đã nộp điểm danh.');})}><Text style={s.outlineText}>Nộp điểm danh</Text></Pressable></>}
    </View>}
    <View style={s.row}><Text style={s.title}>Đơn xin nghỉ chờ duyệt</Text>
      <Pressable disabled={working} onPress={refreshLeaves}><Text style={s.outlineText}>Tải lại</Text></Pressable></View>
    {leaves.filter(l=>l.state==='PENDING').map(l=><View key={l.id} style={s.row}><Text style={s.name}>{l.student_name||l.student_id}</Text><Text>{l.from_date} → {l.through_date}</Text><Text style={s.sub}>{l.reason}</Text>
      <View style={s.options}><Pressable disabled={working} style={s.choice} onPress={()=>decide(l.id,'approve')}><Text>Duyệt</Text></Pressable><Pressable disabled={working} style={s.choice} onPress={()=>decide(l.id,'reject')}><Text>Từ chối</Text></Pressable></View></View>)}
    {working&&<ActivityIndicator color={palette.green}/>} {!!message&&<Text accessibilityRole="alert" style={s.feedback}>{message}</Text>}
  </View>;
}
const s=StyleSheet.create({panel:{paddingTop:12},title:{fontSize:18,fontWeight:'800',color:palette.dark,marginTop:10},sub:{color:'#637089',marginTop:4,fontSize:13},
  label:{fontWeight:'700',color:palette.dark,marginTop:16},input:{borderWidth:1,borderColor:palette.border,padding:12,borderRadius:10,marginTop:6},
  choice:{borderWidth:1,borderColor:palette.border,borderRadius:8,padding:10,marginTop:7,marginRight:6},active:{backgroundColor:'#CDEEEB',borderColor:palette.green},
  button:{backgroundColor:palette.green,padding:14,marginTop:15,borderRadius:10,alignItems:'center'},buttonText:{color:'#fff',fontWeight:'800'},
  buttonOutline:{borderWidth:1,borderColor:palette.green,padding:14,marginTop:10,borderRadius:10,alignItems:'center'},outlineText:{color:palette.green,fontWeight:'800'},
  row:{padding:10,borderBottomWidth:1,borderColor:palette.border,marginTop:8},name:{fontWeight:'700',color:palette.dark},options:{flexDirection:'row',flexWrap:'wrap'},
  option:{borderRadius:8,padding:9,borderWidth:1,borderColor:palette.border,marginTop:7,marginRight:5},feedback:{paddingTop:12,color:palette.red}});
