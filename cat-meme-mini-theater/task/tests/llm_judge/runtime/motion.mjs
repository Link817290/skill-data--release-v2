import fs from 'node:fs';
import path from 'node:path';
import {run,sha} from '../../media-utils.mjs';

// Select high-change regions from the actual film, without relying on candidate plan timings.
export function motionEvidence(video,dest,sourceFps,settings,firstId){
 const cfg=settings.extraction.motion,pixels=run('ffmpeg',['-v','error','-i',video,'-an','-vf','scale=32:18,format=gray','-fps_mode','passthrough','-f','rawvideo','pipe:1']).stdout;
 const size=576,total=Math.floor(pixels.length/size),changes=[];
 for(let frame=1;frame<total;frame++){let sum=0;for(let p=0;p<size;p++)sum+=Math.abs(pixels[frame*size+p]-pixels[(frame-1)*size+p]);changes.push({frame,delta:sum/size});}
 const peaks=[];for(const x of changes.sort((a,b)=>b.delta-a.delta||a.frame-b.frame)){
  if(x.delta<cfg.minimum_change)break;
  if(peaks.every(p=>Math.abs(p.frame-x.frame)/sourceFps>=cfg.minimum_spacing_seconds))peaks.push(x);
  if(peaks.length===cfg.maximum_windows)break;
 }
 peaks.sort((a,b)=>a.frame-b.frame);const frames=[],sheets=[];const step=Math.max(1,Math.round(sourceFps/cfg.fps));
 for(const [index,peak]of peaks.entries()){
  const start=Math.max(0,Math.min(peak.frame-Math.round(sourceFps*cfg.pre_roll_seconds),total-step*cfg.frames_per_window));
  const prefix=`motion-${index}`,pattern=path.join(dest,prefix+'-%02d.jpg');
  run('ffmpeg',['-v','error','-y','-ss',String(start/sourceFps),'-i',video,'-an','-vf',`select='not(mod(n,${step}))',scale=${cfg.cell_width}:-2`,'-fps_mode','vfr','-frames:v',String(cfg.frames_per_window),'-q:v','3',pattern]);
  const images=fs.readdirSync(dest).filter(n=>n.startsWith(prefix+'-')&&/\d\d.jpg$/.test(n)).sort();
  const cells=images.map((file,i)=>({id:firstId+frames.length+i,time_seconds:Number(((start+i*step)/sourceFps).toFixed(6)),file,sha256:sha(path.join(dest,file)),kind:'motion',window:index}));frames.push(...cells);
  const file=prefix+'-sheet.jpg';
  run('ffmpeg',['-v','error','-y','-framerate','1','-i',pattern,'-vf',`tile=4x3:nb_frames=${images.length}`,'-frames:v','1','-q:v','3',path.join(dest,file)]);
  sheets.push({file,sha256:sha(path.join(dest,file)),window:index,peak_time_seconds:peak.frame/sourceFps,selection_delta:peak.delta,columns:4,rows:3,cells:cells.map(c=>({id:c.id,time_seconds:c.time_seconds}))});
 }
 return {frames,sheets,selection:'Largest decoded grayscale frame changes, separated in time. Candidate timing claims are not used.',actual_sample_fps:sourceFps/step};
}
