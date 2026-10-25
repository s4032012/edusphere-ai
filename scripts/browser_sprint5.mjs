// Requires running seeded backend and Admin/Teacher/Support dev servers.
// Creates synthetic Sprint 5 QA records; does not delete existing data.
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
import assert from 'node:assert/strict';
const browser=await chromium.launch({channel:'chrome',headless:true,timeout:20000});
const errors=[];const page=await browser.newPage({viewport:{width:1365,height:1000}});page.setDefaultTimeout(20000);page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto('http://127.0.0.1:5174');
 await page.getByLabel('Username').fill('gvcn_a');await page.getByLabel('Password').fill('DemoOnly!ChangeMe123');await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await page.getByRole('heading',{name:'Liên lạc & thông báo',exact:true}).waitFor();
 await page.getByLabel('Lớp nhận thông báo').selectOption({label:'8A1'});
 const title='Sprint 5 QA '+Date.now();await page.getByLabel('Tiêu đề thông báo',{exact:true}).fill(title);await page.getByLabel('Nội dung thông báo',{exact:true}).fill('Thông báo thử nghiệm với dữ liệu giả lập.');
 await page.getByRole('button',{name:'Lưu bản nháp',exact:true}).click();await page.getByRole('heading',{name:title+' · Bản nháp'}).waitFor();
 page.on('dialog',dialog=>dialog.accept());await page.locator('article').filter({has:page.getByRole('heading',{name:title+' · Bản nháp'})}).getByRole('button',{name:'Công bố',exact:true}).click();
 await page.getByRole('heading',{name:title+' · Đã công bố'}).waitFor();
 const call=async(path,token,tenant,method='GET',body)=>{const res=await fetch('http://127.0.0.1:8000/api/v1/'+path,{method,headers:{...(token?{Authorization:'Bearer '+token}:{}),...(tenant?{'X-Tenant-ID':tenant}:{}),'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});const data=await res.json();if(!res.ok)throw new Error(res.status+': '+JSON.stringify(data));return data;};
 const token=(await call('auth/token/',null,null,'POST',{username:'parent_a',password:'DemoOnly!ChangeMe123'})).access;const me=await call('me/',token),tenant=me.memberships.find(m=>m.role==='PARENT').tenant_id;
 const student=(await call('students/',token,tenant))[0];const contacts=await call(`comms/students/${student.id}/contacts/`,token,tenant);
 const teacher=contacts.teachers.find(t=>t.name.includes('GVCN'));assert(teacher);
 const thread=await call('comms/conversations/',token,tenant,'POST',{student_id:student.id,teacher_id:teacher.id,guardian_id:me.id});
 await call(`comms/conversations/${thread.id}/messages/`,token,tenant,'POST',{body:title+' parent message',client_key:crypto.randomUUID()});
 await page.getByRole('button',{name:'Làm mới liên lạc',exact:true}).click();
 await page.getByRole('button',{name:new RegExp(student.full_name+' · .* · [1-9][0-9]* chưa đọc')}).click();
 await page.getByText(title+' parent message',{exact:false}).waitFor();await page.getByLabel('Tin nhắn',{exact:true}).fill(title+' teacher response');await page.getByRole('button',{name:'Gửi tin nhắn',exact:true}).click();await page.getByText(title+' teacher response',{exact:false}).waitFor();
 assert((await call(`comms/conversations/${thread.id}/messages/`,token,tenant)).messages.some(m=>m.body===title+' teacher response'));
 await page.getByRole('button',{name:'Làm mới liên lạc',exact:true}).waitFor();await page.waitForFunction(()=>!Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='Làm mới liên lạc')?.disabled);await page.screenshot({path:'/tmp/edusphere-s5-teacher.png',fullPage:true});
 const ticket=await call('comms/tickets/',token,tenant,'POST',{category:'ACCOUNT',subject:title+' support',details:'Cần hỗ trợ thử nghiệm',student_id:student.id});
 await page.goto('http://127.0.0.1:5177');await page.getByLabel('Password',{exact:true}).fill('DemoOnly!ChangeMe123');await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();
 await page.getByRole('button',{name:ticket.subject+' · Mới tiếp nhận',exact:true}).click();await page.getByLabel('Phản hồi hỗ trợ',{exact:true}).fill('Đã kiểm tra yêu cầu thử nghiệm.');await page.getByRole('button',{name:'Gửi phản hồi',exact:true}).click();
 await page.getByRole('button',{name:ticket.subject+' · Đang xử lý',exact:true}).waitFor();await page.getByRole('button',{name:'Đã giải quyết',exact:true}).click();await page.getByRole('button',{name:ticket.subject+' · Đã giải quyết',exact:true}).waitFor();await page.getByRole('button',{name:'Đã đóng',exact:true}).click();await page.getByRole('button',{name:ticket.subject+' · Đã đóng',exact:true}).waitFor();
 assert.equal(await page.getByRole('button',{name:'Gửi phản hồi',exact:true}).count(),0);assert.equal((await call(`comms/tickets/${ticket.id}/`,token,tenant)).state,'CLOSED');
 await page.screenshot({path:'/tmp/edusphere-s5-support.png',fullPage:true});
 await page.getByRole('button',{name:'Đăng xuất',exact:true}).click();assert.equal(await page.getByText(ticket.subject,{exact:true}).count(),0);
 await page.getByLabel('Username',{exact:true}).fill('admin_a');await page.getByLabel('Password',{exact:true}).fill('DemoOnly!ChangeMe123');await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();await page.getByRole('alert').filter({hasText:'không có quyền'}).waitFor();
 await page.goto('http://127.0.0.1:5173');
 await page.locator('input').first().fill('admin_a');await page.locator('input[type=password]').fill('DemoOnly!ChangeMe123');await page.getByRole('button',{name:/Đăng nhập|Sign in/}).click();await page.getByRole('button',{name:/Liên lạc & hỗ trợ/}).click();await page.getByRole('heading',{name:'Liên lạc & thông báo',exact:true}).waitFor();
 await page.getByRole('button',{name:ticket.subject+' · Đã đóng',exact:true}).waitFor();assert.equal(await page.getByRole('heading',{name:'Trao đổi phụ huynh – giáo viên'}).count(),0);
 await page.screenshot({path:'/tmp/edusphere-s5-admin.png',fullPage:true});assert.deepEqual(errors,[]);console.log('PASS: announcement draft/publish, parent API -> teacher UI messaging, parent API -> Support UI claim/resolve/close, role rejection, Admin queue, logout, no React runtime errors.');
}catch(e){await page.screenshot({path:'/tmp/edusphere-s5-failure.png',fullPage:true}).catch(()=>{});console.error('PAGE',await page.locator('body').innerText().catch(()=>''));throw e;}finally{await browser.close();}
