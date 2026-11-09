import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
export const readJson=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,''));
export const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
export const digest=x=>crypto.createHash('sha256').update(JSON.stringify(x)).digest('hex');
export function run(cmd,args,options={}){
 if(cmd==='ffmpeg')args=['-threads','1','-filter_threads','1','-filter_complex_threads','1',...args];
 const r=spawnSync(cmd,args,{windowsHide:true,maxBuffer:64*1024*1024,timeout:180000,...options});
 if(r.error)throw Object.assign(new Error(r.error.message),{infrastructure:true});
 if(r.status!==0)throw new Error(`${cmd} exited ${r.status}: ${r.stderr?.toString().slice(-2500)} ${r.stdout?.toString().slice(-1500)}`);
 return r;
}
export function projectFiles(root){
 const result=[];const base=fs.realpathSync(root);
 function walk(dir){for(const e of fs.readdirSync(dir,{withFileTypes:true})){
  if(['node_modules','build','.cache','.git'].includes(e.name))continue;
  const p=path.join(dir,e.name);const real=fs.realpathSync(p);
  if(real!==base&&!real.startsWith(base+path.sep))throw new Error('Project contains an external link: '+path.relative(root,p));
  if(e.isDirectory())walk(p);else if(e.isFile())result.push(p);else throw new Error('Unsupported project entry: '+p);
 }}walk(root);return result.sort();
}
export function projectHash(root){return digest(projectFiles(root).map(p=>[path.relative(root,p).replaceAll('\\','/'),sha(p)]));}
export function inspectMedia(file,params){
 const probe=JSON.parse(run('ffprobe',['-v','error','-count_frames','-show_streams','-show_format','-of','json',file],{encoding:'utf8'}).stdout);
 const video=probe.streams.find(s=>s.codec_type==='video'),audio=probe.streams.find(s=>s.codec_type==='audio');
 if(!video)throw new Error('No video stream');
 const spec=params.media,[n,d]=video.r_frame_rate.split('/').map(Number);
 const videoSpec=video.codec_name==='h264'&&video.width===spec.width&&video.height===spec.height&&Math.abs(n/d-spec.fps)<1e-6&&Number(video.nb_read_frames)===spec.frames&&Math.abs(Number(probe.format.duration)-spec.seconds)<=spec.duration_tolerance_seconds&&audio?.codec_name==='aac';
 run('ffmpeg',['-v','error','-xerror','-i',file,'-f','null','-']);
 const pixels=run('ffmpeg',['-v','error','-i',file,'-an','-vf','scale=32:18,format=gray','-fps_mode','passthrough','-f','rawvideo','pipe:1']).stdout;
 const frameSize=576,frames=Math.floor(pixels.length/frameSize);let black=0;const intervals=[];let begin=null;
 for(let k=0;k<frames;k++){let sum=0,sum2=0;for(let j=0;j<frameSize;j++){const x=pixels[k*frameSize+j];sum+=x;sum2+=x*x;}const mean=sum/frameSize,std=Math.sqrt(Math.max(0,sum2/frameSize-mean*mean));const isBlack=mean<=params.measurement.black_luma_max&&std<=params.measurement.black_spatial_std_max;if(isBlack){black++;if(begin===null)begin=k;}else if(begin!==null){intervals.push([begin/spec.fps,k/spec.fps]);begin=null;}}
 if(begin!==null)intervals.push([begin/spec.fps,frames/spec.fps]);
 let audioStats={peak:0,rms:0,samples:0,active_seconds:0,active_quarters:0,clipped_fraction:0};
 if(audio){const pcm=run('ffmpeg',['-v','error','-i',file,'-vn','-f','f32le','pipe:1']).stdout;const rate=Number(audio.sample_rate),channels=audio.channels||1;let sum=0,peak=0,clipped=0;const perSecond=[];
  for(let j=0;j<pcm.length;j+=4){const x=pcm.readFloatLE(j);peak=Math.max(peak,Math.abs(x));sum+=x*x;if(Math.abs(x)>=0.999)clipped++;const second=Math.floor(j/4/rate/channels);perSecond[second]=(perSecond[second]||0)+x*x;}
  const rmsSeconds=perSecond.map(s=>Math.sqrt(s/rate/channels));const active=rmsSeconds.map(v=>v>0.001);const quarters=new Set(active.map((v,i)=>v?Math.floor(i/10):-1).filter(i=>i>=0));
  audioStats={peak,rms:Math.sqrt(sum/(pcm.length/4)),samples:pcm.length/4,active_seconds:active.filter(Boolean).length,active_quarters:quarters.size,clipped_fraction:clipped/(pcm.length/4),rms_per_second:rmsSeconds};
 }
 return {probe,video_spec:videoSpec,full_decode:true,visual_content:frames>0&&black<frames,audible_audio:audioStats.peak>params.measurement.audio_peak_floor,black_frames:black,decoded_frames:frames,black_intervals:intervals,audio:audioStats};
}
export function audioPcm(file){return run('ffmpeg',['-v','error','-i',file,'-vn','-ac','1','-ar','8000','-f','f32le','pipe:1']).stdout;}
export function compareMedia(a,b,params){
 const gray=f=>run('ffmpeg',['-v','error','-i',f,'-an','-vf','fps=1,scale=64:36,format=gray','-f','rawvideo','pipe:1']).stdout;
 const x=gray(a),y=gray(b),frameSize=2304,frames=Math.floor(x.length/frameSize);let matching=0;const errors=[];
 for(let k=0;k<frames;k++){let sum=0;for(let j=0;j<frameSize;j++)sum+=Math.abs(x[k*frameSize+j]-(y[k*frameSize+j]??0));const mae=sum/frameSize;errors.push(mae);if(mae<=params.measurement.frame_mae_max)matching++;}
 const ax=audioPcm(a),ay=audioPcm(b);let energy=0,difference=0;const samples=Math.max(ax.length,ay.length)/4;
 for(let k=0;k<samples;k++){const p=k*4<ax.length?ax.readFloatLE(k*4):0,q=k*4<ay.length?ay.readFloatLE(k*4):0;energy+=p*p;difference+=(p-q)**2;}
 const relativeRmse=Math.sqrt(difference/Math.max(energy,1e-12));
 return {passed:x.length===y.length&&frames>0&&matching/frames>=params.measurement.matching_frame_fraction_min&&relativeRmse<=params.measurement.audio_relative_rmse_max,matching_frame_fraction:matching/Math.max(1,frames),frame_mae:errors,audio_relative_rmse:relativeRmse,scope:'Sampled frame and full-waveform correspondence; not an editorial judgment.'};
}
