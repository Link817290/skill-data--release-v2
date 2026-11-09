import path from 'node:path';
import fs from 'node:fs';
import {bundle} from '@remotion/bundler';
import {renderMedia,renderStill,selectComposition} from '@remotion/renderer';
const root=path.resolve(import.meta.dirname,'..');
const chrome=process.env.CHROME_PATH||['C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(fs.existsSync);
const serveUrl=await bundle({entryPoint:path.join(root,'src/index.tsx'),publicDir:path.join(root,'public'),outDir:path.join(root,'build')});
const shared={serveUrl,id:'ClockOut',browserExecutable:chrome,chromiumOptions:{gl:'angle'},timeoutInMilliseconds:120000};
const composition=await selectComposition(shared);
const outputIndex=process.argv.indexOf('--output');
if(outputIndex>=0&&!process.argv[outputIndex+1])throw new Error('--output requires a path');
const outputPath=path.resolve(outputIndex>=0?process.argv[outputIndex+1]:path.join(root,'../final.mp4'));
fs.mkdirSync(path.dirname(outputPath),{recursive:true});
const qa=path.resolve(root,'../qa');fs.mkdirSync(qa,{recursive:true});
if(process.argv.includes('--stills')){
  for(const frame of [60,215,350,520,610,735,880,1040,1170]){
    await renderStill({...shared,composition,frame,output:path.join(qa,`frame-${String(frame).padStart(4,'0')}.png`),imageFormat:'png',scale:.5});
    console.log(`Still ${frame}`);
  }
}else{
  let previous=-1;
  await renderMedia({...shared,composition,codec:'h264',crf:18,pixelFormat:'yuv420p',audioCodec:'aac',audioBitrate:'192k',outputLocation:outputPath,concurrency:1,onProgress:({progress})=>{const p=Math.floor(progress*20)*5;if(p!==previous){console.log(`Render ${p}%`);previous=p;}}});
  console.log('Rendered '+outputPath);
}
