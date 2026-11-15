"""Compare original producer state and all decoded image channels."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
from PIL import Image


def image_equal(left,right):
    with Image.open(left) as a,Image.open(right) as b:
        if a.size!=b.size or getattr(a,'n_frames',1)!=getattr(b,'n_frames',1):return False
        for index in range(getattr(a,'n_frames',1)):
            a.seek(index);b.seek(index)
            if a.convert('RGBA').tobytes()!=b.convert('RGBA').tobytes():return False
        return True


def compare(left,right):
    names=['scene-frames.csv','impact-events.csv','contact-sheet.png']
    names+=sorted(str(path.relative_to(left)) for path in left.rglob('*') if path.is_file() and path.suffix.lower() in ['.png','.gif'] and str(path.relative_to(left)) not in names)
    rows=[]
    for name in names:
        a,b=left/name,right/name
        row=dict(path=name,present=a.is_file() and b.is_file())
        if row['present']:
            row.update(left_sha256=hashlib.sha256(a.read_bytes()).hexdigest(),right_sha256=hashlib.sha256(b.read_bytes()).hexdigest())
            if a.suffix.lower()=='.csv':
                with a.open(newline='') as af,b.open(newline='') as bf:row['equal']=list(csv.reader(af))==list(csv.reader(bf))
                row['comparison']='parsed CSV records'
            else:row['equal']=image_equal(a,b);row['comparison']='size, decoded frame count and exact RGBA bytes in every channel'
        else:row['equal']=False
        rows.append(row)
    return dict(passed=bool(rows) and all(row['equal'] for row in rows),files=rows,encoding_equivalence=True,compared_all_rgba_channels=True)


def main():
    parser=argparse.ArgumentParser()
    for name in ['submitted','fresh','output']:parser.add_argument('--'+name,required=True)
    args=parser.parse_args();result=compare(Path(args.submitted),Path(args.fresh));Path(args.output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=result['passed'],file_count=len(result['files']))));raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
