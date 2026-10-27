import {useEffect,useRef,useState} from 'react';
import {ApiError,createDashboardApi,type DashboardChild,type StudentDashboardSnapshot,type AiPreview} from '@edusphere/api-client';
export type DashboardProps={baseUrl:string;token:string;tenant:string;mode:'parent'|'student';onExpired:()=>void};
export function useDashboard(p:DashboardProps){
 const api=createDashboardApi(p.baseUrl),live=useRef(true),sequence=useRef(0),selected=useRef(''),onExpired=useRef(p.onExpired);onExpired.current=p.onExpired;
 const [children,setChildren]=useState<DashboardChild[]>([]),[studentId,setStudentId]=useState('');
 const [data,setData]=useState<StudentDashboardSnapshot|null>(null),[preview,setPreview]=useState<AiPreview|null>(null);
 const [loading,setLoading]=useState(true),[previewLoading,setPreviewLoading]=useState(false),[error,setError]=useState(''),[previewError,setPreviewError]=useState('');
 const previewPending=useRef<number|null>(null);
 function current(n:number){return live.current&&sequence.current===n;}
 function failure(e:unknown,n:number,previewOnly=false){
  if(!current(n))return;
  const message=e instanceof Error?e.message:'Không thể tải dữ liệu. Vui lòng thử lại.';
  if(e instanceof ApiError&&[401,403,404].includes(e.status)){
   setData(null);setPreview(null);setChildren([]);setStudentId('');selected.current='';setError(message);
   if(e.status===401)onExpired.current();
  }else if(previewOnly)setPreviewError(message);else setError(message);
 }
 async function snapshot(id:string,n:number){
  const value=await api.student(p.token,p.tenant,id);if(current(n))setData(value);
 }
 async function select(id:string){
  if(!children.some(x=>x.id===id))return;
  const n=++sequence.current;selected.current=id;setStudentId(id);setData(null);setPreview(null);setError('');setPreviewError('');setLoading(true);setPreviewLoading(false);
  try{await snapshot(id,n);}catch(e){failure(e,n);}finally{if(current(n))setLoading(false);}
 }
 async function refresh(){
  const n=++sequence.current;setLoading(true);setError('');setPreviewError('');setPreview(null);setPreviewLoading(false);
  try{
   const result=await api.children(p.token,p.tenant);if(!current(n))return;
   setChildren(result.students);const id=result.students.some(x=>x.id===selected.current)?selected.current:result.students[0]?.id||'';
   if(id!==selected.current)setData(null);selected.current=id;setStudentId(id);
   if(id)await snapshot(id,n);else setData(null);
  }catch(e){failure(e,n);}finally{if(current(n))setLoading(false);}
 }
 async function showPreview(){
  const n=sequence.current,id=selected.current;if(!data||loading||previewPending.current===n)return;previewPending.current=n;setPreviewLoading(true);setPreviewError('');setPreview(null);
  try{const value=await api.aiPreview(p.token,p.tenant,id);if(current(n))setPreview(value);}
  catch(e){failure(e,n,true);}finally{if(previewPending.current===n)previewPending.current=null;if(current(n))setPreviewLoading(false);}
 }
 useEffect(()=>{live.current=true;void refresh();return()=>{live.current=false;sequence.current++;};},[]);
 return {children,studentId,data,preview,loading,previewLoading,error,previewError,refresh,select,showPreview};
}
