#!/usr/bin/env python3
"""Source-bound semantic and visual evaluation of a revised D2D manuscript.
Proofs and currently adopted claims are assessed by a required, evidence-bound
judge. Columns are extracted independently; actual figures are rendered and
compared to the original archive. Missing service is an infrastructure failure.
"""

from __future__ import annotations

import json
import hashlib
import re
import subprocess
import unicodedata
import sys
from pathlib import Path

from semantic_judge import RULES

HERE = Path(__file__).resolve().parent
GROUND = json.loads((HERE / "ground_truth.json").read_text(encoding="utf-8"))
PARAMS = json.loads((HERE / "scoring_params.json").read_text(encoding="utf-8"))

SCORER_VERSION = "2.2.0"

WEIGHTS = {key: value["weight"] for key, value in PARAMS["positive_owners"].items()}
DEDUCTIONS = dict(PARAMS["deduction_owners"])
CORE_SUBOWNERS = tuple(PARAMS["core_subowners"])
DELIVERY_CHECKS = tuple(PARAMS["delivery_checks"])
LENIENT_COMPONENTS = tuple(PARAMS["lenient_required_components"])
LENIENT_INTEGRITY = tuple(PARAMS["lenient_required_integrity"])

if PARAMS["scorer_version"] != SCORER_VERSION or abs(sum(WEIGHTS.values()) - 1) > 1e-12:
    raise RuntimeError("scoring parameter version or weight sum mismatch")
if set(WEIGHTS) != {"framing", "support_bound", "sparsity_bound", "caratheodory_dimension",
                    "simplex_dimension", "candidate_budget", "positive_rate_domain",
                    "stale_bound_cleared", "preserved_core", "delivery_integrity"}:
    raise RuntimeError("positive owner vocabulary mismatch")
DIRECT_SEMANTIC_OWNERS = set(WEIGHTS) - {"preserved_core", "delivery_integrity"}
if set(RULES) != DIRECT_SEMANTIC_OWNERS | set(CORE_SUBOWNERS) | set(LENIENT_INTEGRITY):
    raise RuntimeError("semantic owner vocabulary mismatch")
if set(DELIVERY_CHECKS) != {"readable", "page_count_plausible", "has_abstract",
                            "has_references", "has_algorithm"}:
    raise RuntimeError("native delivery vocabulary mismatch")

REWARD_FORMULAS = {
    "strict": PARAMS["strict_formula"],
    "lenient": PARAMS["lenient_formula"],
}

if PARAMS.get("settlement") != "bounded_additive_with_zero_floor":
    raise RuntimeError("unsupported strict settlement")
if PARAMS.get("judge_contract", {}).get("protocol") != "openai_responses":
    raise RuntimeError("unsupported semantic judge protocol")


def normalize(text: str) -> str:
    """Fold the notation variants PDF extraction produces into one form.

    Three artefacts have to be folded out before any anchor can match, because
    all three appear in the reference manuscript itself. Accented letters come
    back as a base letter followed by a combining mark, so a literal accented
    spelling never matches. Math fonts leave control bytes between a symbol and
    its subscript, splitting tokens that look contiguous on the page. And the
    relation and minus glyphs vary by font.
    """
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = "".join(" " if unicodedata.category(ch) == "Cc" and ch not in "\n\t" else ch
                   for ch in text)
    for source, target in (("−", "-"), ("≤", "<="), ("≥", ">="),
                           ("∗", "*"), ("×", "x")):
        text = text.replace(source, target)
    text = re.sub(r"[‘’“”]", "'", text)
    # Extraction splits subscripts and inserts stray spaces inside symbols.
    text = re.sub(r"[ \t]+", " ", text)
    return text.lower()


def has(text: str, pattern: str) -> bool:
    return re.search(pattern, text, re.IGNORECASE) is not None


def count(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text, re.IGNORECASE))


def read_pdf(path: Path) -> tuple[str, int, list[str]]:
    """Read columns independently so adjacent mathematical lines cannot interleave."""
    import pymupdf
    try:
        with pymupdf.open(path) as document:
            pages=[]
            for index,page in enumerate(document):
                mid=page.rect.width/2
                top=210 if index==0 else 0
                head=page.get_text(clip=pymupdf.Rect(0,0,page.rect.width,top),sort=True) if top else ''
                left=page.get_text(clip=pymupdf.Rect(0,top,mid,page.rect.height),sort=True)
                right=page.get_text(clip=pymupdf.Rect(mid,top,page.rect.width,page.rect.height),sort=True)
                pages.append(f'PAGE {index+1}\n'+head+'\nLEFT COLUMN\n'+left+'\nRIGHT COLUMN\n'+right)
            return '\n'.join(pages),len(document),[]
    except Exception as exc:
        return '',0,['PDF extraction failed: '+str(exc)]


def visual_evidence(path):
    """Render real candidate pages and independent archived figures for the judge."""
    import pymupdf,base64,zipfile
    images=[];graphics=[]
    with pymupdf.open(path) as document:
        for index,page in enumerate(document):
            pix=page.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False)
            images.append((f'CANDIDATE PAGE {index+1}', 'data:image/jpeg;base64,'+base64.b64encode(pix.tobytes('jpg',jpg_quality=80)).decode()))
            graphics.append({'page':index+1,'vector_paths':len(page.get_drawings()),'embedded_images':len(page.get_images())})
    archive=HERE.parent/'environment/workspace/materials/D2D_conf.zip'
    if not archive.is_file():
        archive=Path('/workspace/materials/D2D_conf.zip')
    with zipfile.ZipFile(archive) as z:
        for name in sorted(n for n in z.namelist() if n.endswith('-eps-converted-to.pdf')):
            with pymupdf.open(stream=z.read(name),filetype='pdf') as figure:
                page=figure[0];scale=min(2,1000/max(page.rect.width,page.rect.height))
                pix=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),alpha=False)
                images.append(('ARCHIVED SOURCE FIGURE '+name, 'data:image/jpeg;base64,'+base64.b64encode(pix.tobytes('jpg',jpg_quality=85)).decode()))
    return images,graphics


def score(path: Path) -> dict:
    raw,pages,notes=read_pdf(path)
    text=normalize(raw)
    # The task requires a readable, complete manuscript; it does not publish a
    # minimum page count.  Page count remains diagnostic while content checks
    # decide completeness.
    minimum=1
    delivery={'readable':bool(text.strip()),'page_count_plausible':pages>=minimum,
              'has_abstract':has(text,r'abstract'),'has_references':has(text,r'\[\s*1\s*\]'),
              'has_algorithm':has(text,r'algorithm')}
    if not text.strip():
        return {'scoring_version':SCORER_VERSION,'reward':0.,'reward_strict':0.,'reward_lenient':0.,
                'rewards':{'strict':0.,'lenient':0.},'group_points':{key:0. for key in WEIGHTS},
                'checks':{'delivery':delivery,'extraction_notes':notes}}
    from semantic_judge import adjudicate
    images,graphics=visual_evidence(path)
    semantic=adjudicate(raw,(HERE/'semantic_source.json').read_text(),images,
                        hashlib.sha256(path.read_bytes()).hexdigest())
    fractions={key:row['fraction'] for key,row in semantic['items'].items()}
    core={key:fractions[key] for key in CORE_SUBOWNERS}
    if not any(g['vector_paths'] or g['embedded_images'] for g in graphics):core['figure_evidence']=0.
    components={key:fractions[key] for key in WEIGHTS if key not in ('preserved_core','delivery_integrity')}
    components['preserved_core']=sum(core[key] for key in CORE_SUBOWNERS)/len(CORE_SUBOWNERS)
    components['delivery_integrity']=sum(delivery[key] for key in DELIVERY_CHECKS)/len(DELIVERY_CHECKS)
    harms={}
    if not core['log_objective']:harms['objective absent']='replaced_objective'
    if not (core['hamming_neighbourhood'] or core['frank_wolfe']):harms['both algorithmic mechanisms absent']='replaced_algorithm'
    if not core['figure_evidence']:harms['archived figure evidence absent']='dropped_figure_evidence'
    if not core['decision_variables']:harms['decision variables absent']='dropped_decision_variables'
    if not fractions['experimental_integrity']:
        harms['claims new experimental evidence']='fabricated_evidence_claim'
    if not fractions['capacity_constraint_integrity']:
        harms['corrupts or conflates the discrete and relaxed capacity constraints']='capacity_constraint_corruption'
    if not fractions['authorship_integrity']:
        harms['authors or affiliations are missing, replaced, or invented']='authorship_or_affiliation_corruption'
    if not fractions['citation_integrity']:
        harms['citations are missing, replaced, or invented']='citation_corruption'
    if not fractions['internal_consistency'] and fractions['capacity_constraint_integrity']:
        harms['material adopted claims contradict one another']='material_internal_contradiction'
    if (not fractions['manuscript_completeness'] and fractions['authorship_integrity']
            and fractions['citation_integrity']):
        harms['manuscript is materially incomplete']='truncated_manuscript'
    if pages<minimum:harms[f'manuscript is {pages} pages']='truncated_manuscript'
    positive=sum(WEIGHTS[key]*value for key,value in components.items())
    deduction_total=sum(DEDUCTIONS[value] for value in harms.values())
    strict=round(max(0.,positive-deduction_total),6)
    # Lenient is a completeness gate, not a "half the proof is enough" score.
    # Keep partial credit in strict while requiring every published correction
    # and the preserved manuscript contract for a binary pass.
    lenient=float(delivery['readable'] and pages>=minimum
                  and all(delivery[key] for key in ('has_abstract','has_references','has_algorithm'))
                  and all(components[key] == 1 for key in LENIENT_COMPONENTS)
                  and core['decision_variables']>=.999 and core['log_objective']>=.999
                  and (core['hamming_neighbourhood']>=.999 or core['frank_wolfe']>=.999)
                  and all(fractions[key] == 1 for key in LENIENT_INTEGRITY))
    return {'scoring_version':SCORER_VERSION,'reward':strict,'reward_strict':strict,'reward_lenient':lenient,
            'rewards':{'strict':strict,'lenient':lenient},'reward_formulas':dict(REWARD_FORMULAS),
            'scoring_contract':PARAMS,
            'group_points':{key:round(value,6) for key,value in components.items()},
            'semantic_judge':semantic,'graphics_inventory':graphics,
            'counts':{'positive_earned':round(positive,6),'deductions':round(deduction_total,6),'pages':pages,
                      'superseded_bound_occurrences':count(text,r'\b2\s*u\b'),'mention_count_is_diagnostic_only':True},
            'checks':{'core':core,'delivery':delivery,'extraction_notes':notes,
                      'harms':[{'finding':key,'trigger':value,'value':DEDUCTIONS[value]} for key,value in harms.items()]}}


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("revised_manuscript.pdf")
    if not target.is_file():
        empty = {
            "scoring_version": SCORER_VERSION,
            "reward": 0.0, "reward_strict": 0.0, "reward_lenient": 0.0,
            "rewards": {"strict": 0.0, "lenient": 0.0},
            "reward_formulas": dict(REWARD_FORMULAS),
            "group_points": {k: 0.0 for k in WEIGHTS},
            "counts": {}, "checks": {"extraction_notes": ["deliverable not found"]},
        }
        print(json.dumps(empty, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print(json.dumps(score(target), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
