import {useEffect,useState,useRef} from 'react';
import {ActivityIndicator,Pressable,StyleSheet,Text,View} from 'react-native';
import {ApiError,createGradesApi,type Student,type StudentGrades} from '@edusphere/api-client';
const api=createGradesApi(process.env.EXPO_PUBLIC_API_URL||'http://127.0.0.1:8000');
const kinds:Record<string,string>={TX:'Thường xuyên',GK:'Giữa kỳ',CK:'Cuối kỳ'};
export function GradeViewer({token,tenant,students,onExpired}:{token:string;tenant:string;students:Student[];onExpired:()=>void}){
  const live=useRef(true), pending=useRef(false), selection=useRef(0);
  useEffect(()=>{live.current=true;return()=>{live.current=false;selection.current++;};},[]);
  function failed(e:unknown){if(!live.current)return;if(e instanceof ApiError&&e.status===401)onExpired();else setError(e instanceof Error?e.message:'Không thể tải dữ liệu.');}

  const [selected,setSelected]=useState(''),[grades,setGrades]=useState<StudentGrades|null>(null);
  const [busy,setBusy]=useState(false),[error,setError]=useState('');const [refresh,setRefresh]=useState(0);
  useEffect(()=>{setSelected(students[0]?.id||'');setGrades(null);},[students,tenant]);
  useEffect(()=>{setGrades(null);setError('');if(!selected)return;let active=true;setBusy(true);
    api.student(token,tenant,selected).then(x=>{if(active)setGrades(x);}).catch(e=>{if(active)failed(e);})
    .finally(()=>{if(active)setBusy(false);});return()=>{active=false;};},[selected,tenant,token,refresh]);
  return <View style={s.card}><Text style={s.heading}>Kết quả học tập · Đã công bố</Text><Pressable accessibilityRole="button" disabled={busy} onPress={()=>setRefresh(v=>v+1)}><Text style={s.total}>Tải lại kết quả</Text></Pressable>
    {students.length>1&&students.map(st=><Pressable key={st.id} style={s.choice} onPress={()=>setSelected(st.id)}>
      <Text style={{fontWeight:selected===st.id?'800':'400'}}>{st.full_name}</Text></Pressable>)}
    {!students.length&&<Text>Chưa có hồ sơ học sinh được phép xem.</Text>}
    {busy&&<ActivityIndicator/>}{error&&<Text accessibilityRole="alert">{error}</Text>}
    {grades?.books.map(b=><View key={b.id} style={s.section}><Text style={s.subject}>{b.subject_name} · Học kỳ {b.semester}</Text>
      {b.assessments.map((a,i)=><Text key={`${a.kind}-${a.slot}-${i}`} style={s.line}>{kinds[a.kind]} {a.slot}: {a.score??a.result} — {a.title}</Text>)}
      <Text style={s.total}>{b.mode==='SCORE'?`Điểm TB học kỳ: ${b.semester_average??'Chưa đủ dữ liệu'}`:
        `Đánh giá học kỳ: ${b.semester_result==='PASS'?'Đạt':b.semester_result==='FAIL'?'Chưa đạt':'Chưa đủ dữ liệu'}`}</Text>
    </View>)}
    {grades&&!grades.books.some(b=>b.assessments.length>0)&&<Text style={s.note}>Chưa có điểm nào được nhà trường công bố.</Text>}
    <Text style={s.note}>Các kết quả chưa công bố không hiển thị. Điểm TB chỉ được tính khi đủ các cột theo cấu hình.</Text>
  </View>;
}
const s=StyleSheet.create({card:{padding:20,backgroundColor:'#fff',borderWidth:1,borderColor:'#DDE4EF',borderRadius:16,marginTop:22},
 heading:{fontSize:18,fontWeight:'800',color:'#192B46',marginBottom:12},choice:{padding:12,borderBottomWidth:1,borderColor:'#E6EBF4'},
 section:{paddingTop:14,marginTop:8,borderTopColor:'#E6EBF4',borderTopWidth:1},subject:{fontSize:16,fontWeight:'800',color:'#192B46'},
 line:{fontSize:14,color:'#424E66',paddingTop:8},total:{fontWeight:'700',color:'#237463',paddingTop:12},
 note:{fontSize:12,color:'#778197',lineHeight:18,marginTop:10}});
