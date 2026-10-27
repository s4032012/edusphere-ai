// Dashboard component QA: live local API, then mocked response-race cases.
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
import assert from 'node:assert/strict';
const browser=await chromium.launch({channel:'chrome',headless:true,timeout:20000});
const page=await browser.newPage({viewport:{width:390,height:844}});page.setDefaultTimeout(15000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
const api=async(path,token,tenant,body)=>{const r=await fetch('http://127.0.0.1:8000/api/v1/'+path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{}),...(tenant?{'X-Tenant-ID':tenant}:{})},...(body?{body:JSON.stringify(body)}:{})});assert(r.ok,await r.clone().text());return r.json();};
const auth=async(username)=>{const {access}=await api('auth/token/',null,null,{username,password:'DemoOnly!ChangeMe123'});const me=await api('me/',access);return {token:access,tenant:me.memberships[0].tenant_id};};
const session=async(values)=>page.evaluate(v=>window.qaSession(v),{...values,key:crypto.randomUUID()});
try{
 await page.goto('http://127.0.0.1:5186');await page.waitForFunction(()=>typeof window.qaSession==='function');
 const parent=await auth('parent_a');await session({...parent,mode:'parent'});
 await page.getByRole('button',{name:'Xem tóm tắt theo quy tắc',exact:true}).click();await page.getByText('Tóm tắt dữ liệu · chưa sử dụng AI',{exact:true}).waitFor();
 assert.equal(await page.getByText('Nguồn:',{exact:false}).count(),3);assert.equal(await page.getByRole('alert').count(),0);
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:'/tmp/edusphere-s6-parent.png',fullPage:true});
 const student=await auth('student_a');await session({...student,mode:'student'});await page.getByText('Nhiệm vụ cần làm · tối đa 8 bài',{exact:true}).waitFor();
 assert.equal(await page.getByRole('button',{name:'Xem tóm tắt theo quy tắc'}).count(),0);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:'/tmp/edusphere-s6-student.png',fullPage:true});
 const children=(await api('dashboard/children/',parent.token,parent.tenant)).students;const base=await api(`dashboard/students/${children[0].id}/`,parent.token,parent.tenant);
 const aid='11111111-1111-4111-8111-111111111111',bid='22222222-2222-4222-8222-222222222222';
 const fake=(id,name)=>({...structuredClone(base),student:{...base.student,id,full_name:name,student_code:id===aid?'QA-A':'QA-B'},grades:{...base.grades,items:[{assessment_id:id,subject:'Toán',title:name+' result',semester:'1',kind:'TX',score:'0.0',result:null,note:name+' note',published_at:new Date().toISOString()}]}});
 let slowA=true,previewDelay=0,previewFailure=0,deny=false,zero=false;
 await page.route('**/api/v1/dashboard/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/children/'))return route.fulfill({json:{students:zero?[]:[{id:aid,full_name:'Child A',student_code:'QA-A'},{id:bid,full_name:'Child B',student_code:'QA-B'}]}});
  const id=path.includes(aid)?aid:bid,name=id===aid?'Child A':'Child B';
  if(path.endsWith('/ai-preview/')){
   if(previewDelay&&id===aid)await new Promise(r=>setTimeout(r,previewDelay));
   if(previewFailure)return route.fulfill({status:previewFailure,json:{detail:'Preview unavailable'}});
   return route.fulfill({json:{student_id:id,as_of:new Date().toISOString(),enabled:false,mode:'RULE_BASED_PREVIEW',model_called:false,exported_to_provider:false,human_review_required:true,enrollment_status:'CURRENT',sentences:[{kind:'grades',text:name+' preview',source:'published_assessments_only'}],limitations:[]}});
  }
  if(slowA&&id===aid)await new Promise(r=>setTimeout(r,600));
  return route.fulfill(deny?{status:404,json:{detail:'Link revoked'}}:{json:fake(id,name)});
 });
 await session({...parent,mode:'parent'});await page.getByRole('button',{name:'Child B QA-B',exact:false}).click();await page.getByText('Child B note',{exact:true}).waitFor();await page.waitForTimeout(700);assert.equal(await page.getByText('Child A note',{exact:true}).count(),0);
 // An old preview cannot replace the newly selected child's result, or block its preview.
 slowA=false;previewDelay=650;await page.getByRole('button',{name:'Child A QA-A',exact:false}).click();await page.getByText('Child A note',{exact:true}).waitFor();await page.getByRole('button',{name:'Xem tóm tắt theo quy tắc',exact:true}).click();
 await page.getByRole('button',{name:'Child B QA-B',exact:false}).click();await page.getByText('Child B note',{exact:true}).waitFor();await page.getByRole('button',{name:'Xem tóm tắt theo quy tắc',exact:true}).click();await page.getByText('Child B preview',{exact:true}).waitFor();await page.waitForTimeout(750);assert.equal(await page.getByText('Child A preview',{exact:true}).count(),0);
 previewFailure=500;await page.getByRole('button',{name:'Xem tóm tắt theo quy tắc',exact:true}).click();await page.getByRole('alert').filter({hasText:'API error (500)'}).waitFor();assert.equal(await page.getByText('Child B note',{exact:true}).count(),1);
 deny=true;await page.getByRole('button',{name:'Làm mới tổng quan',exact:true}).click();await page.getByRole('alert').filter({hasText:'Link revoked'}).waitFor();assert.equal(await page.getByText('Child B note',{exact:true}).count(),0);assert.equal(await page.getByText('Child B preview',{exact:true}).count(),0);
 deny=false;previewFailure=401;await session({...parent,mode:'parent'});await page.getByText('Child A note',{exact:true}).waitFor();await page.getByRole('button',{name:'Xem tóm tắt theo quy tắc',exact:true}).click();await page.getByText('Expired session',{exact:true}).waitFor();
 zero=true;await session({...parent,mode:'parent'});await page.getByText('Chưa có hồ sơ học sinh được xác minh',{exact:false}).waitFor();
 assert.deepEqual(errors,[]);console.log('PASS: live Parent/Student dashboard rendering + local preview; no horizontal overflow at 390px; child-response race; preview race; preview 500 preserves snapshot; revoked snapshot clears data; 401 expires session; empty children state; no React runtime errors.');
}catch(e){console.error(await page.locator('body').innerText());await page.screenshot({path:'/tmp/edusphere-s6-failure.png',fullPage:true});throw e;}finally{await browser.close();}
