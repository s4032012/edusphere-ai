import {test,afterEach} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const source=fs.readFileSync(new URL('../src/index.ts',import.meta.url),'utf8');
const {outputText}=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {createHomeworkApi,ApiError}=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const originalFetch=globalThis.fetch;
afterEach(()=>{globalThis.fetch=originalFetch;});
test('homework creation, edits and transitions preserve scoped auth and timezone',async()=>{
  const calls=[];globalThis.fetch=async(url,init)=>{calls.push({url,...init});return Response.json({});};
  const api=createHomeworkApi('https://school.test/');
  const data={classroom_id:'class',subject_id:'math',title:'Homework',instructions:'Work',due_at:'2030-01-01T09:00:00+07:00',allow_late:false};
  await api.create('token','tenant',data);await api.edit('token','tenant','task',{allow_late:true});
  await api.publish('token','tenant','task');await api.close('token','tenant','task');
  assert.deepEqual(JSON.parse(calls[0].body),data);assert.equal(calls[1].method,'PATCH');
  assert.equal(calls[3].url,'https://school.test/api/v1/homework/task/close/');
  for(const c of calls){assert.equal(c.headers.Authorization,'Bearer token');assert.equal(c.headers['X-Tenant-ID'],'tenant');}
});
test('first save, resubmission and feedback send optimistic versions and score zero',async()=>{
  const calls=[];globalThis.fetch=async(url,init)=>{calls.push({url,...init});return Response.json({});};
  const api=createHomeworkApi('');
  await api.submit('t','s','task','','save');await api.submit('t','s','task','answer','submit',2);
  await api.returnWork('t','s','submission','Feedback',3,'0');
  assert.deepEqual(JSON.parse(calls[0].body),{content_text:'',action:'save',expected_version:0});
  assert.equal(JSON.parse(calls[1].body).expected_version,2);
  assert.deepEqual(JSON.parse(calls[2].body),{feedback:'Feedback',expected_version:3,score:'0'});
});
test('homework views use distinct scoped routes and preserve parent redaction',async()=>{
  const calls=[];globalThis.fetch=async(url,init)=>{calls.push({url,...init});return Response.json({submission:{content_text:null}});};
  const api=createHomeworkApi('');await api.list('t','s');await api.detail('t','s','task');
  await api.roster('t','s','task');await api.mine('t','s','task');const result=await api.student('t','s','child');
  assert.deepEqual(calls.map(c=>c.url),['/api/v1/homework/','/api/v1/homework/task/','/api/v1/homework/task/roster/','/api/v1/homework/task/my-submission/','/api/v1/homework/students/child/']);
  assert.equal(result.submission.content_text,null);
});
test('homework stale versions and expired tokens retain actionable status',async()=>{
  globalThis.fetch=async()=>Response.json({detail:'Reload latest version',version:2},{status:409});
  await assert.rejects(createHomeworkApi('').submit('t','s','task','answer','submit',1),e=>e instanceof ApiError&&e.status===409&&e.message.includes('Reload'));
  globalThis.fetch=async()=>Response.json({detail:'Expired'},{status:401});
  await assert.rejects(createHomeworkApi('').list('t','s'),e=>e instanceof ApiError&&e.status===401);
});
