import {ActivityIndicator,Pressable,StyleSheet,Text,View} from 'react-native';
import {communicationLabels,type DashboardHomework} from '@edusphere/api-client';
import {useDashboard,type DashboardProps} from './dashboard-controller';
const states:Record<string,string>={NOT_SUBMITTED:'Chưa nộp',OVERDUE:'Quá hạn, chưa nộp',IN_PROGRESS:'Đang làm',SUBMITTED:'Đã nộp',RETURNED:'Đã trả',PASS:'Đạt',FAIL:'Chưa đạt',EXEMPT:'Miễn'};
const sources:Record<string,string>={submitted_or_locked_attendance:'Điểm danh đã nộp hoặc khóa',published_homework_and_own_submissions:'Bài tập đã giao và bài nộp của học sinh',published_assessments_only:'Đánh giá đã công bố'};
function Button({text,disabled=false,onPress,color}:{text:string;disabled?:boolean;onPress:()=>void;color:string}){
 return <Pressable accessibilityRole="button" accessibilityState={{disabled}} disabled={disabled} onPress={onPress} style={[s.button,{backgroundColor:color},disabled&&{opacity:.5}]}><Text style={s.buttonText}>{text}</Text></Pressable>;
}
export function DashboardPanel(p:DashboardProps){
 const c=useDashboard(p),d=c.data,color=p.mode==='parent'?'#117C63':'#6B49BC';
 const when=(x:string)=>new Date(x).toLocaleString('vi-VN');
 const homeworkRow=(h:DashboardHomework)=><View key={h.id} style={s.item}><Text style={s.bold}>{h.title}</Text><Text style={s.line}>{h.subject} · {states[h.status]}{h.assignment_state==='CLOSED'?' · Đã đóng':''}</Text><Text style={s.muted}>Hạn: {when(h.due_at)}</Text>{h.actionable?<Text style={s.muted}>Mở phần Bài tập bên dưới để tiếp tục.</Text>:h.status==='OVERDUE'&&<Text style={s.muted}>Không còn nhận bài; liên hệ giáo viên nếu cần hỗ trợ.</Text>}{h.feedback_available&&<Text style={s.muted}>Đã có phản hồi trong phần Bài tập.</Text>}</View>;
 const homework=d&&<View><Text style={s.section}>{p.mode==='student'?'Nhiệm vụ cần làm':'Bài tập của con'} · tối đa 8 bài</Text>
 {p.mode==='student'?<>{d.homework.items.filter(h=>h.actionable).map(homeworkRow)}{!d.homework.summary.pending_action&&<Text style={s.muted}>{d.homework.summary.total?'Hiện không có bài chưa nộp còn nhận bài.':'Chưa có bài tập đã công bố.'}</Text>}
 {d.homework.items.some(h=>!h.actionable)&&<Text style={s.section}>Bài tập đã ghi nhận</Text>}{d.homework.items.filter(h=>!h.actionable).map(homeworkRow)}</>:<>{d.homework.items.map(homeworkRow)}{!d.homework.summary.total&&<Text style={s.muted}>Chưa có bài tập đã công bố.</Text>}</>}
 {!!d.homework.summary.total&&<Text style={s.muted}>{d.homework.summary.submitted_or_returned}/{d.homework.summary.total} bài đã nộp hoặc được trả · {d.homework.summary.overdue} bài quá hạn chưa nộp (kể cả bài đã đóng).</Text>}</View>;
 return <View style={s.card}><Text accessibilityRole="header" style={[s.title,{color}]}>{p.mode==='parent'?'Tổng quan học tập của con':'Tiến độ của em'}</Text>
 <Button text="Làm mới tổng quan" disabled={c.loading} onPress={()=>void c.refresh()} color={color}/>
 {!!c.children.length&&<Text style={s.muted}>{p.mode==='parent'?'Chọn con đang xem:':'Hồ sơ được liên kết:'}</Text>}
 {c.children.map(child=><Pressable key={child.id} accessibilityRole="button" accessibilityState={{selected:c.studentId===child.id}} onPress={()=>void c.select(child.id)} style={[s.child,c.studentId===child.id&&{borderColor:color,backgroundColor:p.mode==='parent'?'#EAF7F2':'#F4F0FB'}]}><Text style={s.bold}>{c.studentId===child.id?'✓ ':''}{child.full_name}</Text><Text style={s.muted}>{child.student_code}</Text></Pressable>)}
 {c.loading&&<ActivityIndicator accessibilityLabel="Đang tải tổng quan" color={color}/>}
 {!!c.error&&<Text accessibilityRole="alert" style={s.error}>{c.error}{d?' Dữ liệu đang hiển thị là lần tải trước.':''}</Text>}
 {!c.loading&&!c.error&&!c.children.length&&<Text style={s.muted}>Chưa có hồ sơ học sinh được xác minh và liên kết với tài khoản. Vui lòng liên hệ nhà trường.</Text>}
 {d&&<><Text style={s.section}>{d.student.full_name} · {d.student.classroom?.code||'Chưa xác định lớp hiện tại'}</Text>
 <Text style={s.muted}>Cập nhật: {when(d.as_of)}</Text>
 {d.enrollment_status!=='CURRENT'&&<Text accessibilityRole="alert" style={s.warning}>{d.enrollment_status==='AMBIGUOUS'?'Có nhiều lớp đang ghi danh. Nhà trường cần kiểm tra trước khi tổng hợp.':'Chưa có ghi danh còn hiệu lực trong năm học hiện tại.'}</Text>}
 {p.mode==='student'&&homework}
 <View style={s.metrics}>{[
  [d.attendance.recorded_days?String(d.attendance.recorded_days):'—','Ngày có điểm danh'],
  [d.attendance.recorded_days?String(d.attendance.ABSENT):'—','Ngày vắng'],
  [d.homework.summary.total?String(d.homework.summary.overdue):'—','Bài quá hạn chưa nộp'],
 ].map(([value,label])=><View key={label} style={s.metric}><Text style={[s.number,{color}]}>{value}</Text><Text style={s.metricLabel}>{label}</Text></View>)}</View>
 <Text style={s.section}>Chuyên cần trong 30 ngày</Text><Text style={s.muted}>{d.attendance.recorded_days?`${d.attendance.PRESENT} có mặt · ${d.attendance.ABSENT} vắng · ${d.attendance.LATE} đi muộn. Chỉ tính ngày có điểm danh đã nộp/khóa.`:'Chưa có dữ liệu điểm danh đã nộp/khóa trong 30 ngày; không suy ra có mặt hay vắng.'}</Text>
 <Text style={s.section}>Kết quả đã công bố · tối đa 8 kết quả</Text>
 {d.grades.items.map(g=><View key={g.assessment_id} style={s.item}><Text style={s.bold}>{g.subject} · {g.score??(g.result?states[g.result]||g.result:'Chưa có kết quả')}</Text><Text style={s.line}>{g.title} · Học kỳ {g.semester}</Text>{!!g.note&&<Text style={s.line}>{g.note}</Text>}{!!g.published_at&&<Text style={s.muted}>Công bố: {when(g.published_at)}</Text>}</View>)}
 {!d.grades.items.length&&<Text style={s.muted}>Chưa có kết quả đã công bố trong phạm vi hiện tại.</Text>}
 {p.mode==='parent'&&homework}
 <Text style={s.section}>Thông báo đúng phạm vi học sinh · tối đa 5</Text>
 {d.announcements.map(n=><View key={n.id} style={s.item}><Text style={s.bold}>{n.title}</Text><Text style={s.muted}>{n.read?'Đã đọc':'Chưa đọc'} · {communicationLabels[n.scope]}{n.published_at?' · '+when(n.published_at):''}</Text></View>)}
 {!d.announcements.length&&<Text style={s.muted}>Chưa có thông báo dành cho học sinh đang xem.</Text>}
 <Text style={s.section}>Cập nhật tài khoản · tối đa 5</Text><Text style={s.muted}>Có thể liên quan đến nhiều học sinh. Mở phần Liên lạc & thông báo để xem chi tiết và đánh dấu đã đọc.</Text>
 {d.notifications.items.map(e=><Text key={e.id} style={s.line}>{communicationLabels[e.event_type]||'Cập nhật'} · {e.read?'Đã đọc':'Chưa đọc'} · {when(e.created_at)}</Text>)}
 {!d.notifications.items.length&&<Text style={s.muted}>Chưa có cập nhật tài khoản được phép xem.</Text>}
 {p.mode==='parent'&&<><Button text="Xem tóm tắt theo quy tắc" disabled={c.loading||c.previewLoading} onPress={()=>void c.showPreview()} color={color}/>
 {c.previewLoading&&<ActivityIndicator accessibilityLabel="Đang tải tóm tắt" color={color}/>}{!!c.previewError&&<Text accessibilityRole="alert" style={s.error}>{c.previewError}</Text>}
 {c.preview&&<View style={s.preview}><Text style={s.bold}>Tóm tắt dữ liệu · chưa sử dụng AI</Text><Text style={s.muted}>Cập nhật: {when(c.preview.as_of)}. Không gửi dữ liệu sang nhà cung cấp AI.</Text>
 {c.preview.sentences.map(x=><View key={x.kind} style={s.item}><Text style={s.line}>{x.text}</Text><Text style={s.muted}>Nguồn: {sources[x.source]||x.source}</Text></View>)}{c.preview.limitations.map(x=><Text key={x} style={s.muted}>{x}</Text>)}</View>}</>}
 <Text style={s.section}>Phạm vi dữ liệu</Text>{d.data_limits.map(x=><Text key={x} style={s.muted}>• {x}</Text>)}</>}
 </View>;
}
const s=StyleSheet.create({card:{marginTop:22,padding:20,borderRadius:18,backgroundColor:'#fff',borderColor:'#DDE4EF',borderWidth:1},
 title:{fontSize:22,fontWeight:'800'},section:{fontSize:16,fontWeight:'700',color:'#20304D',marginTop:20,marginBottom:6},
 child:{padding:14,borderWidth:1,borderColor:'#DDE4EF',borderRadius:10,marginVertical:5,minHeight:48},
 button:{minHeight:48,padding:14,borderRadius:10,marginTop:14,alignItems:'center',justifyContent:'center'},buttonText:{color:'#fff',fontWeight:'700',textAlign:'center'},
 metrics:{flexDirection:'row',flexWrap:'wrap',gap:8,marginTop:18},metric:{flexGrow:1,flexBasis:90,padding:12,borderRadius:10,backgroundColor:'#F2F6FA'},number:{fontSize:25,fontWeight:'800'},metricLabel:{fontSize:12,color:'#43536B',marginTop:5},
 item:{padding:12,borderRadius:10,marginTop:8,backgroundColor:'#F5F7FB'},bold:{fontSize:14,fontWeight:'700',color:'#20304D'},line:{fontSize:14,color:'#283750',lineHeight:22,marginVertical:4},
 muted:{fontSize:12,color:'#637089',lineHeight:19,marginTop:5},error:{color:'#A62828',marginVertical:10},warning:{color:'#805500',backgroundColor:'#FFF7E5',padding:12,marginTop:12,borderRadius:8},preview:{marginTop:14,padding:12,borderRadius:12,backgroundColor:'#EAF7F2'}});
