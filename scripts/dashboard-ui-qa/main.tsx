import React,{useState} from 'react';
import {createRoot} from 'react-dom/client';
import {DashboardPanel} from '@dashboard';
function App(){const [session,setSession]=useState<any>(null),[expired,setExpired]=useState(false);
 (window as any).qaSession=(s:any)=>{setExpired(false);setSession(s);};
 return <div style={{maxWidth:480,margin:'0 auto',padding:12}}>{session?<DashboardPanel key={session.key} {...session} baseUrl="" onExpired={()=>{setSession(null);setExpired(true);}}/>:<p>{expired?'Expired session':'QA session not set'}</p>}</div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
