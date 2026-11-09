import {spawnSync} from 'node:child_process';
import path from 'node:path';
const [workspace='/workspace',output='/logs/verifier',...extra]=process.argv.slice(2);
const args=[path.join(import.meta.dirname,'verify.py'),workspace,'--output',output];
for(let i=0;i<extra.length;i++){
 if(extra[i]==='--execute-project')continue;
 if(extra[i]==='--refresh'){if(!extra.includes('--judge-mode')&&!extra.includes('--mode'))args.push('--mode','fresh');continue;}
 args.push(extra[i]==='--judge-mode'?'--mode':extra[i]);
}
const result=spawnSync('python3',['-B',...args],{stdio:'inherit'});
if(result.error){console.error(result.error.message);process.exitCode=2;}
else process.exitCode=result.status??2;
