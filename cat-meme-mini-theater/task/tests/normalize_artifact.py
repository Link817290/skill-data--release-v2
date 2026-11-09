"""Omit expired PulseAudio session links from an immutable evaluation view."""
import json
import os
from pathlib import Path
import re
import shutil
import sys

def normalize(artifact,destination,receipt):
    artifact=Path(artifact).resolve()
    destination=Path(destination).resolve()
    receipt=Path(receipt)
    if destination==artifact or artifact in destination.parents:
        raise ValueError('Evaluation view must be outside the native artifact')
    pulse=artifact/'project/.remotion-home/.config/pulse'
    excluded={path.relative_to(artifact).as_posix():os.readlink(path)
              for path in pulse.iterdir()
              if path.is_symlink() and re.fullmatch(r'[0-9a-f]{32}-runtime',path.name)} if pulse.is_dir() else {}
    if not excluded:
        selected=artifact
    else:
        def ignore(folder,names):
            relative=Path(folder).relative_to(artifact)
            return [name for name in names
                    if (relative/name).as_posix() in excluded or
                    (name=='node_modules' and relative.parts and relative.parts[0]=='project')]
        def immutable_copy(source,target):
            try:
                os.link(source,target)
            except OSError:
                shutil.copy2(source,target)
            return target
        shutil.copytree(artifact,destination,symlinks=True,ignore=ignore,copy_function=immutable_copy)
        selected=destination
    report={'version':'pulse-session-view-v1','native_artifact':str(artifact),
            'evaluated_artifact':str(selected),'excluded_transient_links':excluded,
            'native_artifact_modified':False,
            'scope':'Only named generated PulseAudio session links; source, media, plan and other links are preserved.'}
    receipt.parent.mkdir(parents=True,exist_ok=True)
    receipt.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return selected

if __name__=='__main__':
    print(normalize(*sys.argv[1:]))
