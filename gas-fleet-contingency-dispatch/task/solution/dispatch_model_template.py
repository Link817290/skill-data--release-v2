#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path


DAILY_NAME = "每日供需.csv"
SNAPSHOT_NAME = "機組發電.json"
PLANT_COLUMNS = {
    "大潭": "大潭 (#1-#9)(萬瓩)",
    "通霄": "通霄 (#1-#6、GT#9)(萬瓩)",
}
TRACE_FIELDS = [
    "來源日期", "來源列號", "步序", "歷史大潭_MW", "歷史通霄_MW",
    "歷史合計_MW", "壓力指數", "目標出力_MW", "機組名稱", "廠群",
    "機組狀態", "事故機組", "快照出力_MW", "裝置容量_MW", "前步出力_MW",
    "步調整上限_MW", "下界_MW", "上界_MW", "指令出力_MW", "實際出力_MW",
    "機組負載率", "步總出力_MW", "步殘差_MW", "步可達性",
]
FULL_OUTAGE_NOTES = {
    "檢修", "歲修", "故障", "計劃停機", "環保停機", "合約限制",
}
PARTIAL_NOTES = {"部分檢修", "部分故障"}


def rounded(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def numeric(value: object) -> float | None:
    text = str(value).strip()
    if not text or text == "-":
        return None
    try:
        return float(text.rstrip("%"))
    except ValueError:
        return None


def plant_for(name: str) -> str | None:
    for plant in PLANT_COLUMNS:
        if name.startswith(plant):
            return plant
    return None


def read_daily(path: Path) -> tuple[list[dict], list[dict]]:
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for line_number, raw in enumerate(csv.DictReader(stream), 2):
            try:
                parsed = datetime.strptime(raw["日期"], "%Y%m%d")
            except (KeyError, ValueError) as exc:
                raise ValueError(f"invalid daily record at line {line_number}") from exc
            rows.append({"raw": raw, "line": line_number, "date": parsed})
    if len({row["date"] for row in rows}) != len(rows):
        raise ValueError("duplicate date in daily records")
    ordered = sorted(rows, key=lambda row: row["date"])
    if len(ordered) < 14:
        raise ValueError("fewer than fourteen daily records")
    selected = ordered[-14:]
    return ordered, selected


def read_snapshot(path: Path) -> tuple[str, list[dict]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    stamp = payload.get("DateTime")
    raw_rows = payload.get("aaData")
    if not isinstance(stamp, str) or not isinstance(raw_rows, list):
        raise ValueError("invalid snapshot structure")
    datetime.fromisoformat(stamp)
    rows = []
    for index, raw in enumerate(raw_rows):
        name = str(raw.get("機組名稱", ""))
        plant = plant_for(name)
        if raw.get("機組類型") != "燃氣" or plant is None:
            continue
        capacity = numeric(raw.get("裝置容量(MW)"))
        power = numeric(raw.get("淨發電量(MW)"))
        note = str(raw.get("備註", "")).strip()
        if capacity is None:
            availability = "不可調度"
            reason = "裝置容量缺值，不能建立上調邊界"
            ceiling = None
        elif note in FULL_OUTAGE_NOTES:
            availability = "不可調度"
            reason = f"備註為{note}，不得納入上調集合"
            ceiling = 0.0
        elif note in PARTIAL_NOTES:
            availability = "降額"
            reason = f"備註為{note}且無降額上限，保守以目前出力為上限"
            ceiling = max(power or 0.0, 0.0)
        elif note:
            availability = "不可調度"
            reason = f"備註為{note}，缺少可用上限依據"
            ceiling = 0.0
        else:
            availability = "可調度"
            reason = "裝置容量為數值且備註空白"
            ceiling = capacity
        rows.append({
            "json_index": index,
            "機組名稱": name,
            "機組類型": raw.get("機組類型"),
            "廠群": plant,
            "裝置容量_MW": capacity,
            "快照淨發電量_MW": power,
            "備註": note,
            "可用性": availability,
            "可用上限_MW": ceiling,
            "判定理由": reason,
        })
    return stamp, rows


def nearest_rank(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("empty percentile input")
    ordered = sorted(values)
    rank = max(1, math.ceil(fraction * len(ordered)))
    return ordered[rank - 1]


def allocate_minimax(units: list[dict], previous: dict[str, float], limits: dict[str, float],
                     target: float, lost_name: str) -> tuple[dict, dict]:
    bounds = {}
    active = []
    for unit in units:
        name = unit["機組名稱"]
        if name == lost_name:
            low = high = 0.0
        else:
            prior = previous[name]
            low = max(0.0, prior - limits[name])
            high = min(float(unit["裝置容量_MW"]), prior + limits[name])
            active.append(unit)
        bounds[name] = (low, high)

    lower_sum = sum(bounds[u["機組名稱"]][0] for u in units)
    upper_sum = sum(bounds[u["機組名稱"]][1] for u in units)
    served_target = min(max(target, lower_sum), upper_sum)
    lo = 0.0
    hi = max((bounds[u["機組名稱"]][1] / float(u["裝置容量_MW"]) for u in active), default=0.0) + 1.0
    for _ in range(100):
        level = (lo + hi) / 2.0
        total = 0.0
        for unit in active:
            name = unit["機組名稱"]
            low_bound, high_bound = bounds[name]
            total += min(max(level * float(unit["裝置容量_MW"]), low_bound), high_bound)
        if total < served_target:
            lo = level
        else:
            hi = level

    level = (lo + hi) / 2.0
    outputs = {lost_name: 0.0}
    for unit in active:
        name = unit["機組名稱"]
        low_bound, high_bound = bounds[name]
        outputs[name] = min(max(level * float(unit["裝置容量_MW"]), low_bound), high_bound)

    correction = served_target - sum(outputs.values())
    for unit in sorted(active, key=lambda item: item["機組名稱"]):
        if abs(correction) <= 1e-9:
            break
        name = unit["機組名稱"]
        low_bound, high_bound = bounds[name]
        slack = high_bound - outputs[name] if correction > 0 else outputs[name] - low_bound
        move = min(abs(correction), max(0.0, slack))
        outputs[name] += move if correction > 0 else -move
        correction = served_target - sum(outputs.values())

    certificate = {
        "lower_sum": lower_sum,
        "upper_sum": upper_sum,
        "served_target": served_target,
        "lambda": level,
        "reachable": lower_sum - 1e-7 <= target <= upper_sum + 1e-7,
    }
    return outputs, {"bounds": bounds, "certificate": certificate}


def build(workspace: Path) -> tuple[dict, list[dict]]:
    materials = workspace / "materials"
    daily_path = materials / DAILY_NAME
    snapshot_path = materials / SNAPSHOT_NAME
    all_daily, selected = read_daily(daily_path)
    snapshot_time, register = read_snapshot(snapshot_path)
    if len(register) == 0:
        raise ValueError("empty in-scope register")

    dispatchable = [row for row in register if row["可用性"] == "可調度"]
    online = [row for row in dispatchable if (row["快照淨發電量_MW"] or 0.0) > 0]
    if not online:
        raise ValueError("no online dispatchable unit")
    lost = sorted(online, key=lambda row: (-float(row["快照淨發電量_MW"]), row["機組名稱"]))[0]
    lost_name = lost["機組名稱"]
    loss_mw = float(lost["快照淨發電量_MW"])

    pre_event_output = sum(float(row["快照淨發電量_MW"] or 0.0) for row in dispatchable)
    post_event_output = pre_event_output - loss_mw
    remaining_capacity = sum(float(row["裝置容量_MW"]) for row in dispatchable if row is not lost)

    history = []
    for record in selected:
        raw = record["raw"]
        plant_values = {plant: float(raw[column]) * 10.0 for plant, column in PLANT_COLUMNS.items()}
        history.append({
            "date": record["date"].strftime("%Y%m%d"),
            "line": record["line"],
            "plant": plant_values,
            "combined": sum(plant_values.values()),
        })
    combined_values = [row["combined"] for row in history]
    hist_min, hist_max = min(combined_values), max(combined_values)
    if hist_max <= hist_min:
        raise ValueError("constant historical stress series")

    plant_fractions = {}
    plant_changes = {}
    for plant in PLANT_COLUMNS:
        values = [row["plant"][plant] for row in history]
        capacity = sum(float(row["裝置容量_MW"]) for row in dispatchable if row["廠群"] == plant)
        changes = [abs(current - previous) for previous, current in zip(values, values[1:])]
        fractions = [value / capacity for value in changes]
        plant_changes[plant] = changes
        plant_fractions[plant] = nearest_rank(fractions, 0.90)

    limits = {
        row["機組名稱"]: (0.0 if row["機組名稱"] == lost_name
                           else float(row["裝置容量_MW"]) * plant_fractions[row["廠群"]])
        for row in dispatchable
    }
    previous = {
        row["機組名稱"]: (0.0 if row["機組名稱"] == lost_name
                           else float(row["快照淨發電量_MW"] or 0.0))
        for row in dispatchable
    }

    trace = []
    step_certificates = []
    for step, hist in enumerate(history, 1):
        stress = (hist["combined"] - hist_min) / (hist_max - hist_min)
        target = pre_event_output * (0.85 + 0.15 * stress)
        outputs, detail = allocate_minimax(dispatchable, previous, limits, target, lost_name)
        total = sum(outputs.values())
        residual = target - total
        reachable = abs(residual) <= 1e-6
        certificate = detail["certificate"]
        step_certificates.append({
            "步序": step,
            "目標出力_MW": rounded(target),
            "下界合計_MW": rounded(certificate["lower_sum"]),
            "上界合計_MW": rounded(certificate["upper_sum"]),
            "lambda": rounded(certificate["lambda"], 9),
            "步殘差_MW": rounded(residual),
            "步可達性": "可達" if reachable else "不可達",
        })
        for unit in sorted(dispatchable, key=lambda row: row["機組名稱"]):
            name = unit["機組名稱"]
            low_bound, high_bound = detail["bounds"][name]
            output = outputs[name]
            capacity = float(unit["裝置容量_MW"])
            trace.append({
                "來源日期": hist["date"],
                "來源列號": hist["line"],
                "步序": step,
                "歷史大潭_MW": rounded(hist["plant"]["大潭"]),
                "歷史通霄_MW": rounded(hist["plant"]["通霄"]),
                "歷史合計_MW": rounded(hist["combined"]),
                "壓力指數": rounded(stress, 9),
                "目標出力_MW": rounded(target),
                "機組名稱": name,
                "廠群": unit["廠群"],
                "機組狀態": "事故退出" if name == lost_name else "可調度",
                "事故機組": "是" if name == lost_name else "否",
                "快照出力_MW": rounded(float(unit["快照淨發電量_MW"] or 0.0)),
                "裝置容量_MW": rounded(capacity),
                "前步出力_MW": rounded(previous[name]),
                "步調整上限_MW": rounded(limits[name]),
                "下界_MW": rounded(low_bound),
                "上界_MW": rounded(high_bound),
                "指令出力_MW": rounded(output),
                "實際出力_MW": rounded(output),
                "機組負載率": rounded(output / capacity, 9),
                "步總出力_MW": rounded(total),
                "步殘差_MW": rounded(residual),
                "步可達性": "可達" if reachable else "不可達",
            })
        previous = outputs

    max_abs_residual = max(abs(float(row["步殘差_MW"])) for row in step_certificates)
    max_utilization = max(float(row["機組負載率"]) for row in trace)
    feasible_steps = sum(row["步可達性"] == "可達" for row in step_certificates)
    status = "條件式可行" if feasible_steps == len(history) and max_utilization <= 1.0 + 1e-7 else "不通過"
    daily_end = selected[-1]["date"]
    snap_dt = datetime.fromisoformat(snapshot_time)
    gap_days = (snap_dt.date() - daily_end.date()).days

    source_binding = {
        "每日供需": {
            "path": f"materials/{DAILY_NAME}",
            "sha256": sha256(daily_path),
            "record_count": len(all_daily),
            "first_date": all_daily[0]["date"].strftime("%Y%m%d"),
            "last_date": all_daily[-1]["date"].strftime("%Y%m%d"),
            "selected_first_date": selected[0]["date"].strftime("%Y%m%d"),
            "selected_last_date": selected[-1]["date"].strftime("%Y%m%d"),
            "selected_record_count": len(selected),
            "role": "歷史壓力形狀",
        },
        "機組發電": {
            "path": f"materials/{SNAPSHOT_NAME}",
            "sha256": sha256(snapshot_path),
            "timestamp": snapshot_time,
            "record_count": len(json.loads(snapshot_path.read_text(encoding="utf-8-sig"))["aaData"]),
            "role": "目前機組狀態與容量邊界",
        },
        "time_separation_days": gap_days,
        "relation": "兩檔案不同時；本案為歷史形狀套用目前狀態的前瞻情景",
    }
    report = {
        "source_binding": source_binding,
        "unit_register": register,
        "scenario": {
            "scope": list(PLANT_COLUMNS),
            "horizon_records": len(history),
            "event": "線上單一機組瞬時退出",
            "lost_unit": lost_name,
            "lost_output_MW": rounded(loss_mw),
            "selection_rule": "在範圍內可調度且目前有出力的機組中，依淨發電量由大至小選取，名稱作同值序位",
            "pre_event_dispatchable_output_MW": rounded(pre_event_output),
            "post_event_initial_output_MW": rounded(post_event_output),
            "remaining_capacity_MW": rounded(remaining_capacity),
            "stress_band": [0.85, 1.0],
            "scenario_character": "前瞻壓力測試，並非實際同時序事故回放",
        },
        "model": {
            "history_conversion": "萬瓩乘以10轉為MW",
            "stress_formula": "(歷史合計-最小歷史合計)/(最大歷史合計-最小歷史合計)",
            "target_formula": "事故前可調度出力*(0.85+0.15*壓力指數)",
            "adjustment_envelope": {
                plant: {
                    "rule": "最近十四筆相鄰廠群出力絕對變化除以目前可調度容量所得之最鄰近秩第90百分位",
                    "dispatchable_capacity_MW": rounded(sum(float(row["裝置容量_MW"]) for row in dispatchable if row["廠群"] == plant)),
                    "absolute_changes_MW": [rounded(value) for value in plant_changes[plant]],
                    "fraction_per_step": rounded(plant_fractions[plant], 9),
                }
                for plant in PLANT_COLUMNS
            },
            "state_equation": "出力_t依調整係數乘裝置容量計算，並截限於下界_t與上界_t；上下界只由前步出力及步調整上限形成",
            "objective": "在每步可行總出力下最小化最大機組負載率",
            "solver": "單調共同負載率二分法，名稱排序修正浮點尾差",
            "step_certificates": step_certificates,
        },
        "metrics": {
            "steps": len(history),
            "traced_units_per_step": len(dispatchable),
            "trace_rows": len(trace),
            "feasible_steps": feasible_steps,
            "max_abs_residual_MW": rounded(max_abs_residual),
            "max_unit_utilization": rounded(max_utilization, 9),
            "final_total_output_MW": trace[-1]["步總出力_MW"],
            "minimum_headroom_to_remaining_capacity_MW": rounded(min(remaining_capacity - float(row["目標出力_MW"]) for row in step_certificates)),
        },
        "decision": {
            "status": status,
            "basis": ("十四個情景步均在逐機容量與資料導出的步調整邊界內達成目標；"
                      "結論仍受跨期、日尺度與廠群彙總限制。") if status == "條件式可行" else
                     "至少一個情景步無法在逐機容量與步調整邊界內達成目標。",
            "operational_boundary": "不得據此宣稱全系統備轉、輸電、燃料或次小時動態已通過",
        },
        "evidence": [
            {"claim": "十四筆歷史壓力形狀", "source": f"materials/{DAILY_NAME}",
             "locator": f"lines {selected[0]['line']}-{selected[-1]['line']} and headers {PLANT_COLUMNS['大潭']} / {PLANT_COLUMNS['通霄']}"},
            {"claim": "範圍內機組狀態與容量", "source": f"materials/{SNAPSHOT_NAME}",
             "locator": "unit_register保留DateTime與aaData索引"},
            {"claim": "逐步容量、狀態與平衡閉合", "source": "output/dispatch_trace.csv",
             "locator": "逐一核對每個步序與機組名稱列"},
            {"claim": "模型可重跑", "source": "output/dispatch_model.py", "locator": "由build與allocate_minimax函式生成"},
        ],
        "limitations": [
            f"機組快照晚於歷史序列末日{gap_days}日，兩者不是同時量測。",
            "每日資料是尖峰廠群彙總，不能證明單機次小時爬坡能力。",
            "情景未納入輸電限制、燃料限制、啟停時間、備轉商品與穩定度。",
            "步調整上限是歷史日尺度變化的情景包絡，不是機組額定爬坡率。",
        ],
    }
    return report, trace


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path)
    args = parser.parse_args()
    workspace = args.workspace or Path(__file__).resolve().parents[1]
    output = workspace / "output"
    output.mkdir(parents=True, exist_ok=True)
    report, trace = build(workspace)
    (output / "dispatch_review.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (output / "dispatch_trace.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=TRACE_FIELDS)
        writer.writeheader()
        writer.writerows(trace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
