#!/usr/bin/env python3
# harbor 归一化：定位 agent 的 markdown 交付物 -> 调 submission 自带 task_judge.py -> 打印 final_score。
# 只做 I/O 定位与取数；只评声明路径 artifacts/appeal-defence-statement.md，缺失即 0 分。task_judge 顶层有 PACKAGE_ROOT=parents[3]，
# 容器内 /tests 只有 3 层会 IndexError，故把 program_judge 嵌到 pjroot/task/tests/ 下补足深度。
import sys, os, json, subprocess, tempfile, math
from semantic_judge import adjudicate, POSITIVE, RULES
args = sys.argv[1:]
# --output PATH: also write the judge's full result there.
detail_copy = None
if "--output" in args:
    i = args.index("--output")
    detail_copy = args[i + 1] if i + 1 < len(args) else None
    del args[i:i + 2]
WS = args[0] if args else "/workspace"
DELIV = 'appeal-defence-statement.md'  # 交付物文件名 (instruction 指定)
here = os.path.dirname(os.path.abspath(__file__))
# Only the declared deliverable is scored (contract: first_nonempty_candidate_forbidden). No fallback to
# another artifacts/*.md, no caller-supplied file, no workspace-root copy: a missing declared path scores 0.
art = os.path.join(WS, "artifacts", DELIV)
if not os.path.isfile(art):
    print(json.dumps({"final_score": 0.0, "rewards": {"strict": 0.0, "lenient": 0.0},
                      "deliverable_missing": True, "artifact": art}, ensure_ascii=False))
    sys.exit(0)
# A private directory per run: a fixed path would let two submissions scored at the same
# time read each other's result. Cleaned up when the process exits.
_detail_dir = tempfile.TemporaryDirectory(prefix="pj_")
out = os.path.join(_detail_dir.name, "reward_detail.json")
judge = os.path.join(here, "pjroot", "task", "tests", "program_judge", "task_judge.py")
contract = os.path.join(here, "rubric-contract.json")
r = subprocess.run(
    [sys.executable, judge, art, "--contract", contract, "--json", out],
    capture_output=True, text=True)
try:
    d = json.load(open(out, encoding="utf-8"))
    decision=adjudicate(open(art,encoding='utf-8').read())
    for item in d['items']:
        if item['id'] in POSITIVE:
            v=decision['items'][item['id']]; item.update(program_fraction=item['fraction'],program_reason=item['reason'],fraction=v['fraction'],earned=item['weight']*v['fraction'],reason=v['reason'],semantic_evidence=v)
    semantic_d=set(RULES)-POSITIVE
    # Program patterns provide candidate diagnostics, but source-bound semantic
    # owners decide whether those spans are actually adopted errors. Remove the
    # program instances for those owners before applying the semantic verdict.
    penalties=[p for p in d['penalty_instances'] if not semantic_d.intersection(p.get('item_ids', []))]
    coeff={x['id']:x['penalty_coefficient'] for x in json.load(open(contract))['deduction_items']}
    for key in semantic_d:
        v=decision['items'][key]
        if v['fraction'] and not any(key in p.get('item_ids',[]) for p in penalties):penalties.append({'damage_instance_key':'semantic_'+key,'item_ids':[key],'penalty_coefficient':coeff[key],'semantic_evidence':v})
    d['program_penalty_instances']=d['penalty_instances'];d['penalty_instances']=penalties;d['positive_earned']=sum(x['earned'] for x in d['items']);d['retention_multiplier']=math.prod(x['penalty_coefficient'] for x in penalties);fs=d['positive_earned']*d['retention_multiplier']
    fr={x['id']:x['fraction'] for x in d['items']}; critical={'D01','D04','D05','D06','D08','D09','D12','D13','D17'};ln=float(all(fr.get(k)==1 for k in ['P02','P10','P12','P15','P16']) and not any(critical.intersection(p['item_ids']) for p in penalties))
    d.update(final_score=fs,rewards={'strict':fs,'lenient':ln},semantic_judge=decision,status='measured')
    if detail_copy:
        with open(detail_copy, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=2)
    # The full judge result (items, deduction_items, retention ...) is kept; final_score /
    # rewards / artifact stay as top-level keys for the wrappers that read them.
    full = dict(d)
    full.update({"final_score": fs, "rewards": d.get("rewards"), "artifact": art})
    print(json.dumps(full, ensure_ascii=False))
except Exception as exc:
    sys.stderr.write(f"judge rc={r.returncode} stderr={r.stderr[:400]}\n")
    if os.path.isfile(art):
        # The deliverable is there but the judge produced no result (crash, unreadable input,
        # missing tool): a scoring error, never a zero.
        sys.stderr.write(f"SCORING ERROR: judge produced no result for {art}: {exc}\n")
        sys.exit(2)
    print(json.dumps({"final_score": 0.0, "rewards": {"strict": 0.0, "lenient": 0.0},
                       "error": str(exc), "artifact": art}, ensure_ascii=False))
