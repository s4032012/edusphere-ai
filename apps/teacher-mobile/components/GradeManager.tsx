import {useEffect,useState,useRef} from 'react';
import {ActivityIndicator,Alert,Pressable,StyleSheet,Text,TextInput,View} from 'react-native';
import {ApiError,createGradesApi,type GradeBook,type GradeBookDetail,type AssessmentKind} from '@edusphere/api-client';
const api=createGradesApi(process.env.EXPO_PUBLIC_API_URL||'http://127.0.0.1:8000');
export function GradeManager({token,tenant,onExpired}:{token:string;tenant:string;onExpired:()=>void}){
  const live=useRef(true), pending=useRef(false), selection=useRef(0);
  useEffect(()=>{live.current=true;return()=>{live.current=false;selection.current++;};},[]);
  function failed(e:unknown){if(!live.current)return;if(e instanceof ApiError&&e.status===401)onExpired();else setMsg(e instanceof Error?e.message:'Không thể tải dữ liệu.');}

  const [books,setBooks]=useState<GradeBook[]>([]),[book,setBook]=useState<GradeBookDetail|null>(null),[selected,setSelected]=useState('');
  const [kind,setKind]=useState<AssessmentKind>('TX'),[title,setTitle]=useState(''),[slot,setSlot]=useState('1');
  const [scores,setScores]=useState<Record<string,string>>({}),[busy,setBusy]=useState(false),[msg,setMsg]=useState('');
  async function refresh(){const bs=await api.books(token,tenant);setBooks(bs);if(selected)setBook(await api.book(token,tenant,selected));}
  useEffect(()=>{setBooks([]);setBook(null);setSelected('');void api.books(token,tenant).then(setBooks).catch(failed);},[token,tenant]);
  async function choose(id:string){const ticket=++selection.current;setSelected(id);setBook(null);setScores({});try{const data=await api.book(token,tenant,id);if(live.current&&ticket===selection.current)setBook(data);}catch(e){failed(e);}}
  async function run(fn:()=>Promise<unknown>){if(pending.current)return;pending.current=true;setBusy(true);setMsg('');try{await fn();setMsg('Đã lưu.');await refresh();}
    catch(e){failed(e);}finally{pending.current=false;if(live.current)setBusy(false);}}
  return <View style={s.card}><Text style={s.heading}>Sổ điểm · Sprint 3</Text>
    <Pressable disabled={busy} onPress={()=>void run(async()=>{})}><Text style={s.action}>Làm mới</Text></Pressable>
    {books.map(b=><Pressable key={b.id} disabled={busy} style={s.row} onPress={()=>void choose(b.id)}><Text style={s.action}>{b.classroom_code} · {b.subject_name} · HK{b.semester}</Text></Pressable>)}
    {book&&<>{book.can_edit&&<><Text style={s.heading}>Tạo cột đánh giá</Text><View style={s.row}><Text style={s.label}>Loại</Text>{(['TX','GK','CK'] as AssessmentKind[]).map(k=><Pressable key={k} disabled={busy} onPress={()=>{setKind(k);if(k!=='TX')setSlot('1');}} style={s.chip}><Text style={{color:kind===k?'#146D79':'#777'}}>{k}</Text></Pressable>)}</View>
      <TextInput editable={!busy} style={s.input} value={slot} onChangeText={setSlot} keyboardType="numeric" accessibilityLabel="Slot" placeholder="Slot" />
      <TextInput editable={!busy} style={s.input} value={title} onChangeText={setTitle} accessibilityLabel="Tên cột điểm" placeholder="Tên cột điểm"/>
      <Pressable style={s.btn} disabled={busy||title.trim().length<2} onPress={()=>void run(()=>api.createAssessment(token,tenant,book.id,kind,Number(slot),title))}><Text style={s.btnText}>Tạo cột</Text></Pressable></>}
      {book.assessments.map(a=><View key={a.id} style={s.item}><Text style={s.heading}>{a.kind}{a.slot} · {a.title} · {a.state}</Text>
        {a.entries?.map(e=><View key={e.student_id} style={s.item}><Text>{e.full_name}</Text>{book.can_edit&&a.state==='DRAFT'?
          <TextInput editable={!busy} style={s.input} accessibilityLabel={'Điểm '+e.full_name} keyboardType={book.mode==='SCORE'?'decimal-pad':'default'}
          placeholder={book.mode==='SCORE'?e.score||'Điểm 0–10':e.result||'PASS / FAIL'}
          value={scores[a.id+e.student_id]??(book.mode==='SCORE'?e.score||'':e.result||'')}
          onChangeText={v=>setScores(old=>({...old,[a.id+e.student_id]:v}))}/>
          :<Text>{e.score??e.result??'—'}</Text>}</View>)}
        {book.can_edit&&a.state==='DRAFT'&&<><Pressable style={s.btn} disabled={busy} onPress={()=>void run(()=>api.saveGrades(token,tenant,a.id,(a.entries||[]).map(e=>({student_id:e.student_id,
          ...(book.mode==='SCORE'?{score:scores[a.id+e.student_id]??e.score??''}:{result:scores[a.id+e.student_id]??e.result??''})}))))}><Text style={s.btnText}>Lưu điểm cả lớp</Text></Pressable>
          <Pressable style={s.btnOutline} disabled={busy} onPress={()=>Alert.alert('Khóa cột điểm','Lưu giá trị hiện tại và khóa? Sau đó sửa điểm phải qua yêu cầu điều chỉnh.',[{text:'Hủy',style:'cancel'},{text:'Lưu và khóa',onPress:()=>void run(async()=>{await api.saveGrades(token,tenant,a.id,(a.entries||[]).map(e=>({student_id:e.student_id,...(book.mode==='SCORE'?{score:scores[a.id+e.student_id]??e.score??''}:{result:scores[a.id+e.student_id]??e.result??''})})));await api.lock(token,tenant,a.id);})}])}><Text>Khóa cột điểm</Text></Pressable></>}</View>)}
    </>}
    {busy&&<ActivityIndicator/>}{!!msg&&<Text style={s.message}>{msg}</Text>}
  </View>;
}
const s=StyleSheet.create({card:{backgroundColor:'white',padding:18,borderRadius:16,marginTop:20,borderWidth:1,borderColor:'#DDE4EF'},
 heading:{fontSize:16,fontWeight:'800',color:'#192B46',marginVertical:12},row:{flexDirection:'row',flexWrap:'wrap',alignItems:'center',gap:8,paddingVertical:10},
 label:{fontSize:13},chip:{padding:10,borderWidth:1,borderColor:'#DDE4EF',borderRadius:8},action:{color:'#146D79',fontWeight:'700'},
 input:{borderWidth:1,borderColor:'#DDE4EF',padding:12,borderRadius:8,marginVertical:7},btn:{backgroundColor:'#146D79',padding:13,borderRadius:8,marginTop:10},
 btnText:{color:'#fff',fontWeight:'800',textAlign:'center'},btnOutline:{borderWidth:1,borderColor:'#146D79',padding:12,borderRadius:8,marginTop:8},
 item:{borderTopWidth:1,borderTopColor:'#EEF1F5',paddingVertical:9},message:{color:'#146D79',marginTop:12}});
