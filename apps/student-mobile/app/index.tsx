import {useEffect,useState,useRef} from 'react';
import {ActivityIndicator,Pressable,SafeAreaView,ScrollView,StyleSheet,Text,TextInput,View} from 'react-native';
import * as SecureStore from 'expo-secure-store';
import {ApiError,createRequestScope,createApi,membershipsFor,ROLES,type CurrentUser,type Student} from '@edusphere/api-client';
const API_URL=process.env.EXPO_PUBLIC_API_URL || 'http://127.0.0.1:8000';
const api=createApi(API_URL);
const accessKey='edusphere.student.access';
const allowed=ROLES.student;
const accent='#6B49BC';
export default function Home(){
  const [username,setUsername]=useState('student_a');const [password,setPassword]=useState('');
  const [token,setToken]=useState('');const [user,setUser]=useState<CurrentUser|null>(null);
  const [tenant,setTenant]=useState('');const [students,setStudents]=useState<Student[]>([]);
  const [loading,setLoading]=useState(true);const [working,setWorking]=useState(false);const [error,setError]=useState('');
  const scope=useRef(createRequestScope());
  useEffect(()=>{
    if(!user)return;
    const timer=setTimeout(()=>{void signOut();setError('Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.');},Math.max(0,user.session_expires_at*1000-Date.now()));
    return ()=>clearTimeout(timer);
  },[user]);
  const memberships=user?membershipsFor(user,allowed):[];
  useEffect(()=>{let live=true;(async()=>{try{const saved=await SecureStore.getItemAsync(accessKey);
    if(!saved)return;const me=await api.me(saved);const scoped=membershipsFor(me,allowed);
    if(live&&scoped.length){setUser(me);setToken(saved);setTenant(scoped[0].tenant_id);}
    else await SecureStore.deleteItemAsync(accessKey);
  }catch{await SecureStore.deleteItemAsync(accessKey);}finally{if(live)setLoading(false);}})();return()=>{live=false;};},[]);
  async function signIn(){setWorking(true);setError('');try{
    const pair=await api.login(username,password);const me=await api.me(pair.access);
    const scoped=membershipsFor(me,allowed);
    if(!scoped.length){setError('Tài khoản không có quyền sử dụng EduSphere Student.');return;}
    await SecureStore.setItemAsync(accessKey,pair.access);
    setToken(pair.access);setUser(me);setTenant(scoped[0].tenant_id);setPassword('');
  }catch(e){setError(e instanceof Error?e.message:'Đăng nhập thất bại');}finally{setWorking(false);}}
  async function loadStudents(){const current=scope.current.capture();setWorking(true);setError('');setStudents([]);
    try{const rows=await api.students(token,tenant);if(current())setStudents(rows);}
    catch(e){if(current()){if(e instanceof ApiError&&e.status===401)await signOut();setError(e instanceof ApiError&&e.status===401?'Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.':e instanceof Error?e.message:'Không thể tải danh sách');}}
    finally{if(current())setWorking(false);}}
  async function signOut(){scope.current.invalidate();setWorking(false);setToken('');setUser(null);setTenant('');setStudents([]);setPassword('');
    try{await SecureStore.deleteItemAsync(accessKey);}catch{setError('Không thể xóa phiên đã lưu. Vui lòng thử lại.');}}
  if(loading)return <SafeAreaView style={styles.page}><ActivityIndicator color={accent} size="large"/></SafeAreaView>;
  return <SafeAreaView style={styles.page}><ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
    <Text style={styles.kicker}>EDUSPHERE AI · SPRINT 0 v2</Text>
    <Text style={styles.title}>EduSphere Student</Text>
    <Text style={styles.desc}>Quản lý và học tập thông minh · dữ liệu demo</Text>
    {!user? <View style={styles.card}><Text style={styles.heading}>Đăng nhập</Text>
      <TextInput style={styles.input} accessibilityLabel="Tên tài khoản" value={username} onChangeText={setUsername} placeholder="Username" autoCapitalize="none"/>
      <TextInput style={styles.input} accessibilityLabel="Mật khẩu" value={password} onChangeText={setPassword} secureTextEntry placeholder="Password"/>
      <Pressable disabled={working||!username||!password} accessibilityRole="button" onPress={signIn} style={styles.button}><Text style={styles.buttonText}>Đăng nhập</Text></Pressable>
      <Text style={styles.small}>Tài khoản demo: student_a · mật khẩu xem README</Text></View>
    : <><View style={styles.card}><Text style={styles.heading}>Xin chào, {user.display_name}</Text>
      <Text style={styles.desc}>Vai trò hợp lệ trong ứng dụng:</Text>
      {memberships.map(m=><Pressable key={m.tenant_id+'-'+m.role} accessibilityRole="button" onPress={()=>{scope.current.invalidate();setWorking(false);setError('');setTenant(m.tenant_id);setStudents([]);}} style={[styles.tenant,tenant===m.tenant_id&&styles.tenantActive]}>
        <Text style={styles.tenantText}>{m.tenant} · {m.role}</Text></Pressable>)}
      <Pressable accessibilityRole="button" disabled={working} onPress={loadStudents} style={styles.button}><Text style={styles.buttonText}>Xem học sinh được phép</Text></Pressable>
      <Pressable accessibilityRole="button" onPress={signOut} style={styles.outline}><Text style={styles.outlineText}>Đăng xuất</Text></Pressable>
    </View><View style={styles.card}><Text style={styles.heading}>Danh sách học sinh</Text>
      {students.length===0?<Text style={styles.desc}>Chưa tải dữ liệu hoặc không có học sinh trong phạm vi được cấp quyền.</Text>
        :students.map(s=><View key={s.id} style={styles.student}><Text style={styles.studentName}>{s.full_name}</Text><Text style={styles.small}>{s.student_code}</Text></View>)}
    </View></>}
    {working?<ActivityIndicator accessibilityLabel="Đang tải" color={accent}/>:null}
    {error?<Text accessibilityRole="alert" style={styles.error}>{error}</Text>:null}
    <Text style={styles.footer}>PROTOTYPE • Chưa có refresh token, push notification, AI hay các thao tác ghi điểm.</Text>
  </ScrollView></SafeAreaView>;
}
const styles=StyleSheet.create({
  page:{flex:1,backgroundColor:'#F5F8FC'},content:{padding:24,paddingTop:48,paddingBottom:48},
  kicker:{fontSize:12,color:accent,fontWeight:'800',letterSpacing:1.2},title:{fontSize:32,color:'#162440',fontWeight:'800',marginTop:12},
  desc:{fontSize:14,color:'#637089',lineHeight:21,marginTop:10},card:{backgroundColor:'#fff',borderRadius:16,padding:22,borderColor:'#DDE4EF',borderWidth:1,marginTop:22},
  heading:{fontSize:18,color:'#162440',fontWeight:'700',marginBottom:12},
  input:{backgroundColor:'#F8FAFD',borderWidth:1,borderColor:'#DDE4EF',borderRadius:10,padding:14,marginTop:10,fontSize:16},
  button:{backgroundColor:accent,padding:16,borderRadius:10,marginTop:15,alignItems:'center',minHeight:48},
  buttonText:{color:'white',fontWeight:'800',fontSize:15},small:{fontSize:12,color:'#6D7790',marginTop:10},
  tenant:{padding:12,borderRadius:10,borderWidth:1,borderColor:'#DDE4EF',marginTop:8},
  tenantActive:{borderColor:accent,backgroundColor:'#ECF4FF'},tenantText:{color:'#162440'},
  outline:{borderColor:accent,borderWidth:1,borderRadius:10,padding:14,alignItems:'center',marginTop:10},
  outlineText:{color:accent,fontWeight:'700'},student:{paddingVertical:12,borderBottomColor:'#E5EAF2',borderBottomWidth:1},
  studentName:{color:'#162440',fontWeight:'700'},error:{color:'#BA2727',marginTop:18},
  footer:{fontSize:11,color:'#8993A4',marginTop:36},
});
