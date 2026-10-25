import {test,afterEach} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const source=fs.readFileSync(new URL('../src/index.ts',import.meta.url),'utf8');
const {outputText}=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {createCommunicationsApi,ApiError,messageKey,ticketTransitions}=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const original=globalThis.fetch;afterEach(()=>{globalThis.fetch=original;});
function capture(){const calls=[];globalThis.fetch=async(url,init)=>{calls.push({url,...init});return Response.json({});};return calls;}
test('communication routes retain tenant and auth headers without embedding private text in URLs',async()=>{
 const calls=capture(),api=createCommunicationsApi('https://school.test/');
 await api.announcements('token','tenant');await api.contacts('token','tenant','child');await api.conversations('token','tenant');await api.messages('token','tenant','thread');await api.tickets('token','tenant');await api.ticket('token','tenant','ticket');await api.inbox('token','tenant');
 assert.deepEqual(calls.map(c=>c.url.replace('https://school.test/api/v1/comms','')),['/announcements/','/students/child/contacts/','/conversations/','/conversations/thread/messages/','/tickets/','/tickets/ticket/','/notifications/']);
 for(const c of calls){assert.equal(c.method,'GET');assert.equal(c.headers.Authorization,'Bearer token');assert.equal(c.headers['X-Tenant-ID'],'tenant');assert.equal(c.body,undefined);}
});
test('send retry retains provided UUID and read watermark is explicit',async()=>{
 const calls=capture(),api=createCommunicationsApi(''),key=messageKey();assert.match(key,/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/);
 await api.createConversation('t','s','child','teacher','guardian');await api.sendMessage('t','s','thread','private',key);await api.sendMessage('t','s','thread','private',key);await api.readConversation('t','s','thread','last');await api.readConversation('t','s','thread',null);
 assert.deepEqual(JSON.parse(calls[0].body),{student_id:'child',teacher_id:'teacher',guardian_id:'guardian'});
 assert.equal(calls[1].body,calls[2].body);assert.deepEqual(JSON.parse(calls[3].body),{last_message_id:'last'});assert.deepEqual(JSON.parse(calls[4].body),{last_message_id:null});
});
test('notice draft, publish and receipts are separate actions',async()=>{
 const calls=capture(),api=createCommunicationsApi('');const draft={scope:'GRADE',grade_level:8,title:'Meeting',body:'Friday'};
 await api.createAnnouncement('t','s',draft);await api.publishAnnouncement('t','s','notice');await api.readAnnouncement('t','s','notice');await api.markInboxRead('t','s','event');
 assert.deepEqual(JSON.parse(calls[0].body),draft);assert.equal(calls[1].url,'/api/v1/comms/announcements/notice/publish/');assert.equal(calls[3].url,'/api/v1/comms/notifications/event/read/');
 for(const c of calls){assert.equal(c.method,'POST');assert.equal(c.headers['Content-Type'],'application/json');}
});
test('ticket transitions carry observed version and closed state is terminal',async()=>{
 const calls=capture(),api=createCommunicationsApi('');await api.createTicket('t','s',{category:'ACCOUNT',subject:'Help',details:'Description'});await api.replyTicket('t','s','ticket','Response');await api.changeTicketStatus('t','s','ticket','RESOLVED',4);
 assert.deepEqual(JSON.parse(calls[2].body),{state:'RESOLVED',expected_version:4});assert.deepEqual(ticketTransitions.CLOSED,[]);assert.deepEqual(ticketTransitions.RESOLVED,['IN_PROGRESS','CLOSED']);
});
test('expired sessions, stale versions and throttles preserve actionable errors',async()=>{
 for(const status of [401,409,429]){globalThis.fetch=async()=>Response.json({detail:'Refresh or retry'},{status});await assert.rejects(createCommunicationsApi('').inbox('t','s'),e=>e instanceof ApiError&&e.status===status&&e.message.includes('retry'));}
});
