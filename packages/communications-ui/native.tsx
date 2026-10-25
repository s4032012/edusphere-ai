import {View,Text,TextInput,Pressable,StyleSheet,Alert,ActivityIndicator} from 'react-native';
import {communicationLabels as labels} from '@edusphere/api-client';
import {useCommunications,type Props} from './controller';
function Button({text,disabled,onPress}:{text:string;disabled:boolean;onPress:()=>void}){return <Pressable accessibilityRole="button" accessibilityState={{disabled}} disabled={disabled} onPress={onPress} style={[styles.button,disabled&&{opacity:.5}]}><Text style={styles.buttonText}>{text}</Text></Pressable>;}
export function CommunicationCenter(p:Props){
 const c=useCommunications(p),when=(s:string)=>new Date(s).toLocaleString('vi-VN');
 const btn=(text:string,fn:()=>Promise<void>,disabled=false)=><Button text={text} disabled={c.busy||disabled} onPress={()=>void c.run(fn)}/>;
 const input=(label:string,value:string,set:(v:string)=>void,max=5000,multiline=true)=><TextInput accessibilityLabel={label} placeholder={label} value={value} onChangeText={set} editable={!c.busy} maxLength={max} multiline={multiline} style={styles.input}/>;
 return <View style={styles.panel}><Text style={styles.heading}>Liên lạc & thông báo</Text>
 {btn('Làm mới liên lạc',c.refresh)}{c.busy&&<ActivityIndicator accessibilityLabel="Đang xử lý"/>}
 {!!c.error&&<Text accessibilityRole="alert" style={styles.error}>{c.error}</Text>}{!!c.success&&<Text accessibilityRole="alert" style={styles.success}>{c.success}</Text>}
 {c.compose&&<View><Text style={styles.heading}>Soạn thông báo lớp</Text><Text>Chọn lớp nhận thông báo:</Text>
 {c.classes.map(x=><View key={x.id}>{btn(`${c.classId===x.id?'✓ ':''}${x.code}`,async()=>c.setClassId(x.id))}</View>)}
 {!c.classes.length&&<Text>Chưa có lớp được phân công.</Text>}
 {input('Tiêu đề thông báo',c.title,c.setTitle,180,false)}{input('Nội dung thông báo',c.body,c.setBody,12000)}
 {btn('Lưu bản nháp',c.createNotice,!c.classId||!c.title.trim()||!c.body.trim())}</View>}
 <Text style={styles.heading}>Thông báo nhà trường</Text>{!c.notices.length&&<Text>Chưa có thông báo trong phạm vi của bạn.</Text>}
 {c.notices.map(n=><View key={n.id} style={styles.entry}><Text style={styles.bold}>{n.title} · {labels[n.state]}</Text>
 <Text style={styles.small}>{when(n.published_at||n.created_at)}{n.recipient_count!==null&&` · ${n.read_count}/${n.recipient_count} đã đọc`}</Text><Text selectable>{n.body}</Text>
 {n.can_publish&&<Button text="Công bố" disabled={c.busy} onPress={()=>Alert.alert('Công bố thông báo',`“${n.title}” sẽ được gửi đến lớp đã chọn và không thể chỉnh sửa.`,[{text:'Hủy',style:'cancel'},{text:'Công bố',onPress:()=>void c.run(()=>c.publish(n.id))}])}/>}
 {n.state==='PUBLISHED'&&!n.read&&btn('Đánh dấu thông báo đã đọc',()=>c.readNotice(n.id))}</View>)}
 {c.canChat&&<View><Text style={styles.heading}>Trao đổi phụ huynh – giáo viên</Text><Text>Chọn học sinh để xem liên hệ được xác minh:</Text>
 {c.students.map(s=><View key={s.id}>{btn(`${c.studentId===s.id?'✓ ':''}${s.full_name}`,()=>c.pickStudent(s.id))}</View>)}
 {!!c.studentId&&!c.contacts.length&&<Text>Không có liên hệ đang được xác minh.</Text>}
 {c.contacts.map(x=><View key={x.id}>{btn('Trao đổi với '+x.name,()=>c.startThread(x.id))}</View>)}
 {!c.threads.length&&<Text>Chưa có hội thoại.</Text>}
 {c.threads.map(t=><View key={t.id}>{btn(`${t.student_name} · ${p.mode==='parent'?t.teacher_name:t.guardian_name} · ${t.unread_count} chưa đọc`,()=>c.openThread(t.id))}</View>)}
 {c.thread&&<View style={styles.entry}><Text style={styles.bold}>{c.thread.student_name} · {c.thread.teacher_name} ↔ {c.thread.guardian_name}</Text>
 {!c.messages.length&&<Text>Chưa có tin nhắn.</Text>}{c.messages.map(m=><View key={m.id} style={{paddingVertical:8}}><Text style={styles.small}>{m.sender_id===p.userId?'Bạn':'Người liên hệ'} · {when(m.created_at)}</Text><Text selectable>{m.body}</Text></View>)}
 {input('Tin nhắn',c.draft,c.setDraft)}{btn('Gửi tin nhắn',c.send,!c.draft.trim())}</View>}</View>}
 {p.mode==='parent'&&<View><Text style={styles.heading}>Yêu cầu hỗ trợ nhà trường</Text><Text>Loại yêu cầu:</Text>
 {['ACCOUNT','ACADEMIC_RECORD','SCHEDULE','FEES','OTHER'].map(v=><View key={v}>{btn(`${c.category===v?'✓ ':''}${labels[v]}`,async()=>c.setCategory(v))}</View>)}
 <Text>Học sinh liên quan (không bắt buộc):</Text>{btn(`${!c.ticketStudent?'✓ ':''}Yêu cầu chung`,async()=>c.setTicketStudent(''))}
 {c.students.map(s=><View key={s.id}>{btn(`${c.ticketStudent===s.id?'✓ ':''}${s.full_name}`,async()=>c.setTicketStudent(s.id))}</View>)}
 {input('Tiêu đề yêu cầu',c.subject,c.setSubject,180,false)}{input('Mô tả vấn đề',c.details,c.setDetails)}{btn('Gửi yêu cầu hỗ trợ',c.createTicket,!c.subject.trim()||!c.details.trim())}
 {!c.tickets.length&&<Text>Chưa có yêu cầu hỗ trợ.</Text>}
 {c.tickets.map(t=><View key={t.id}>{btn(`${t.subject} · ${labels[t.state]}`,()=>c.openTicket(t.id))}</View>)}
 {c.ticket&&<View style={styles.entry}><Text style={styles.bold}>{c.ticket.subject} · {labels[c.ticket.state]}</Text><Text>{c.ticket.details}</Text>
 {(c.ticket.replies||[]).map(r=><View key={r.id} style={{paddingVertical:8}}><Text style={styles.small}>{r.author_id===p.userId?'Bạn':'Nhân viên hỗ trợ'} · {when(r.created_at)}</Text><Text>{r.body}</Text></View>)}
 {c.ticket.state!=='CLOSED'&&<>{input('Phản hồi hỗ trợ',c.reply,c.setReply)}{btn('Gửi phản hồi',c.replyTicket,!c.reply.trim())}</>}</View>}</View>}
 <Text style={styles.heading}>Hộp thông báo · {c.inbox.filter(n=>!n.read).length} chưa đọc</Text>
 {!c.inbox.length&&<Text>Hộp thông báo trống.</Text>}{c.inbox.map(n=><View key={n.id} style={styles.entry}><Text>{labels[n.type]||'Cập nhật'} · {n.read?'Đã đọc':'Chưa đọc'}</Text><Text style={styles.small}>{when(n.created_at)}</Text>{!n.read&&btn('Đánh dấu đã đọc',()=>c.readEvent(n.id))}</View>)}
 <Text style={styles.small}>Tối đa 100 mục gần đây. Bấm làm mới để cập nhật; chưa có gửi push/email/SMS.</Text></View>;
}
const styles=StyleSheet.create({panel:{marginTop:20,backgroundColor:'#fff',padding:18,borderRadius:16,borderWidth:1,borderColor:'#DFE5F0'},
 heading:{fontSize:19,color:'#142845',fontWeight:'800',marginTop:20,marginBottom:10},bold:{fontWeight:'700',color:'#142845'},
 entry:{padding:12,marginVertical:5,backgroundColor:'#F5F8FC',borderRadius:10},small:{color:'#637089',fontSize:12,marginVertical:7},
 button:{backgroundColor:'#146D79',borderRadius:9,padding:14,marginVertical:5,minHeight:48,justifyContent:'center'},buttonText:{color:'#fff',fontWeight:'700'},
 input:{padding:14,marginTop:8,borderWidth:1,borderColor:'#CCD6E4',borderRadius:9,color:'#142845'},error:{color:'#B42318',marginTop:12},success:{color:'#067647',marginTop:12}});
