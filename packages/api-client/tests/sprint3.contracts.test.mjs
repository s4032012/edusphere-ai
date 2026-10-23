import {test,afterEach} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const source=fs.readFileSync(new URL('../src/index.ts',import.meta.url),'utf8');
const {outputText}=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {createGradesApi,ApiError}=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const originalFetch=globalThis.fetch;
afterEach(()=>{globalThis.fetch=originalFetch;});
test('grade writes send exact decimal strings and scoped authorization',async()=>{
  const calls=[];globalThis.fetch=async(url,init)=>{calls.push({url,...init});return Response.json({});};
  const api=createGradesApi('https://school.test/');
  await api.createBook('token','tenant',{classroom_id:'class',subject_id:'subject',semester:'1',mode:'SCORE',regular_required:2});
  await api.createAssessment('token','tenant','book','TX',1,'Quiz');
  await api.saveGrades('token','tenant','assessment',[{student_id:'pupil',score:'0.0'}]);
  await api.lock('token','tenant','assessment');await api.publish('token','tenant','assessment');
  for(const call of calls){assert.equal(call.headers.Authorization,'Bearer token');assert.equal(call.headers['X-Tenant-ID'],'tenant');assert.equal(call.headers['Content-Type'],'application/json');}
  assert.equal(calls[2].method,'PUT');assert.deepEqual(JSON.parse(calls[2].body),{entries:[{student_id:'pupil',score:'0.0'}]});
  assert.equal(calls[4].url,'https://school.test/api/v1/assessments/assessment/publish/');
});
test('published student view preserves missing average and revision requests carry a reason',async()=>{
  const calls=[];globalThis.fetch=async(url,init)=>{calls.push({url,...init});return Response.json({books:[{semester_average:null}]});};
  const api=createGradesApi('');const data=await api.student('token','tenant','pupil');
  assert.equal(data.books[0].semester_average,null);assert.equal(calls[0].url,'/api/v1/students/pupil/grades/');
  await api.requestRevision('token','tenant','entry',{score:'7.5',reason:'Correct input error'});
  await api.decideRevision('token','tenant','revision','reject','Needs evidence');
  assert.deepEqual(JSON.parse(calls[1].body),{score:'7.5',reason:'Correct input error'});
  assert.deepEqual(JSON.parse(calls[2].body),{action:'reject',decision_note:'Needs evidence'});
});
test('grade errors preserve field details and expiry status',async()=>{
  globalThis.fetch=async()=>Response.json({score:['Invalid precision']},{status:400});
  await assert.rejects(createGradesApi('').saveGrades('token','tenant','assessment',[]),e=>e instanceof ApiError&&e.status===400&&e.message.includes('Invalid precision'));
  globalThis.fetch=async()=>Response.json({detail:'Expired'},{status:401});
  await assert.rejects(createGradesApi('').books('token','tenant'),e=>e instanceof ApiError&&e.status===401);
});
