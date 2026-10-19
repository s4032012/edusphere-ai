import {test, afterEach} from 'node:test';
import {strict as assert} from 'node:assert';
import fs from 'node:fs';
import ts from 'typescript';
const source=fs.readFileSync(new URL('../src/index.ts',import.meta.url),'utf8');
const {outputText}=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {createApi,ApiError,membershipsFor,ROLES,createRequestScope}=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
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
