import {fileURLToPath,pathToFileURL} from 'node:url';
import {dirname,resolve} from 'node:path';
const root=dirname(fileURLToPath(import.meta.url)),repo=resolve(root,'../..');
const tmp=process.env.DASHBOARD_QA_DEPS||'/tmp/edusphere-s6-ui';
const {createServer}=await import(pathToFileURL(resolve(repo,'apps/teacher-web/node_modules/vite/dist/node/index.js')).href);
const server=await createServer({root,resolve:{alias:[
 {find:'@dashboard',replacement:repo+'/packages/communications-ui/dashboard.tsx'},
 {find:'@edusphere/api-client',replacement:repo+'/packages/api-client/src/index.ts'},
 {find:/^react-native$/,replacement:tmp+'/node_modules/react-native-web/dist/index.js'},
 {find:/^react$/,replacement:tmp+'/node_modules/react/index.js'},
 {find:/^react\/(.*)$/,replacement:tmp+'/node_modules/react/$1'},
 {find:/^react-dom$/,replacement:tmp+'/node_modules/react-dom/index.js'},
 {find:/^react-dom\/(.*)$/,replacement:tmp+'/node_modules/react-dom/$1'},
]},esbuild:{jsx:'automatic'},server:{host:'127.0.0.1',port:5186,strictPort:true,fs:{allow:[repo,tmp]},proxy:{'/api':'http://127.0.0.1:8000'}}});
await server.listen();console.log('Sprint 6 QA component server: http://127.0.0.1:5186');
