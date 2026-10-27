import {test,afterEach} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const source=fs.readFileSync(new URL('../src/index.ts',import.meta.url),'utf8');
const {outputText}=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {createDashboardApi,ApiError}=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const original=globalThis.fetch;afterEach(()=>{globalThis.fetch=original;});
test('dashboard calls are GET-only, carry scoped auth and encode identifiers',async()=>{
 const calls=[];globalThis.fetch=async(url,init)=>{calls.push({url,...init});return Response.json({});};
 const api=createDashboardApi('https://school.test/');await api.children('t','a');await api.student('t','a','child/one');await api.aiPreview('t','a','child/one');
 assert.deepEqual(calls.map(c=>c.url),['https://school.test/api/v1/dashboard/children/','https://school.test/api/v1/dashboard/students/child%2Fone/','https://school.test/api/v1/dashboard/students/child%2Fone/ai-preview/']);
 for(const c of calls){assert.equal(c.method,'GET');assert.equal(c.headers.Authorization,'Bearer t');assert.equal(c.headers['X-Tenant-ID'],'a');assert.equal(c.body,undefined);}
});
test('snapshot preserves zero scores, null class, empty feeds and separate totals',async()=>{
 const data={student:{classroom:null},enrollment_status:'NONE',grades:{items:[{score:'0.0',result:null}],limited_to:8},homework:{summary:{total:20,overdue:9},items:[],limited_to:8}};
 globalThis.fetch=async()=>Response.json(data);assert.deepEqual(await createDashboardApi('').student('t','s','id'),data);
});
test('local preview keeps explicit no-model/no-export flags and evidence labels',async()=>{
 const preview={enabled:false,mode:'RULE_BASED_PREVIEW',model_called:false,exported_to_provider:false,human_review_required:true,sentences:[{source:'submitted_or_locked_attendance',text:'Recorded data'}]};
 globalThis.fetch=async()=>Response.json(preview);assert.deepEqual(await createDashboardApi('').aiPreview('t','s','id'),preview);
});
test('authorization, revocation and rate limits retain status for the UI',async()=>{
 for(const status of [401,403,404,429]){globalThis.fetch=async()=>Response.json({detail:'Dashboard unavailable'},{status});await assert.rejects(createDashboardApi('').student('t','s','id'),e=>e instanceof ApiError&&e.status===status);}
});
