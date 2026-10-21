import {useEffect,useState,useRef} from 'react';
import {ActivityIndicator,Pressable,StyleSheet,Text,TextInput,View} from 'react-native';
import {ApiError,createAttendanceApi,type AttendanceHistory,type LeaveRequest,type Student} from '@edusphere/api-client';
const at=createAttendanceApi(process.env.EXPO_PUBLIC_API_URL||'http://127.0.0.1:8000');
const GREEN='#117C63';
const words:Record<string,string>={PRESENT:'Có mặt',ABSENT:'Vắng',LATE:'Đi muộn',EXCUSED_ABSENCE:'Nghỉ có phép',PENDING:'Đang chờ',APPROVED:'Đã duyệt',REJECTED:'Từ chối',WITHDRAWN:'Đã rút'};
export function LeaveAndAttendance({token,tenant,students,onExpired}:{token:string;tenant:string;students:Student[];onExpired:()=>void}){
  const live=useRef(true), pending=useRef(false);
  useEffect(()=>{live.current=true;return()=>{live.current=false;};},[]);

  const [studentId,setStudentId]=useState('');const [history,setHistory]=useState<AttendanceHistory[]>([]),[leaves,setLeaves]=useState<LeaveRequest[]>([]);
  const [from,setFrom]=useState(''),[through,setThrough]=useState(''),[reason,setReason]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false);
  useEffect(()=>{if(!students.some(s=>s.id===studentId))setStudentId(students[0]?.id||'');},[students,studentId]);
  useEffect(()=>{setHistory([]);setLeaves([]);if(!studentId)return;
    let live=true;Promise.all([at.studentAttendance(token,tenant,studentId),at.leaves(token,tenant,studentId)])
      .then(([a,b])=>{if(live){setHistory(a);setLeaves(b);}}).catch(e=>{if(live){if(e instanceof ApiError&&e.status===401)onExpired();else setMessage(String(e));}});
    return()=>{live=false};},[token,tenant,studentId]);
  async function run(action:()=>Promise<void>){if(pending.current)return;pending.current=true;setBusy(true);setMessage('');try{await action();}catch(e){if(live.current){if(e instanceof ApiError&&e.status===401)onExpired();else setMessage(e instanceof Error?e.message:'Có lỗi xảy ra');}}finally{pending.current=false;if(live.current)setBusy(false);}}
  async function refresh(){setHistory(await at.studentAttendance(token,tenant,studentId));setLeaves(await at.leaves(token,tenant,studentId));}
  return <View style={s.card}><Text style={s.heading}>Chuyên cần & Đơn xin nghỉ</Text>
    <Text style={s.note}>Chọn con</Text>{students.map(st=><Pressable key={st.id} disabled={busy} onPress={()=>setStudentId(st.id)} style={[s.tab,studentId===st.id&&s.active]}><Text>{st.full_name}</Text></Pressable>)}
    {!studentId?<Text>Không có học sinh được liên kết và xác minh.</Text>:<>
      <Text style={s.heading}>Lịch sử chuyên cần</Text><Pressable disabled={busy} onPress={()=>run(refresh)}><Text style={s.link}>Tải lại lịch sử và đơn</Text></Pressable>
      {history.length?history.slice(0,12).map(h=><Text key={h.date} style={s.item}>{h.date} · {words[h.effective_status]}</Text>):<Text style={s.note}>Chưa có dữ liệu điểm danh đã nộp.</Text>}
      <Text style={s.heading}>Gửi đơn xin nghỉ</Text>
      <Text style={s.note}>Từ ngày (YYYY-MM-DD)</Text><TextInput accessibilityLabel="Từ ngày" editable={!busy} style={s.input} value={from} onChangeText={setFrom} placeholder="2026-10-21"/>
      <Text style={s.note}>Đến ngày</Text><TextInput accessibilityLabel="Đến ngày" editable={!busy} style={s.input} value={through} onChangeText={setThrough} placeholder="2026-10-22"/>
      <Text style={s.note}>Lý do (ít nhất 5 ký tự)</Text><TextInput accessibilityLabel="Lý do xin nghỉ" editable={!busy} multiline style={[s.input,{minHeight:75}]} value={reason} onChangeText={setReason} placeholder="Lý do xin nghỉ học"/>
      <Pressable disabled={busy||!from||!through||reason.trim().length<5} style={s.button} onPress={()=>run(async()=>{
        await at.requestLeave(token,tenant,studentId,from,through,reason);setReason('');await refresh();setMessage('Đã gửi đơn đến GVCN / nhà trường.');})}><Text style={s.buttonText}>Gửi đơn xin nghỉ</Text></Pressable>
      <Text style={s.heading}>Các đơn đã gửi</Text>
      {leaves.map(l=><View key={l.id} style={s.item}><Text>{l.from_date} → {l.through_date} · {words[l.state]}</Text><Text style={s.note}>{l.reason}</Text>
        {l.decision_note?<Text style={s.note}>Nhận xét: {l.decision_note}</Text>:null}
        {l.state==='PENDING'&&<Pressable disabled={busy} onPress={()=>run(async()=>{await at.withdraw(token,tenant,l.id);await refresh();})}><Text style={s.link}>Rút đơn</Text></Pressable>}
      </View>)}
    </>}
    {busy&&<ActivityIndicator color={GREEN}/>}{!!message&&<Text accessibilityRole="alert" style={s.note}>{message}</Text>}
  </View>;
}
const s=StyleSheet.create({card:{backgroundColor:'#fff',padding:20,borderRadius:16,borderWidth:1,borderColor:'#DDE4EF',marginTop:22},
 heading:{fontSize:18,fontWeight:'800',color:'#162440',marginTop:14,marginBottom:8},note:{fontSize:13,color:'#637089',marginTop:7},
 tab:{padding:10,borderWidth:1,borderColor:'#DDE4EF',borderRadius:10,marginVertical:4},active:{backgroundColor:'#D3F4E9',borderColor:GREEN},
 item:{borderBottomWidth:1,borderColor:'#E4EAF0',paddingVertical:11},input:{padding:12,borderWidth:1,borderColor:'#DDE4EF',borderRadius:8,marginTop:5},
 button:{padding:14,backgroundColor:GREEN,marginTop:16,alignItems:'center',borderRadius:9},buttonText:{fontWeight:'800',color:'#fff'},link:{color:GREEN,fontWeight:'800',paddingTop:8}});
