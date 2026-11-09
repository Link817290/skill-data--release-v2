import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
const root=path.resolve(import.meta.dirname,'..');
const source=path.join(root,'public/source');
const assets=path.join(root,'public/assets');
fs.mkdirSync(assets,{recursive:true});
function run(args, options={}) {
  const r=spawnSync('ffmpeg',['-hide_banner','-y',...args],{maxBuffer:64*1024*1024,...options});
  if(r.status!==0) throw new Error(r.stderr?.toString()||'ffmpeg failed');
  return r;
}
const specs=[
  {id:'typing',file:'060-typing.mp4',key:'0x329f39',similarity:0.10,blend:0.045},
  {id:'boss',file:'110-talking.mp4',key:'0x20f000',similarity:0.30,blend:0.08},
  {id:'confused',file:'013-confused.mp4',key:'0x00ef39',similarity:0.27,blend:0.08},
  {id:'shocked',file:'127-shocked.mp4',key:'0x29ee00',similarity:0.30,blend:0.08},
  {id:'laughing',file:'035-laughing.mp4',key:'0x2eee00',similarity:0.30,blend:0.08},
  {id:'sad',file:'2376-sad.mp4',key:'0x36dd00',similarity:0.28,blend:0.08},
];
const manifest={};
for(const spec of specs){
  const input=path.join(source,'cats',spec.file);
  const key=`crop=iw-4:ih-4:2:2,scale=w='min(960,iw)':h=-2,fps=30,format=rgba,colorkey=${spec.key}:${spec.similarity}:${spec.blend},despill=type=green:mix=0.5:expand=0`;
  // Find the union of visible bounds over the entire short candidate clip.
  const scan=run(['-i',input,'-vf',`${key},alphaextract,cropdetect=limit=24:round=2:reset=0`,'-an','-f','null','-']);
  const crops=[...scan.stderr.toString().matchAll(/crop=(\d+):(\d+):(\d+):(\d+)/g)];
  const last=crops.at(-1);
  if(!last) throw new Error(`No alpha bounds for ${spec.id}`);
  const [w,h,x,y]=last.slice(1).map(Number);
  const folder=path.join(assets,spec.id); fs.mkdirSync(folder,{recursive:true});
  run(['-loglevel','error','-i',input,'-vf',`${key},crop=${w}:${h}:${x}:${y}`,'-an','-start_number','0',path.join(folder,'%04d.png')]);
  const frames=fs.readdirSync(folder).filter(f=>f.endsWith('.png')).length;
  manifest[spec.id]={frames,width:w,height:h,source:spec.file,key:spec.key,similarity:spec.similarity,blend:spec.blend,crop:{x,y,w,h}};
  console.log(`${spec.id}: ${frames} frames, ${w}x${h}`);
}
fs.writeFileSync(path.join(root,'src/assets.json'),JSON.stringify(manifest,null,2));
// Original synthesized music / effects. No network services or third-party music.
const sr=48000,duration=40,samples=new Float32Array(sr*duration);
function tone(start,seconds,freq,amp=0.1,kind='pluck'){
  const startSample=Math.round(start*sr), len=Math.round(seconds*sr);
  for(let i=0;i<len && startSample+i<samples.length;i++){
    const t=i/sr; const attack=Math.min(1,t/0.008);
    const env=kind==='pluck'?Math.exp(-t*9):Math.min(1,(seconds-t)/0.06);
    const f=kind==='drop'?freq*Math.exp(-t*7):freq;
    samples[startSample+i]+=amp*attack*env*(Math.sin(2*Math.PI*f*t)+0.2*Math.sin(4*Math.PI*f*t));
  }
}
const melody=[659.25,783.99,987.77,783.99,587.33,739.99,880,739.99];
for(let beat=0;beat<80;beat++){
  const t=beat*0.5;
  if((t>=18.8&&t<22)||(t>=31.8&&t<37.1))continue;
  tone(t,0.24,melody[beat%8],0.045);
  if(beat%2===0)tone(t,0.35,[164.81,146.83,130.81,146.83][Math.floor(beat/8)%4],0.035);
}
for(const start of [5,14,37.2]){tone(start,.32,987.77,.16);tone(start+.14,.45,1318.51,.11);}
tone(19,.6,100,.4,'drop'); tone(38,.6,80,.32,'drop');
for(let i=0;i<20;i++)tone(27+i*.23,.045,1600+(i%3)*450,.035);
for(let i=0;i<6;i++)tone(32+i*.65,.9,[493.88,440,392,369.99,329.63,246.94][i],.08);
let seed=29;function noise(){seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296*2-1;}
for(const [a,b] of [[0,3.8],[27,31.8]])for(let t=a;t<b;t+=.11){const p=Math.round(t*sr);for(let j=0;j<750;j++)samples[p+j]+=noise()*.065*Math.exp(-j/130);}
// Small original meme-audio reactions, normalized individually before mixing.
for(const cue of [{id:'boss',start:6.0,trim:.4,length:2.4,gain:.19},{id:'confused',start:10.5,trim:0,length:1.7,gain:.24},{id:'boss',start:14.7,trim:3,length:2.6,gain:.19},{id:'shocked',start:19.35,trim:0,length:1.9,gain:.2},{id:'laughing',start:22.5,trim:.3,length:3.4,gain:.25}]){
  const spec=specs.find(s=>s.id===cue.id);
  const raw=run(['-loglevel','error','-ss',String(cue.trim),'-t',String(cue.length),'-i',path.join(source,'cats',spec.file),'-vn','-ac','1','-ar',String(sr),'-f','f32le','pipe:1']).stdout;
  let peak=.001;for(let k=0;k<raw.length;k+=4)peak=Math.max(peak,Math.abs(raw.readFloatLE(k)));
  const offset=Math.round(cue.start*sr),n=raw.length/4;
  for(let k=0;k<n&&offset+k<samples.length;k++){const fade=Math.min(1,k/1000,(n-k)/2000);samples[offset+k]+=raw.readFloatLE(k*4)/peak*cue.gain*fade;}
}
const pcm=Buffer.alloc(samples.length*2);let peak=0;for(const v of samples)peak=Math.max(peak,Math.abs(v));
for(let i=0;i<samples.length;i++)pcm.writeInt16LE(Math.round(samples[i]/Math.max(1,peak/0.85)*32767),i*2);
run(['-loglevel','error','-f','s16le','-ar',String(sr),'-ac','1','-i','pipe:0','-af','loudnorm=I=-16:TP=-1.5:LRA=9','-ar',String(sr),path.join(assets,'soundtrack.wav')],{input:pcm});
console.log('Soundtrack: 40 seconds, generated score + selected original cat reactions.');
