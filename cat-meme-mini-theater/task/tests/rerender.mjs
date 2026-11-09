import fs from 'node:fs';
import path from 'node:path';
import {projectFiles,projectHash,readJson,run,sha} from './media-utils.mjs';
export function reproduce(project,destination,{runtimeModules}={}){
 fs.mkdirSync(destination,{recursive:true});
 const work=path.join(destination,'project');
 if(fs.existsSync(work))throw new Error('Rerender destination must be fresh');
 const before=projectHash(project);fs.mkdirSync(work,{recursive:true});
 for(const src of projectFiles(project)){const dst=path.join(work,path.relative(project,src));fs.mkdirSync(path.dirname(dst),{recursive:true});fs.copyFileSync(src,dst);}
 const pkg=readJson(path.join(work,'package.json'));
 if(typeof pkg.scripts?.render!=='string'||!pkg.scripts.render.trim())return {version:2,project_sha256:before,status:'failed',reason:'No render script'};
 const candidates=[process.env.NPM_CLI,path.join(path.dirname(process.execPath),'node_modules/npm/bin/npm-cli.js'),path.resolve(path.dirname(process.execPath),'../lib/node_modules/npm/bin/npm-cli.js')].filter(Boolean);
 const npm=candidates.find(fs.existsSync);if(!npm)throw Object.assign(new Error('npm CLI not available'),{infrastructure:true});
 const logs=[];
 const allow=new Set(['PATH','SYSTEMROOT','WINDIR','TEMP','TMP','HOME','USERPROFILE','CHROME_PATH','NPM_CONFIG_CACHE','COMSPEC','PATHEXT','APPDATA','LOCALAPPDATA']);
 const env=Object.fromEntries(Object.entries(process.env).filter(([k])=>allow.has(k.toUpperCase())));env.npm_config_offline='true';
 try{
  if(runtimeModules){const runtimePackage=path.resolve(runtimeModules,'../package.json');const installed=readJson(runtimePackage);for(const [name,version] of Object.entries({...pkg.dependencies,...pkg.devDependencies})){if(installed.dependencies?.[name]!==version&&installed.devDependencies?.[name]!==version)throw Object.assign(new Error(`Runtime does not provide declared dependency ${name}@${version}`),{infrastructure:true});}fs.symlinkSync(path.resolve(runtimeModules),path.join(work,'node_modules'),'junction');}
  else{const args=[npm,fs.existsSync(path.join(work,'package-lock.json'))||fs.existsSync(path.join(work,'npm-shrinkwrap.json'))?'ci':'install','--offline','--ignore-scripts','--no-audit','--no-fund'];const r=run(process.execPath,args,{cwd:work,env,encoding:'utf8',timeout:120000});logs.push({command:args,stdout:r.stdout,stderr:r.stderr});}
  if(pkg.scripts?.['prepare-assets']){const args=[npm,'run','prepare-assets'];const r=run(process.execPath,args,{cwd:work,env,encoding:'utf8',timeout:180000});logs.push({command:args,stdout:r.stdout,stderr:r.stderr});}
  const output=path.join(destination,'rerender.mp4'),args=[npm,'run','render','--','--output',output];
  const r=run(process.execPath,args,{cwd:work,env,encoding:'utf8',timeout:600000});logs.push({command:args,stdout:r.stdout,stderr:r.stderr});
  if(!fs.existsSync(output)||!fs.statSync(output).size)throw new Error('Render command did not produce requested output');
  const proof={version:2,project_sha256:before,status:'passed',output,output_sha256:sha(output),runtime_modules:runtimeModules||null,logs};fs.writeFileSync(path.join(destination,'proof.json'),JSON.stringify(proof,null,2));return proof;
 }catch(error){if(error.infrastructure||/ENOTCACHED|cache mode is 'only-if-cached'/i.test(error.message))throw Object.assign(error,{infrastructure:true});const proof={version:2,project_sha256:before,status:'failed',reason:error.message,logs};fs.writeFileSync(path.join(destination,'proof.json'),JSON.stringify(proof,null,2));return proof;}
}
if(process.argv[1]&&path.resolve(process.argv[1])===path.resolve(import.meta.filename)){
 try{const result=reproduce(path.resolve(process.argv[2]),path.resolve(process.argv[3]),{runtimeModules:process.argv[4]});console.log(JSON.stringify({status:result.status,proof:path.resolve(process.argv[3],'proof.json'),reason:result.reason}));process.exitCode=result.status==='passed'?0:1;}catch(e){console.error(e.message);process.exitCode=2;}
}
