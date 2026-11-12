#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math
from pathlib import Path
import numpy as np
from program_judge_runtime import Locator, ProgramJudge, load_contract

def loc(path, index, field, observed):
    return Locator(str(path), "jsonl", f"record[{index}]", f"record_slot_{index}", field, repr(observed))

def extract(path):
    records=[]; errors=[]
    try:
        lines=[line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception as exc:
        return {"artifact":path,"records":[],"errors":[str(exc)]}
    for index,line in enumerate(lines):
        try: records.append(json.loads(line))
        except Exception as exc: errors.append(f"line {index + 1}: {exc}")
    return {"artifact":path,"records":records,"errors":errors}

def expected_phase(t, segments):
    for segment in segments:
        if segment["start_frame"] <= t <= segment["end_frame"]: return segment["phase"]
    if t > segments[-1]["end_frame"]: return segments[-1]["phase"]
    return None

def scaffold_properties(rows, qpos_len, segments):
    """Assess the sampling scaffold on the properties the procedure names for it.

    The procedure asks for a compact scaffold: begin at the episode origin and the
    terminal state, infer a coarse cadence and place interior anchors on it, give
    every operationally important phase a representative, and add one interior point
    near the temporal centre of a short transition phase rather than moving the whole
    scaffold. Those are the properties checked here. Identity with any one selection
    is not among them, because several selections satisfy all of them.
    """
    times = sorted({r["t"] for r in rows if isinstance(r, dict) and type(r.get("t")) is int and 0 <= r["t"] < qpos_len})
    origin_ok = 0 in times
    covered = {expected_phase(t, segments) for t in times}
    required = {segment["phase"] for segment in segments}
    coverage_ok = bool(required) and required.issubset(covered)
    interior = [t for t in times if t not in (0, qpos_len - 1)]
    cadence_ok = False
    for cadence in range(10, qpos_len):
        on = [t for t in interior if t % cadence == 0]
        off = [t for t in interior if t % cadence != 0]
        short = sum(1 for s in segments if s["end_frame"] - s["start_frame"] + 1 < cadence)
        if len(on) >= 2 and len(off) <= short:
            cadence_ok = True
            break
    return times, origin_ok, coverage_ok, cadence_ok, sorted(required - covered)

def recursive_key_count(value):
    if isinstance(value,dict): return len(value)+sum(recursive_key_count(v) for v in value.values())
    if isinstance(value,list): return sum(recursive_key_count(v) for v in value)
    return 0

def numeric_values(value):
    if isinstance(value,dict):
        for child in value.values(): yield from numeric_values(child)
    elif isinstance(value,list):
        for child in value: yield from numeric_values(child)
    elif type(value) in (int,float): yield value

PRECONTACT_PHASES={"reach","approach"}
CLOSURE_PHASES={"contact","grasp"}

def target_triplet(row):
    v=row.get("reward_target") if isinstance(row.get("reward_target"),dict) else {}
    return [v.get(k) for k in ("tracking","contact","lift")]

def target_discipline(rows):
    """Normalised target vectors whose dominance follows the phase objective.

    The procedure asks for target components to be normalised and for their relative
    dominance to follow the phase objective: tracking before contact, contact through
    closure, and lift only after a stable grasp. A vector read on a private scale cannot
    be compared across records, and a dominance order that does not follow the objective
    trains the consumer toward the wrong goal. Both halves are required.
    """
    usable=[r for r in rows if isinstance(r,dict) and all(type(x) in (int,float) for x in target_triplet(r))]
    if not usable:
        return 0.0
    normalised=all(
        abs(max(target_triplet(r))-1.0) <= 1e-9
        or abs(sum(target_triplet(r))-1.0) <= 1e-9
        for r in usable
    )
    def dominant(row):
        v=target_triplet(row)
        return ("tracking","contact","lift")[v.index(max(v))]
    ordered=True
    for r in usable:
        phase=r.get("phase")
        if phase in PRECONTACT_PHASES and dominant(r)!="tracking": ordered=False
        if phase in CLOSURE_PHASES and dominant(r)!="contact": ordered=False
        if phase=="lift" and dominant(r)!="lift": ordered=False
    return 1.0 if (normalised and ordered) else (0.5 if ordered else 0.0)

def routing_evidence(rows, materials):
    """Extract routing labels and immutable source text without deciding semantics."""
    source=(materials/"ppo_script.py").read_text(encoding="utf-8",errors="strict")
    def labels(phases):
        out=[]
        for index,row in enumerate(rows):
            if not isinstance(row,dict) or row.get("phase") not in phases: continue
            value=row.get("use_for")
            if isinstance(value,str): out.append({"record":index,"label":value})
        return out
    return {
        "precontact_labels":labels(PRECONTACT_PHASES),
        "later_labels":labels({"contact","grasp","lift"}),
        "source_path":"materials/ppo_script.py",
        "source_text":source,
    }


def evaluate(reg, judge, materials):
    path=reg["artifact"]; rows=reg["records"]
    arrays=np.load(materials/"trajectory_unified.npz"); qpos=arrays["qpos"]; original=arrays["qpos_original"]
    segments=json.loads((materials/"grasp_phase_segments.json").read_text())["segments"]
    for slot in range(7):
        row=rows[slot] if slot < len(rows) and isinstance(rows[slot],dict) else None
        evidence=[loc(path,slot,"record",row)]
        t=row.get("t") if row else None
        valid=type(t) is int and 0 <= t < len(qpos)
        phase_ok=valid and row.get("phase")==expected_phase(t,segments)
        item_id=f"P{slot+1:02d}"
        if item_id=="P03":
            early=[r.get("action_ref",{}).get("finger_residual_limit_rad") for r in rows if isinstance(r,dict) and r.get("phase") in {"reach","approach"} and isinstance(r.get("action_ref"),dict)]
            late=[r.get("action_ref",{}).get("finger_residual_limit_rad") for r in rows if isinstance(r,dict) and r.get("phase") in {"contact","grasp","lift"} and isinstance(r.get("action_ref"),dict)]
            usable=bool(early and late) and all(type(v) in (int,float) for v in early+late) and max(late)>0
            # The procedure asks for conservative residual authority before contact and warns
            # against carrying a live training bound into the seed unchecked. A pre-contact
            # bound a shade under the post-contact one restricts nothing, so the credit turns
            # on the size of the restriction: at most half the post-contact authority is a
            # restriction, some reduction is partial, and no reduction is the unchecked bound.
            ratio=(max(early)/max(late)) if usable else None
            fraction=0.0 if ratio is None or ratio>=1.0 else (1.0 if ratio<=0.5 else 0.25)
            judge.positive(item_id,fraction,"identified",[loc(path,0,"residual_ratio",ratio)],"conservative residual authority before contact")
        elif item_id=="P05":
            early=[r.get("use_for") for r in rows if isinstance(r,dict) and r.get("phase") in {"reach","approach"}]
            late=[r.get("use_for") for r in rows if isinstance(r,dict) and r.get("phase") in {"contact","grasp","lift"}]
            ok=bool(early and late) and all(isinstance(v,str) and v.strip() for v in early+late) and set(early).isdisjoint(set(late))
            judge.positive(item_id,1 if ok else 0,"identified",[loc(path,0,"routing_sequence",early+late)],"scalar phase aware downstream routing")
        elif item_id=="P06":
            terminal=[r for r in rows if isinstance(r,dict) and r.get("t")==len(qpos)-1 and r.get("phase")==segments[-1]["phase"]]
            judge.positive(item_id,1 if terminal else 0,"identified",[loc(path,slot,"terminal_frame",terminal)],"stitched terminal tail coverage")
        elif item_id=="P07":
            applicable=[r for r in rows if isinstance(r,dict) and type(r.get("t")) is int and 0<=r["t"]<len(qpos)]
            ok=bool(applicable) and all(r.get("phase")==expected_phase(r["t"],segments) for r in applicable)
            judge.positive(item_id,1 if ok else 0,"identified",[loc(path,slot,"phase_sequence",[(r.get("t"),r.get("phase")) for r in applicable])],"absolute annotation intervals with terminal extension")
        else:
            phase_fraction=1 if phase_ok else 0
            judge.positive(item_id,phase_fraction,"identified" if row else "confirmed_missing",evidence,"strict local phase relation for the selected row")
        obs=row.get("obs") if row and isinstance(row.get("obs"),dict) else {}
        mean=obs.get("qpos_mean_abs"); dim=obs.get("qpos_dim")
        mean_ok=valid and type(mean) in (int,float) and math.isfinite(mean) and abs(mean-float(np.mean(np.abs(qpos[t])))) <= 5e-7
        dim_ok=valid and type(dim) is int and dim==qpos.shape[1]
        terminal_base=obs.get("base_z")
        terminal_base_ok=slot != 6 or (valid and type(terminal_base) in (int,float) and math.isfinite(terminal_base) and abs(terminal_base-float(qpos[t,2])) <= 5e-7)
        row_observation_ok=mean_ok and dim_ok and terminal_base_ok
        mean_fraction=1 if row_observation_ok else 0
        judge.positive(f"P{slot+8:02d}",mean_fraction,"identified" if row else "confirmed_missing",[loc(path,slot,"obs.qpos_mean_abs",mean)],"strict corrected row mean derivation for the selected row")
        if slot < 6:
            base=obs.get("base_z"); base_ok=valid and type(base) in (int,float) and math.isfinite(base) and abs(base-float(qpos[t,2])) <= 5e-7
            base_fraction=1 if base_ok else 0
            judge.positive(f"P{slot+15:02d}",base_fraction,"identified" if row else "confirmed_missing",[loc(path,slot,"obs.base_z",base)],"strict corrected third coordinate derivation for the selected row")
    times, origin_ok, coverage_ok, cadence_ok, uncovered = scaffold_properties(rows, len(qpos), segments)
    judge.positive("P21",1 if origin_ok else 0,"identified",[loc(path,0,"selected_times",times)],"scaffold begins at the episode origin")
    judge.positive("P22",1 if coverage_ok else 0,"identified",[loc(path,0,"phases_without_representative",uncovered)],"every declared phase has a representative row")
    judge.positive("P23",1 if cadence_ok else 0,"identified",[loc(path,0,"selected_times",times)],"interior anchors sit on one coarse cadence apart from short phase interior points")
    judge.positive("P24",target_discipline(rows),"identified",[loc(path,0,"reward_targets",[target_triplet(r) for r in rows if isinstance(r,dict)][:4])],"normalised phase objective targets")
    routing=routing_evidence(rows,materials)
    evidence=[loc(path,0,"routing_labels",{
        "precontact":routing["precontact_labels"],"later":routing["later_labels"]})]
    judge.positive("P25",0.0,"ambiguous",evidence,
                   "open routing equivalence is reserved for the source-bound semantic judge")
    judge.semantic_candidate("P25","Decide whether the adopted precontact and later labels are semantically equivalent to the two consumer routes established by ppo_script.py.",evidence+[Locator(
        str(materials/"ppo_script.py"),"text","whole_file","routing_source",
        "source_text",routing["source_text"])])
    if reg["errors"] or not rows: judge.deduct("D01","parse_failure_or_empty",1,[loc(path,0,"parse",reg["errors"] or ["no nonempty JSONL records"])],"invalid or empty JSONL")
    ts=[]
    for i,row in enumerate(rows):
        if not isinstance(row,dict): judge.deduct("D02",f"nonobject:{i}",1,[loc(path,i,"record",row)],"record is not an object"); continue
        bad_nested=[key for key in ("obs","action_ref","reward_target") if key in row and not isinstance(row.get(key),dict)]
        if bad_nested: judge.deduct("D12",f"nested_type:{i}",1,[loc(path,i,"nested_types",bad_nested)],"required nested carrier has incompatible type")
        nonfinite=[value for value in numeric_values(row) if not math.isfinite(value)]
        if nonfinite: judge.deduct("D14",f"nonfinite:{i}",1,[loc(path,i,"numeric_values",nonfinite)],"record contains nonfinite numeric value")
        key_count=recursive_key_count(row)
        if key_count>=15: judge.deduct("D19",f"field_overrun:{i}",key_count-14,[loc(path,i,"recursive_key_count",key_count)],"record exceeds local field shape upper bound")
        if key_count<=9: judge.deduct("D21",f"field_underrun:{i}",10-key_count,[loc(path,i,"recursive_key_count",key_count)],"record falls below local field shape lower bound")
        required_top={"t","phase","obs","action_ref","reward_target","use_for"}
        if not required_top.issubset(row): judge.semantic_candidate("W_SCHEMA","Publicly required top level members are missing; report as a nonnumeric schema warning.",[loc(path,i,"keys",sorted(row))])
        t=row.get("t"); obs=row.get("obs") if isinstance(row.get("obs"),dict) else {}
        if type(t) is not int: judge.deduct("D03",f"t_type:{i}",1,[loc(path,i,"t",t)],"t is not integer"); continue
        if not 0 <= t < len(qpos): judge.deduct("D04",f"t_range:{i}",1,[loc(path,i,"t",t)],"t outside corrected trajectory"); continue
        ts.append(t)
        phase=expected_phase(t,segments)
        if row.get("phase") not in {s["phase"] for s in segments}: judge.deduct("D17",f"phase_vocab:{i}",1,[loc(path,i,"phase",row.get("phase"))],"unknown phase")
        elif row.get("phase") != phase: judge.deduct("D07",f"phase_wrong:{i}",1,[loc(path,i,"phase",row.get("phase"))],"phase contradicts interval")
        mean=obs.get("qpos_mean_abs")
        if type(mean) in (int,float) and math.isfinite(mean) and abs(mean-float(np.mean(np.abs(qpos[t])))) > 5e-7: judge.deduct("D08",f"mean_wrong:{i}",1,[loc(path,i,"obs.qpos_mean_abs",mean)],"mean contradicts corrected row")
        dim=obs.get("qpos_dim")
        if dim is not None and dim != qpos.shape[1]: judge.deduct("D09",f"dim_wrong:{i}",1,[loc(path,i,"obs.qpos_dim",dim)],"dimension contradicts corrected array")
        base=obs.get("base_z")
        if type(base) in (int,float) and math.isfinite(base) and abs(base-float(qpos[t,2])) > 5e-7: judge.deduct("D10",f"base_wrong:{i}",1,[loc(path,i,"obs.base_z",base)],"base z contradicts corrected row")
        if set(row)-{"t","phase","obs","action_ref","reward_target","use_for"}: judge.deduct("D11",f"extra_keys:{i}",1,[loc(path,i,"keys",sorted(row))],"unsupported top level fields")
        if len(original)>t and type(mean) in (int,float) and abs(mean-float(np.mean(np.abs(original[t])))) <= 5e-7 and abs(mean-float(np.mean(np.abs(qpos[t])))) > 5e-7: judge.deduct("D13",f"original:{i}",1,[loc(path,i,"obs.qpos_mean_abs",mean)],"used original trajectory")
        action=row.get("action_ref") if isinstance(row.get("action_ref"),dict) else {}
        residual=action.get("finger_residual_limit_rad")
        if type(residual) in (int,float) and residual < 0: judge.deduct("D15",f"negative_residual:{i}",1,[loc(path,i,"action_ref",residual)],"negative residual limit")
        reward=row.get("reward_target") if isinstance(row.get("reward_target"),dict) else {}
        if any(type(v) in (int,float) and not 0 <= v <= 1 for v in reward.values()): judge.deduct("D16",f"reward_range:{i}",1,[loc(path,i,"reward_target",reward)],"reward outside normalized range")
    if len(ts)!=len(set(ts)): judge.deduct("D05","duplicate_t",1,[loc(path,0,"t_sequence",ts)],"duplicate time")
    by_time={}
    for i,row in enumerate(rows):
        if isinstance(row,dict) and type(row.get("t")) is int:
            if row["t"] in by_time and by_time[row["t"]]!=row: judge.deduct("D20",f"conflicting_t:{row['t']}",1,[loc(path,i,"record",row)],"same time has conflicting adopted record values")
            by_time.setdefault(row["t"],row)
    if any(a>=b for a,b in zip(ts,ts[1:])): judge.deduct("D06","nonascending",1,[loc(path,0,"t_sequence",ts)],"time order is not strict")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("artifact",type=Path); ap.add_argument("--materials",type=Path,required=True); ap.add_argument("--contract",type=Path,required=True); ap.add_argument("--json",type=Path)
    args=ap.parse_args(); judge=ProgramJudge(load_contract(args.contract),args.artifact); evaluate(extract(args.artifact),judge,args.materials); result=judge.finish(); out=json.dumps(result,indent=2)+"\n"
    if args.json: args.json.write_text(out)
    else: print(out,end="")
if __name__=="__main__": main()
