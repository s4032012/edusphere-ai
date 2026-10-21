import {test, afterEach} from 'node:test';
import {strict as assert} from 'node:assert';
import fs from 'node:fs';
import ts from 'typescript';
const source=fs.readFileSync(new URL('../src/index.ts',import.meta.url),'utf8');
const {outputText}=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {createApi,createAttendanceApi,ApiError,membershipsFor,ROLES,createRequestScope}=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const originalFetch=globalThis.fetch;
afterEach(()=>{globalThis.fetch=originalFetch;});
test('login sends credentials in JSON and trims trailing slash',async()=>{
  globalThis.fetch=async(url,init)=>{
    assert.equal(url,'https://school.test/api/v1/auth/token/');
    assert.equal(init.method,'POST');assert.deepEqual(JSON.parse(init.body),{username:'user',password:'pass'});
    return Response.json({access:'access',refresh:'refresh'});
  };
  assert.equal((await createApi('https://school.test/').login('user','pass')).access,'access');
});
test('scoped reads send tenant and authorization; me has no tenant',async()=>{
  const calls=[];globalThis.fetch=async(url,init)=>{calls.push({url,...init});return Response.json([]);};
  const api=createApi('https://school.test');
  await api.students('secret','school-a');await api.classrooms('secret','school-b');await api.me('secret');
  assert.equal(calls[0].headers['X-Tenant-ID'],'school-a');
  assert.equal(calls[1].headers['X-Tenant-ID'],'school-b');
  assert.ok(!('X-Tenant-ID' in calls[2].headers));
  for(const call of calls)assert.equal(call.headers.Authorization,'Bearer secret');
});
test('401 remains typed so apps can clear sessions',async()=>{
  globalThis.fetch=async()=>Response.json({detail:'Expired'},{status:401});
  await assert.rejects(createApi('').me('expired'),e=>e instanceof ApiError&&e.status===401&&e.message==='Expired');
});
test('non-JSON errors do not leak server HTML',async()=>{
  globalThis.fetch=async()=>new Response('<html>internal traceback</html>',{status:502});
  await assert.rejects(createApi('').me('token'),e=>e.message==='API error (502)');
});
test('network errors propagate for retry UI',async()=>{
  globalThis.fetch=async()=>{throw new TypeError('Network unavailable');};
  await assert.rejects(createApi('').me('token'),/Network unavailable/);
});
test('role mismatch is rejected and multi-role users retain only allowed memberships',()=>{
  const user={memberships:[{role:'PARENT',tenant_id:'a'},{role:'SUBJECT_TEACHER',tenant_id:'b'}]};
  assert.deepEqual(membershipsFor(user,ROLES.student),[]);
  assert.deepEqual(membershipsFor(user,ROLES.teacher),[user.memberships[1]]);
});
test('school change or logout invalidates in-flight responses',()=>{
  const scope=createRequestScope();const old=scope.capture();assert.equal(old(),true);
  scope.invalidate();assert.equal(old(),false);assert.equal(scope.capture()(),true);
});
test('administration writes preserve method, payload, token and tenant',async()=>{
  const calls=[];globalThis.fetch=async(url,init)=>{calls.push({url,...init});return Response.json({id:'created'});};
  const api=createApi('https://school.test/');
  await api.adminPost('/api/v1/subjects/','token-a','tenant-a',{code:'MATH',name:'Toán'});
  await api.adminPatch('/api/v1/students/id/edit/','token-b','tenant-b',{full_name:'Updated'});
  assert.equal(calls[0].method,'POST');assert.equal(calls[1].method,'PATCH');
  assert.equal(calls[0].headers['X-Tenant-ID'],'tenant-a');assert.equal(calls[1].headers['X-Tenant-ID'],'tenant-b');
  assert.equal(calls[1].headers.Authorization,'Bearer token-b');
  assert.deepEqual(JSON.parse(calls[0].body),{code:'MATH',name:'Toán'});
  assert.deepEqual(JSON.parse(calls[1].body),{full_name:'Updated'});
});
test('validation errors show field details instead of generic HTTP code',async()=>{
  globalThis.fetch=async()=>Response.json({code:['Mã đã tồn tại.']},{status:400});
  await assert.rejects(createApi('').adminPost('/api/v1/subjects/','token','school',{}),e=>e.status===400&&e.message==='code: Mã đã tồn tại.');
});


test('attendance and leave workflow uses scoped JSON writes and encoded filters',async()=>{
  const calls=[];
  globalThis.fetch=async(url,init)=>{calls.push({url,...init});return Response.json({id:'session',state:'DRAFT'});};
  const api=createAttendanceApi('https://school.test/');
  await api.start('token','tenant','class','2026-10-21');
  await api.save('token','tenant','session',[{student_id:'pupil',mark:'ABSENT'}]);
  await api.submit('token','tenant','session');
  await api.decide('token','tenant','leave','approve','Reviewed');
  await api.withdraw('token','tenant','leave');
  await api.leaves('token','tenant','a&b');
  for(const call of calls){assert.equal(call.headers.Authorization,'Bearer token');assert.equal(call.headers['X-Tenant-ID'],'tenant');}
  assert.equal(calls[1].method,'PUT');
  assert.deepEqual(JSON.parse(calls[1].body),{records:[{student_id:'pupil',mark:'ABSENT'}]});
  assert.equal(calls[2].url,'https://school.test/api/v1/attendance/sessions/session/submit/');
  assert.deepEqual(JSON.parse(calls[3].body),{action:'approve',decision_note:'Reviewed'});
  assert.equal(calls[4].method,'POST');
  assert.equal(calls[5].url,'https://school.test/api/v1/leave-requests/?student_id=a%26b');
});

test('attendance errors preserve typed 401 and validation details',async()=>{
  const api=createAttendanceApi('https://school.test');
  globalThis.fetch=async()=>Response.json({detail:'Expired'},{status:401});
  await assert.rejects(api.detail('token','tenant','session'),e=>e instanceof ApiError&&e.status===401);
  globalThis.fetch=async()=>Response.json({records:['Incomplete roster']},{status:400});
  await assert.rejects(api.submit('token','tenant','session'),e=>e instanceof ApiError&&e.message.includes('Incomplete roster'));
});
