import path from 'node:path';
import {spawnSync} from 'node:child_process';
const result=spawnSync('python3',[path.join(import.meta.dirname,'judge.py'),...process.argv.slice(2)],{stdio:'inherit',env:process.env});
if(result.error){console.error(result.error.message);process.exitCode=2;}else process.exitCode=result.status??2;
