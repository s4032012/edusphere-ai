import {useEffect,useState} from 'react';
import {ActivityIndicator,Pressable,StyleSheet,Text,View} from 'react-native';
import {ApiError,createHomeworkApi,type Student,type StudentHomeworkOverview} from '@edusphere/api-client';
const api=createHomeworkApi(process.env.EXPO_PUBLIC_API_URL||'http://127.0.0.1:8000');
const labels:Record<string,string>={DRAFT:'Đang làm nháp',SUBMITTED:'Đã nộp',RETURNED:'Đã trả bài',NOT_SUBMITTED:'Chưa nộp',OVERDUE:'Quá hạn'};
export function HomeworkParent({token,tenant,students,onExpired}:{token:string;tenant:string;students:Student[];onExpired:()=>void}){
  const [chosen,setChosen]=useState(''),[data,setData]=useState<StudentHomeworkOverview|null>(null);
  const [reload,setReload]=useState(0);
  const [busy,setBusy]=useState(false),[message,setMessage]=useState('');
  useEffect(()=>{setChosen(students[0]?.id||'');setData(null);setReload(v=>v+1);},[students,tenant]);
  useEffect(()=>{setData(null);setMessage('');if(!chosen){setBusy(false);return;}let live=true;setBusy(true);
    api.student(token,tenant,chosen).then(x=>{if(live)setData(x);}).catch(e=>{if(live){if(e instanceof ApiError&&e.status===401)onExpired();else setMessage(e instanceof Error?e.message:'Không thể tải dữ liệu.');}})
      .finally(()=>{if(live)setBusy(false);});return()=>{live=false;};},[chosen,token,tenant,reload]);
  return <View style={s.card}><Text style={s.heading}>Bài tập của con</Text><Pressable accessibilityRole="button" style={s.item} disabled={busy} onPress={()=>setReload(v=>v+1)}><Text>Tải lại</Text></Pressable>
    {!students.length&&<Text style={s.muted}>Chưa có hồ sơ học sinh được phép xem.</Text>}
    {students.length>1&&students.map(child=><Pressable style={s.item} key={child.id} onPress={()=>{setData(null);setChosen(child.id);setReload(v=>v+1);}}><Text style={s.title}>{chosen===child.id?'✓ ':''}{child.full_name}</Text></Pressable>)}
    {busy&&<ActivityIndicator/>}{data?.items.map(row=><View key={row.assignment.id} style={s.item}>
      <Text style={s.title}>{row.assignment.title}</Text><Text style={s.muted}>{row.assignment.subject_name} · {labels[row.status]}</Text>
      <Text style={s.muted}>Hạn nộp: {new Date(row.assignment.due_at).toLocaleString('vi-VN')}</Text>
      {row.submission?.state==='RETURNED'&&<Text style={s.muted}>Nhận xét GV: {row.submission.feedback||'—'} · Điểm bài tập: {row.submission.score||'—'}</Text>}
    </View>)}
    {!busy&&data?.items.length===0&&<Text style={s.muted}>Chưa có bài tập được giao.</Text>}
    {message&&<Text accessibilityRole="alert" style={s.muted}>{message}</Text>}
    <Text style={s.muted}>Phụ huynh chỉ xem; không thể nộp bài thay học sinh.</Text>
  </View>;
}
const s=StyleSheet.create({card:{backgroundColor:'#fff',padding:20,borderRadius:16,marginTop:20},heading:{fontWeight:'800',fontSize:18,color:'#192B46'},
 item:{minHeight:44,marginTop:12,paddingTop:12,borderTopWidth:1,borderColor:'#E3EAF3'},title:{fontWeight:'700',fontSize:15,color:'#192B46'},
 muted:{color:'#65748A',fontSize:13,marginTop:7}});
