"""Resolve only documented public context for the known original producer."""
from pathlib import Path
import json
import re
import shlex
from openpyxl import load_workbook

ALLOWED=['HOME','XDG_DATA_HOME','XDG_CONFIG_HOME','XDG_CACHE_HOME']


def prepare(artifact,evidence):
    public=[];recipes=[];path=artifact/'delivery-register.xlsx'
    if not path.exists():return dict(status='known_missing',recipe_interpretable=False,selected_recipe=None,public_environment=[])
    workbook=load_workbook(path,data_only=True)
    for sheet in workbook:
        for ri,row in enumerate(sheet.iter_rows(values_only=True),1):
            for ci,value in enumerate(row,1):
                if isinstance(value,str):
                    public.append(dict(path='delivery-register.xlsx/'+sheet.title+'/'+str(ri)+':'+str(ci),text=value))
                    if 'export_effects.py' in value:recipes.append(dict(id='recipe-'+str(len(recipes)),sheet=sheet.title,row=ri,column=ci,command=value))
    for path in sorted(artifact.rglob('*')):
        if path.is_file() and not str(path.relative_to(artifact)).startswith('project/') and path.suffix.lower() in ['.md','.txt','.sh'] and path.stat().st_size<=500_000:public.append(dict(path=str(path.relative_to(artifact)),text=path.read_text(errors='replace')))
    if evidence.get('final_message'):public.append(dict(path='actual final public handover',text=evidence['final_message']))
    selected=None
    for row in recipes:
        text=row['command']
        if not re.search(r'(?:python(?:3(?:\.\d+)?)?|/[^\s]+/python3?)\s+(?:/opt/fx-tools/export_effects\.py|environment/skeletal-animation-production-ops/build-context/runtime/export_effects\.py)\s+--',text):continue
        try:
            lex=shlex.shlex(text,posix=True,punctuation_chars=True);lex.whitespace_split=True;tokens=list(lex);project=tokens[tokens.index('--project')+1];output=tokens[tokens.index('--output')+1]
        except (ValueError,IndexError):continue
        if project in ['output/project','project','/workspace/output/project'] and output in ['output/preview','preview','/workspace/output/preview']:selected=row;break
    if selected is None:return dict(status='needs_review',recipe_interpretable=False,selected_recipe=None,public_environment=[],why='No supported known producer route was established; unknown legitimate tools/routes are not business zero.')
    env=[];citations=[];prefix=selected['command'].split('export_effects.py',1)[0]
    for name in ALLOWED:
        match=re.search(r'\b'+name+r'=(/[^\s;]+)',prefix)
        if match:
            env.append(dict(name=name,value=match.group(1).strip('\"\''),interpretation='literal'));citations.append(dict(name=name,path='actual recorded recipe',quote=selected['command']))
    if not env:
        for row in public:
            for line in row['text'].splitlines():
                if re.search(r'HOME|XDG_DATA_HOME',line) and re.search(r'writ|user.data|temp|mktemp',line,re.I):
                    name='XDG_DATA_HOME' if 'XDG_DATA_HOME' in line and 'HOME' not in line.replace('XDG_DATA_HOME','') else 'HOME';env.append(dict(name=name,value='',interpretation='fresh_writable_directory'));citations.append(dict(name=name,path=row['path'],quote=line));break
            if env:break
    return dict(status='measured',recipe_interpretable=True,selected_recipe=selected,public_environment=env,public_context_citations=citations,mode='public')
