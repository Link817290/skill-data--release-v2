#!/usr/bin/env python3
# harbor 归一化：定位 agent 的 markdown 交付物 -> 调 submission 自带 task_judge.py -> 打印 final_score。
# 本文件只做 I/O 定位与取数，判分逻辑全部在 task_judge.py。task_judge 顶层有 PACKAGE_ROOT=parents[3]，
# 容器内 /tests 只有 3 层会 IndexError，故把 program_judge 嵌到 pjroot/task/tests/ 下补足深度。
import sys, os, json, subprocess, tempfile
WS = sys.argv[1] if len(sys.argv) > 1 else "/workspace"
# instruction.md 第 3 行是本任务唯一的交付路径祈使句：
#   "Deliver a civil statement of defense in Chinese to `artifacts/statement-of-defense.md`."
# 判据只认这一条路径。契约 observation_normalization.first_nonempty_candidate_forbidden = true
# 明文禁止「命名交付物缺失时依次回退到别的根目录、再从 glob 取第一个非空候选」；
# judge-conformance-suite.json 的 excluded_variants 也把 docx_or_pdf_carrier 与 multi_file_split
# 排除在表示变体之外。因此不回退到工作区根目录，也不 glob *.md/*.docx 取 cand[0]：
# 交付物没写到声明路径上，就是没交付，判据按缺失处理（task_judge 的 parse_failure 分支）。
DELIV = os.path.join('artifacts', 'statement-of-defense.md')  # instruction.md 指定的唯一路径
here = os.path.dirname(os.path.abspath(__file__))
if os.path.isfile(WS):
    # 调用方直接点名了一份交付物（金标复现走这条：repro 时把 golden/statement-of-defense.md
    # 作为参数传进来）。这是调用方显式给出的单一路径，不是候选搜索。
    art = WS
else:
    art = os.path.join(WS, DELIV)
# A fixed /tmp path is shared by every package and every concurrent run: when it is not
# writable (another user owns it) the judge fails to write and this script silently reads
# a stale foreign result, or reports 0.0. Use a private file and remove it afterwards.
_fd, out = tempfile.mkstemp(prefix="pj_reward_detail.", suffix=".json")
os.close(_fd)
judge = os.path.join(here, "pjroot", "task", "tests", "program_judge", "task_judge.py")
contract = os.path.join(here, "rubric-contract.json")
r = subprocess.run(
    [sys.executable, judge, art, "--contract", contract, "--json", out],
    capture_output=True, text=True)
if r.returncode:
    os.unlink(out)
    sys.stderr.write("required adjudication failed: " + r.stderr[-1200:])
    raise SystemExit(2)
try:
    d = json.load(open(out, encoding="utf-8"))
    fs = float(d["final_score"])
    print(json.dumps({"final_score": fs, "rewards": d.get("rewards"),
                       "artifact": art, "program": d}, ensure_ascii=False))
except Exception as exc:
    sys.stderr.write(f"judge rc={r.returncode} stderr={r.stderr[:400]}\n")
    print(json.dumps({"final_score": 0.0, "rewards": {"strict": 0.0, "lenient": 0.0},
                       "error": str(exc), "artifact": art}, ensure_ascii=False))
finally:
    try:
        os.unlink(out)
    except OSError:
        pass
