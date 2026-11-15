from pathlib import Path
import argparse,ast,csv,hashlib,subprocess,sys,tempfile,os,shlex,re,math,json
from openpyxl import load_workbook
from PIL import Image
from preview_compare import equivalent_preview
TASK=Path(__file__).resolve().parents[1]
ROOT=TASK.parents[1] if len(TASK.parents)>1 else TASK.parent
TESTS=Path(__file__).resolve().parent
PACKAGED_WORKSPACE=TASK/'environment/workspace'
ORIGINAL_WORKSPACE=Path(os.environ.get('TASK_WORKSPACE','/workspace'))
if not (ORIGINAL_WORKSPACE/'project').is_dir() and (PACKAGED_WORKSPACE/'project').is_dir():ORIGINAL_WORKSPACE=PACKAGED_WORKSPACE
TOOL_DIR=Path(os.environ.get('FX_TOOLS',str(ROOT/'environment/skeletal-animation-production-ops/build-context/runtime' if (ROOT/'environment/skeletal-animation-production-ops/build-context/runtime').is_dir() else Path('/opt/fx-tools'))))
sys.path.insert(0,str(TOOL_DIR))
from export_assets import godot_binary
from export_effects import sample,render
from render_check import verify_render, RenderingUnavailable

def capture_observations(project,capture):
    """Independent source-pixel and display-contract checks, beyond export equality."""
    with (capture/'scene-frames.csv').open(encoding='utf-8') as f:rows=list(csv.DictReader(f))
    cache={};good=0;total=0;details=[]
    for r in rows:
        if not r['node']:continue
        total+=1;kind=r['animation'];frame=int(r['frame']);idx=int(r['source_frame'])
        if kind not in ('hit','appear','fly'):
            details.append(f'Unexpected animation: {kind}');continue
        group,ax,ay={'hit':('003',79,86),'appear':('023',122,214),'fly':('500',75,20)}[kind]
        expected=ORIGINAL_WORKSPACE/f'project/assets/frames/{group}/{group}_{idx:02d}.png'
        actual=capture/r['texture'];key=(str(actual),str(expected))
        if key not in cache:
            try:
                with Image.open(actual) as a,Image.open(expected) as b:cache[key]=a.size==b.size and a.convert('RGBA').tobytes()==b.convert('RGBA').tobytes()
            except (OSError,ValueError):cache[key]=False
        a,b,c,d,tx,ty,ox,oy=[float(r[k]) for k in ['a','b','c','d','tx','ty','offset_x','offset_y']]
        world=(a*(ax+ox)+b*(ay+oy)+tx,c*(ax+ox)+d*(ay+oy)+ty)
        timing=True
        if kind=='appear':target=(150,290);angle=0;timing=idx>=4 and frame<=91
        elif kind=='hit':target=(480,190);angle=0
        else:
            # The two deterministic launch windows overlap. Match either contracted path.
            options=[]
            for launch,start in [(9,(130,150)),(27,(130,260))]:
                t=(frame-launch)/30
                if 0<=t<=1.00001:
                    p=(start[0]+(480-start[0])*t,start[1]+(190-start[1])*t)
                    options.append((math.dist(world,p),p,math.atan2(190-start[1],480-start[0])))
            if not options:target=(1e9,1e9);angle=0;timing=False
            else:_,target,angle=min(options)
        geometry=math.dist(world,target)<.05 and abs(math.hypot(a,c)-1)<.0001 and abs(math.hypot(b,d)-1)<.0001 and abs(a*d-b*c-1)<.0001
        orientation=abs(math.atan2(math.sin(math.atan2(c,a)-angle),math.cos(math.atan2(c,a)-angle)))<.0001
        color=all(abs(float(r[k])-1)<.0001 for k in ['red','green','blue','alpha'])
        ok=cache[key] and r['visible'].lower()=='true' and color and int(r['blend'])==0 and geometry and orientation and timing
        good+=ok
        if not ok and len(details)<12:details.append(f'frame={frame} node={r["node"]}: pixels={cache[key]}, visible={r["visible"]}, color={color}, geometry={geometry}, orientation={orientation}, timing={timing}')
    return good/max(total,1),details


def delivered_textures(sub,actual):
    """Require every exported texture, verified by decoded pixels, not PNG encoding."""
    with (actual/'scene-frames.csv').open(encoding='utf-8') as f:
        required={r['texture'] for r in csv.DictReader(f) if r['node']}
    problems=[]
    for name in sorted(required):
        p=sub/'preview'/name
        try:
            if not p.resolve().is_relative_to((sub/'preview').resolve()):raise ValueError('Texture escapes preview')
            with Image.open(p) as supplied,Image.open(actual/name) as measured:
                if supplied.size!=measured.size or supplied.convert('RGBA').tobytes()!=measured.convert('RGBA').tobytes():
                    problems.append('Changed texture: '+name)
        except (OSError,ValueError):problems.append('Missing or unreadable texture: '+name)
    return bool(required) and not problems,problems

def command_matches(value,sub):
    for tokens in command_parts(value):
        for index,token in enumerate(tokens[:-1]):
            if not re.fullmatch(r'(python(?:\d+(?:\.\d+)?)?|py)(?:\.exe)?',Path(token.replace('\\','/')).name.lower()):continue
            if Path(tokens[index+1].replace('\\','/')).name!='export_effects.py':continue
            args=tokens[index+2:];values={};position=0
            while position+1<len(args) and args[position] in ('--project','--output'):
                values[args[position]]=args[position+1];position+=2
            # A prose annotation after the command is not an exporter argument.
            remainder=args[position:]
            if remainder and not remainder[0].startswith('('):continue
            if set(values)=={'--project','--output'} and output_path(values['--project'],sub)==sub/'project' and output_path(values['--output'],sub)==sub/'preview':return True
    return False

def command_parts(value):
    try:
        lexer=shlex.shlex(str(value),posix=True,punctuation_chars=';&|<>')
        lexer.whitespace_split=True;parts=[[]]
        for token in lexer:
            if token and all(char in ';&|<>' for char in token):parts.append([])
            else:parts[-1].append(token)
        return [part for part in parts if part]
    except ValueError:return []

def output_path(value,sub):
    path=Path(value)
    if path.is_absolute():return path.resolve()
    return (sub/Path(*path.parts[1:]) if path.parts and path.parts[0]=='output' else sub/path).resolve()

def verification_matches(value,sub):
    if command_matches(value,sub):return True
    if reexport_comparison_matches(value,sub):return True
    for tokens in command_parts(value):
        for index,token in enumerate(tokens):
            launcher=Path(token).name
            if re.fullmatch(r'python(?:\d+(?:\.\d+)?)?',launcher) and tokens[index+1:index+2]==['-c'] and len(tokens)>index+2:
                try:tree=ast.parse(tokens[index+2])
                except SyntaxError:continue
                paths=[node.value for node in ast.walk(tree) if isinstance(node,ast.Constant) and isinstance(node.value,str)]
                if any(output_path(path,sub).is_relative_to(sub) and output_path(path,sub).is_file() for path in paths if '/' in path):return True
            if launcher in ('godot','godot4') and '--path' in tokens and '--script' in tokens:
                try:
                    project=output_path(tokens[tokens.index('--path')+1],sub)
                    script=output_path(tokens[tokens.index('--script')+1],sub)
                    if project==sub/'project' and script.is_relative_to(project) and script.is_file():return True
                except (IndexError,ValueError):continue
            if launcher=='awk' and any(output_path(path,sub).is_relative_to(sub) and output_path(path,sub).is_file() for path in tokens[index+1:] if path.endswith('.csv')):return True
    return False

def reexport_comparison_matches(value,sub):
    """Accept a fresh temporary export compared with both delivered traces."""
    exports=[];compared=set()
    for tokens in command_parts(value):
        for index,token in enumerate(tokens):
            launcher=Path(token.replace('\\','/')).name.lower()
            if re.fullmatch(r'(python(?:\d+(?:\.\d+)?)?|py)(?:\.exe)?',launcher) and len(tokens)>index+1 and Path(tokens[index+1]).name=='export_effects.py':
                args=tokens[index+2:];options={};position=0
                while position+1<len(args) and args[position] in ('--project','--output'):
                    options[args[position]]=args[position+1];position+=2
                if position==len(args) and set(options)=={'--project','--output'} and output_path(options['--project'],sub)==sub/'project':
                    exports.append(output_path(options['--output'],sub))
            if launcher=='cmp' and len(tokens)>=index+3:
                remainder=tokens[index+3:]
                if remainder and not (remainder[0].startswith('[expect') or remainder[0].startswith('(')):continue
                left,right=(output_path(path,sub) for path in tokens[index+1:index+3])
                for destination in exports:
                    for name in ('scene-frames.csv','impact-events.csv'):
                        delivered=sub/'preview'/name
                        if delivered.is_file() and {left,right}=={delivered,destination/name}:compared.add(name)
    return compared=={'scene-frames.csv','impact-events.csv'}

def delivery_rows(sub,runtime,preview_ok,report=None):
    p=sub/'delivery-register.xlsx'
    if not p.is_file():return 0,['Missing delivery-register.xlsx']
    book=load_workbook(p,read_only=True,data_only=True)
    try:
        sheet=book['Delivery Register'];allrows=list(sheet.iter_rows(values_only=True))
    finally:book.close()
    headers=[str(v).strip().casefold() for v in allrows[0]]
    expected=['ticket','status','change summary','verification command','artifact paths']
    if not all(x in headers for x in expected):return 0,['Required register columns missing']
    records=[{k:r[headers.index(k)] if headers.index(k)<len(r) else None for k in expected} for r in allrows[1:] if any(v is not None for v in r)]
    if len(records)!=5 or {str(r['ticket']).strip() for r in records}!={f'FX-{i}' for i in range(301,306)}:return 0,['Expected exactly one row for each ticket']
    related={'FX-301':['C02','C03'],'FX-302':['C04','C05','C06'],'FX-303':['C07','C08'],'FX-304':['C09','C10','C11','C12'],'FX-305':['C01']}
    count=0;details=[];decisions=[]
    export_recorded=any(command_matches(r['verification command'],sub) for r in records)
    for r in records:
        ticket=str(r['ticket']).strip();note=str(r['change summary'] or '')
        paths=[x.strip().strip('`') for x in str(r['artifact paths'] or '').split(';') if x.strip()]
        paths_ok=bool(paths) and all(not Path(x).is_absolute() and (sub/x).resolve().is_relative_to(sub) and (sub/x).exists() for x in paths)
        changed=[]
        for name in ['stage.gd','stage.tscn','delivery.cfg','project.godot']:
            f=sub/'project'/name;initial=ORIGINAL_WORKSPACE/'project'/name
            if name in note and f.is_file() and initial.is_file() and f.read_bytes()!=initial.read_bytes():changed.append(name)
        behavior=all(runtime.get(c,False) for c in related[ticket]) and (preview_ok if ticket=='FX-305' else True)
        command_ok=export_recorded and verification_matches(r['verification command'],sub)
        ok=str(r['status']).strip().casefold()=='completed' and bool(changed) and paths_ok and command_ok and behavior
        decisions.append([ticket,bool(ok)])
        count+=ok;details.append(f'{ticket}: changed-file={bool(changed)}, paths={paths_ok}, command={command_ok}, behavior={behavior}')
    if report is not None:
        with (report/'delivery-checks.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.writer(f);w.writerow(['ticket','passed']);w.writerows(decisions)
    return count/5,details

def validate(submission,report,godot=None):
    sub=Path(submission).resolve();report=Path(report).resolve();report.mkdir(parents=True,exist_ok=True)
    checks=[];score=0.0;core=[]
    (report/'delivery-checks.csv').write_text('ticket,passed\n',encoding='utf-8')
    try:
        with (TESTS/'asset-manifest.csv').open(encoding='utf-8-sig',newline='') as f:expected=[r for r in csv.DictReader(f) if r['kind']=='frames']
        assert len(expected)==73
        for r in expected:
            p=sub/r['workspace_path'];assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256'],r['workspace_path']
        assert len(list((sub/'project/assets/frames').rglob('*.png')))==73
        checks.append(['A00','Original 73 PNG files intact','PASS',0,0,'SHA256 verified'])
        proc=subprocess.run([godot_binary(godot),'--headless','--fixed-fps','60','--path',str(sub/'project'),'--script',str(TESTS/'verify_runtime.gd'),'--',str(report),'--verification'],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
        (report/'engine.log').write_text(proc.stdout+proc.stderr,encoding='utf-8')
        assert proc.returncode in (0,1) and 'ERROR:' not in proc.stderr,proc.stdout+proc.stderr
        with (report/'runtime-checks.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
        assert len(rows)==12;runtime={r['id']:r['result']=='PASS' for r in rows}
        overlap_proc=subprocess.run([godot_binary(godot),'--headless','--fixed-fps','60','--path',str(sub/'project'),'--script',str(TESTS/'verify_overlap.gd'),'--',str(report/'overlap-observations.json'),'--verification'],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
        (report/'overlap-engine.log').write_text(overlap_proc.stdout+overlap_proc.stderr,encoding='utf-8')
        assert overlap_proc.returncode in (0,1) and (report/'overlap-observations.json').is_file(),overlap_proc.stdout+overlap_proc.stderr
        overlap=json.loads((report/'overlap-observations.json').read_text(encoding='utf-8'))['measurements']
        overlap_owners={'C02':['hit_anchor'],'C04':['hit_identity','hit_visible'],'C05':['visual_only'],'C06':['hit_interval_and_reclamation'],'C09':['flight_heading','asynchronous_flight_heading'],'C10':['flight_path_and_interval','asynchronous_flight_path_and_interval'],'C11':['arrival_notifications','asynchronous_arrival_notifications','same_target_arrival_notifications'],'C12':['arrival_visuals_and_reclamation','asynchronous_arrival_visuals_and_reclamation','same_target_independent_arrival_lifetimes']}
        for r in rows:
            failed=[key for key in overlap_owners.get(r['id'],[]) if not overlap[key]]
            if failed:r.update(result='FAIL',earned='0',detail=r['detail']+'; independent overlap cases failed: '+','.join(failed));runtime[r['id']]=False
            earned=float(r['earned'])*.9;available=float(r['available'])*.9;score+=earned
            checks.append([r['id'],r['check'],r['result'],earned,available,r['detail']]);core.append([r['id'],r['result'],r['detail']])
        normal_proc=subprocess.run([godot_binary(godot),'--headless','--fixed-fps','60','--path',str(sub/'project'),'--script',str(TESTS/'verify_default_entry.gd'),'--',str(report/'default-entry-observations.json')],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
        (report/'default-entry-engine.log').write_text(normal_proc.stdout+normal_proc.stderr,encoding='utf-8')
        assert normal_proc.returncode==0 and (report/'default-entry-observations.json').is_file(),normal_proc.stdout+normal_proc.stderr
        normal=json.loads((report/'default-entry-observations.json').read_text(encoding='utf-8'))
        default_completion=float(normal['timing_completion']);default_earned=2.7*default_completion;score+=default_earned
        checks.append(['C15','Configured default stage follows the supplied event timetable','PASS' if default_completion==1 else 'FAIL',default_earned,2.7,'Integration Timeline 0.65/0.95; independent SceneTree delta clock, one-sample tolerance. '+json.dumps(normal['timing_items'],sort_keys=True)])
        core.append(['DEFAULT_STAGE','PASS' if normal['usable_default_stage'] else 'FAIL','Actual configured entry: exactly two destination impacts and no effects at two seconds. Detailed timetable is scored independently.'])
        with tempfile.TemporaryDirectory(prefix='fx-verification-') as temp:
            actual=Path(temp);sample(sub/'project',actual,godot);render(actual)
            names=['contact-sheet.png','dark.gif','light.gif','scene-frames.csv','impact-events.csv']
            reproduced=all(equivalent_preview(actual/n,sub/'preview'/n) for n in names)
            coverage,details=capture_observations(sub/'project',actual)
            textures_ok,texture_details=delivered_textures(sub,actual)
            render_ok,render_data=verify_render(sub/'project',report,godot_binary(godot),TESTS/'verify_render.gd')
            visibility={kind:bool(render_data['effects'][kind]['passed']) for kind in ('hit','appear','fly')}
            art=json.loads((report/'artwork-coverage.json').read_text(encoding='utf-8'))
            visual_owners={'C02':'hit','C03':'hit','C04':'hit','C06':'hit','C07':'appear','C08':'appear','C09':'fly','C10':'fly'}
            for row in checks:
                ident=row[0];before=float(row[3])
                if ident=='C01':row[3]=9*sum(float(art[kind])*visibility[kind] for kind in visibility)/3
                elif ident in visual_owners and not visibility[visual_owners[ident]]:row[3]=0
                if row[3]!=before:
                    score+=float(row[3])-before;row[2]='FAIL';row[5]+='; required source artwork is not faithfully visible in the actual viewport'
                    runtime[ident]=False
                    for diagnostic in core:
                        if diagnostic[0]==ident:diagnostic[1]='FAIL';diagnostic[2]=row[5]
            details+=texture_details
            preview_ok=reproduced and coverage==1 and textures_ok and render_ok
            earned=6*coverage if reproduced and textures_ok and render_ok else 0;score+=earned
            checks.append(['C13','Reproduced preview shows the contracted original artwork','PASS' if preview_ok else 'FAIL',earned,6,f'reproduced={reproduced}; textures={textures_ok}; actual_render={render_ok}; correct display samples={coverage:.6f}; '+ '; '.join(details)])
            core.append(['DISPLAY','PASS' if coverage==1 and render_ok else 'FAIL','Source-pixel, geometry, timeline and actual viewport comparison'])
            (report/'visual-observations.txt').write_text('\n'.join(details) or 'All sampled display relationships agree with the contract.\n',encoding='utf-8')
        delivery,details=delivery_rows(sub,runtime,preview_ok,report);score+=4*delivery
        checks.append(['C14','Ticket-level reproducible delivery register','PASS' if delivery==1 else 'FAIL',4*delivery,4,'; '.join(details)])
        core.append(['DELIVERY','PASS' if delivery==1 else 'FAIL','Checks concrete command, changed-file citation, resolving paths and associated behavior; does not fully interpret prose'])
        for source in expected:
            assert hashlib.sha256((sub/source['workspace_path']).read_bytes()).hexdigest()==source['sha256'],'Source PNG changed during candidate execution: '+source['workspace_path']
    except RenderingUnavailable as e:
        (report/'execution-error.json').write_text(json.dumps({'kind':'rendering_infrastructure','error':str(e)})+'\n',encoding='utf-8')
        raise
    except Exception as e:
        checks.append(['ERROR','Validation could not complete or source assets were incomplete','FAIL',0,100,str(e)]);score=0.0
        core.append(['EXECUTION','FAIL','Inspect engine.log and checks.csv; an execution failure is not a measured business result'])
    with (report/'checks.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['id','check','result','earned','available','detail']);w.writerows(checks)
    with (report/'core-requirements.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['requirement','diagnostic','evidence']);w.writerows(core)
    (report/'score.txt').write_text(f'{score:.2f}\n',encoding='utf-8')
    print(f'SCORE {score:.2f}/100 | {report}')
    return score

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--submission',required=True);p.add_argument('--report',required=True);p.add_argument('--godot');a=p.parse_args();sys.exit(0 if abs(validate(a.submission,a.report,a.godot)-100)<1e-8 else 1)
