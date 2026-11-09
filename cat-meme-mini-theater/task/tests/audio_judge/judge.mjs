import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';

const here=import.meta.dirname;
const args=process.argv.slice(2);
const get=(name,fallback)=>{const i=args.indexOf(name);return i<0?fallback:args[i+1];};
const mode=get('--mode'),artifact=path.resolve(get('--artifact','')),output=path.resolve(get('--output',''));
const cache=path.resolve(get('--cache-dir',path.join(here,'cache')));
const run=(command,values)=>{const result=spawnSync(command,values,{stdio:'inherit',env:process.env});if(result.error)throw result.error;if(result.status!==0)throw new Error(command+' failed with exit '+result.status);};
try{
 if(!['fresh','replay'].includes(mode)||!get('--artifact')||!get('--output'))throw new Error('Use --mode fresh|replay --artifact OUTPUT --output VERIFIER --cache-dir CACHE [--refresh]');
 const base=fs.realpathSync(artifact);
 for(const target of [output,cache]){let ancestor=target;while(!fs.existsSync(ancestor))ancestor=path.dirname(ancestor);const resolved=fs.realpathSync(ancestor);if(target===artifact||target.startsWith(artifact+path.sep)||resolved===base||resolved.startsWith(base+path.sep))throw new Error('Verifier output/cache must be outside the candidate artifact');}
 fs.mkdirSync(output,{recursive:true});
 let task=get('--task');
 if(!task){let current=here;while(true){if(fs.existsSync(path.join(current,'instruction.md'))&&fs.existsSync(path.join(current,'environment/workspace/materials/screenplay.txt'))){task=current;break;}const parent=path.dirname(current);if(parent===current)break;current=parent;}}
 const instruction=get('--instruction',task&&path.join(task,'instruction.md'));
 const screenplay=get('--screenplay',task&&path.join(task,'environment/workspace/materials/screenplay.txt'));
 if(!instruction||!screenplay)throw new Error('Cannot locate task sources; pass --task or --instruction and --screenplay');
 let evidence=get('--evidence');
 if(!evidence){const settings=JSON.parse(fs.readFileSync(path.join(here,'settings.json'),'utf8'));evidence=path.join(output,'audio-evidence','candidates.json');run('python3',[path.resolve(here,settings.audio_extractor),'--video',path.join(artifact,'final.mp4'),'--references',get('--references',path.join(here,'../audio/references')),'--output',evidence]);}
 const values=[path.join(here,'judge.py'),'--mode',mode,'--artifact',artifact,'--output',output,'--cache-dir',cache,'--evidence',path.resolve(evidence),'--instruction',path.resolve(instruction),'--screenplay',path.resolve(screenplay)];
 if(args.includes('--refresh'))values.push('--refresh');
 if(get('--frames-json'))values.push('--frames-json',path.resolve(get('--frames-json')));
 run('python3',values);
}catch(error){
 const resultFile=path.join(output,'llm_judge_result.json');
 if(fs.existsSync(output)&&!output.startsWith(artifact+path.sep)&&output!==artifact&&!fs.existsSync(resultFile))fs.writeFileSync(resultFile,JSON.stringify({status:'judge_error',mode,error:error.message,role_audio:null,effects:null},null,2)+'\n');
 console.error(error.message);process.exitCode=2;
}
