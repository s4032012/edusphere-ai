import {DashboardPanel} from '@edusphere/communications-ui/dashboard';
export function MyLearningDashboard({token,tenant,onExpired}:{token:string;tenant:string;onExpired:()=>void}){
 return <DashboardPanel token={token} tenant={tenant} mode="student" baseUrl={process.env.EXPO_PUBLIC_API_URL||'http://127.0.0.1:8000'} onExpired={onExpired}/>;
}
