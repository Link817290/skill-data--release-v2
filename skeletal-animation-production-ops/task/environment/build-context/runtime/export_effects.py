from pathlib import Path
import argparse,subprocess,csv
from PIL import Image,ImageDraw,ImageChops
from export_assets import godot_binary

def sample(project,out,godot=None):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    cmd=[godot_binary(godot),'--headless','--fixed-fps','60','--path',str(Path(project).resolve()),'--script',str(Path(__file__).with_name('sample_effects.gd')),'--',str(out),'--verification']
    p=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
    (out/'engine.log').write_text(p.stdout+p.stderr,encoding='utf-8')
    if p.returncode or 'ERROR:' in p.stderr:raise RuntimeError(p.stdout+p.stderr)

def render(out):
    out=Path(out);groups={}
    with (out/'scene-frames.csv').open(encoding='utf-8',newline='') as f:
        for r in csv.DictReader(f):
            group=groups.setdefault(int(r['frame']),[])
            if r['node']:group.append(r)
    sheet=Image.new('RGB',(4*640,2*390),(20,30,40))
    sampled=[20,34,44,58]
    for row,(theme,bg,ink) in enumerate([('dark',(15,25,40,255),'#A7C4D1'),('light',(230,236,241,255),'#385465')]):
        frames=[]
        for frame in range(0,121,2):
            im=Image.new('RGBA',(640,360),bg);d=ImageDraw.Draw(im)
            for x in range(0,640,40):d.line((x,0,x,360),fill=(*bg[:3],255) if x==0 else ((27,42,57,255) if theme=='dark' else (217,225,231,255)))
            for y in range(0,360,40):d.line((0,y,640,y),fill=(27,42,57,255) if theme=='dark' else (217,225,231,255))
            for x,y,name in [(150,290,'APPEAR'),(480,190,'TARGET')]:
                d.line((x-8,y,x+8,y),fill=ink,width=1);d.line((x,y-8,x,y+8),fill=ink,width=1);d.text((x+10,y+8),name,fill=ink)
            for r in groups[frame]:
                if r.get('visible','true').lower()!='true':continue
                src=Image.open(out/r['texture']).convert('RGBA')
                channels=src.split()
                src=Image.merge('RGBA',[ch.point(lambda x,f=float(r.get(k,1)):max(0,min(255,round(x*f)))) for ch,k in zip(channels,['red','green','blue','alpha'])])
                a,b,c,e,tx,ty,ox,oy=[float(r[k]) for k in ['a','b','c','d','tx','ty','offset_x','offset_y']]
                det=a*e-b*c
                if abs(det)<1e-12:continue
                ia,ib,ic,ie=e/det,-b/det,-c/det,a/det
                coeff=(ia,ib,-ia*tx-ib*ty-ox,ic,ie,-ic*tx-ie*ty-oy)
                transformed=src.transform(im.size,Image.Transform.AFFINE,coeff,resample=Image.Resampling.BICUBIC)
                if int(r['blend'])==1:
                    rgb=ImageChops.multiply(transformed.convert('RGB'),Image.merge('RGB',[transformed.getchannel('A')]*3))
                    im=ImageChops.add(im.convert('RGB'),rgb).convert('RGBA')
                else:im=Image.alpha_composite(im,transformed)
            d=ImageDraw.Draw(im);d.text((14,12),f'KO66 | {theme} | {frame/60:.2f}s | engine frame {frame}',fill=ink)
            frames.append(im.convert('RGB'))
            if frame in sampled:
                col=sampled.index(frame);sheet.paste(im.convert('RGB'),(col*640,row*390));ImageDraw.Draw(sheet).text((col*640+15,row*390+367),f'{theme} / {frame/60:.3f}s',fill='#D7E9F1')
        frames[0].save(out/f'{theme}.gif',save_all=True,append_images=frames[1:],duration=[30,30,40]*20+[30],loop=0,disposal=2,optimize=False)
    sheet.save(out/'contact-sheet.png')

def main():
    p=argparse.ArgumentParser();p.add_argument('--project',required=True);p.add_argument('--output',required=True);p.add_argument('--godot');a=p.parse_args();sample(a.project,a.output,a.godot);render(a.output);print('Exported engine-state CPU composite previews to '+str(Path(a.output).resolve()))
if __name__=='__main__':main()
