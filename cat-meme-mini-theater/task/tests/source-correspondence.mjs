import {run,audioPcm} from './media-utils.mjs';

export function compareMedia(a,b,params){
 const pixels=f=>run('ffmpeg',['-v','error','-threads','1','-i',f,'-an','-vf','scale=64:36,format=rgb24','-fps_mode','passthrough','-threads','1','-f','rawvideo','pipe:1']).stdout;
 const x=pixels(a),y=pixels(b),frameSize=2304*3,frames=Math.floor(x.length/frameSize);let matching=0;const errors=[];
 for(let k=0;k<frames;k++){let sum=0;for(let j=0;j<frameSize;j++)sum+=Math.abs(x[k*frameSize+j]-(y[k*frameSize+j]??0));const mae=sum/frameSize;errors.push(mae);if(mae<=params.measurement.frame_mae_max)matching++;}
 const ax=audioPcm(a),ay=audioPcm(b);let energy=0,difference=0;const samples=Math.max(ax.length,ay.length)/4;
 for(let k=0;k<samples;k++){const p=k*4<ax.length?ax.readFloatLE(k*4):0,q=k*4<ay.length?ay.readFloatLE(k*4):0;energy+=p*p;difference+=(p-q)**2;}
 const relativeRmse=Math.sqrt(difference/Math.max(energy,1e-12));
 return {passed:x.length===y.length&&frames>0&&matching/frames>=params.measurement.matching_frame_fraction_min&&relativeRmse<=params.measurement.audio_relative_rmse_max,matching_frame_fraction:matching/Math.max(1,frames),compared_frames:frames,frame_mae:errors,audio_relative_rmse:relativeRmse,scope:'Every decoded frame at 64x36 RGB and full-waveform correspondence; not a pixel-identity or editorial judgment.'};
}
