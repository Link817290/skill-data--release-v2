"""Deterministic checks for the public review-artifact contract, not business wording."""
from pathlib import Path
import argparse,json,re
from read_word_comments import extract_docx
REPORT="一期工程验收监测报告表（批注稿）.docx"
OPINION="验收材料补充意见.docx"
DRAFT="一期工程验收监测报告表（复核稿）.docx"
def norm(paragraphs):return re.sub(r"\s+","",''.join(paragraphs))
def verify(submission,inputs):
    checks=[];details={}
    for name in [REPORT,OPINION]:
        try:
            details[name]=extract_docx(submission/name)
            checks.append({"id":"readable:"+name,"passed":bool(norm(details[name]["body_paragraphs"]))})
        except Exception as e:checks.append({"id":"readable:"+name,"passed":False,"error":str(e)})
    if REPORT in details:
        doc=details[REPORT];src=extract_docx(inputs/DRAFT)
        checks.append({"id":"source_text_preserved","passed":norm(doc["body_paragraphs"])==norm(src["body_paragraphs"])})
        ids=[c["id"] for c in doc["comments"]]
        valid=(bool(ids) and len(ids)==len(set(ids)) and not doc["unclosed_ids"]
               and sorted(ids)==sorted(doc["comment_range_starts"])==sorted(doc["comment_range_ends"])==sorted(doc["comment_references"]))
        # A native range may intentionally anchor an empty table cell or blank
        # placeholder. The matched start/end/reference IDs prove the anchor;
        # only the comment itself must contain review text.
        valid=valid and all(c["text"].strip() for c in doc["comments"])
        checks.append({"id":"native_comments_with_real_anchors","passed":bool(valid),"comment_count":len(ids)})
    else:
        checks.extend([{"id":"source_text_preserved","passed":False},{"id":"native_comments_with_real_anchors","passed":False}])
    score=sum(c["passed"] for c in checks)/len(checks)
    return {"measurement_complete":True,"passed":all(c["passed"] for c in checks),"score":score,"checks":checks,
            "boundary":"Business truthfulness and completeness are judged semantically from body+anchored comments+opinion; no fixed phrases or expected comment count."}
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--submission-dir",type=Path,default=Path("/workspace/output"));p.add_argument("--input",type=Path,default=Path(__file__).resolve().parents[1]/"environment/workspace/input");p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    try:r=verify(a.submission_dir,a.input)
    except Exception as e:r={"measurement_complete":False,"passed":False,"score":None,"error":str(e)}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(r,ensure_ascii=False))

    raise SystemExit(0 if r['passed'] else (1 if r['measurement_complete'] else 2))
