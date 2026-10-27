import {DashboardPanel} from '@edusphere/communications-ui/dashboard';
export function LearningDashboard({token,tenant,onExpired}:{token:string;tenant:string;onExpired:()=>void}){
 return <DashboardPanel token={token} tenant={tenant} mode="parent" baseUrl={process.env.EXPO_PUBLIC_API_URL||'http://127.0.0.1:8000'} onExpired={onExpired}/>;
}
