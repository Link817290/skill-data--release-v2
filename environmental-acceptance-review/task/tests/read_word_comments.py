"""Read native OOXML comments with document anchors; does not execute document code."""
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET
import argparse,json
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W='{'+NS['w']+'}'
def extract_docx(path):
    with ZipFile(path) as z:
        body=ET.fromstring(z.read('word/document.xml'))
        paragraphs=[''.join(n.text or '' for n in p.iter(W+'t')) for p in body.iter(W+'p')]
        active={};anchors={};starts=[];ends=[];refs=[]
        for n in body.iter():
            if n.tag==W+'commentRangeStart':
                cid=n.get(W+'id');active[cid]=[];starts.append(cid)
            elif n.tag==W+'t':
                for values in active.values():values.append(n.text or '')
            elif n.tag==W+'commentRangeEnd':
                cid=n.get(W+'id');ends.append(cid)
                if cid in active:anchors[cid]=''.join(active.pop(cid))
            elif n.tag==W+'commentReference':refs.append(n.get(W+'id'))
        comments=[]
        if 'word/comments.xml' in z.namelist():
            for c in ET.fromstring(z.read('word/comments.xml')).findall('w:comment',NS):
                cid=c.get(W+'id')
                comments.append({'id':cid,'anchor':anchors.get(cid,''),'text':'\n'.join(''.join(n.text or '' for n in p.iter(W+'t')) for p in c.iter(W+'p'))})
        return {'body_paragraphs':paragraphs,'comments':comments,
                'comment_range_starts':starts,'comment_range_ends':ends,
                'comment_references':refs,'unclosed_ids':list(active)}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('document',type=Path);ap.add_argument('--out',type=Path)
    args=ap.parse_args();s=json.dumps(extract_docx(args.document),ensure_ascii=False,indent=2)
    if args.out:args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(s,encoding='utf-8')
    else:print(s)
