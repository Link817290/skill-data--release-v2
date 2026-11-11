#!/usr/bin/env python3
"""v11 decision-chain verifier; numeric truth is derived from supplied inputs."""

from __future__ import annotations

from pathlib import Path
from copy import deepcopy
import hashlib
import json
import os
import re
import sys
import tempfile

HERE = Path(__file__).resolve().parent
PARAMS = Path(os.environ.get("SCORING_PARAMS", HERE / "scoring_params.json"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "solution"))
import semantic_checks as v9  # noqa: E402
from sheet_primitives import Score, close, column, norm, number, value, workbook  # noqa: E402
from metric_checks import primary_checks
from q12_pipeline import advanced_tables, adopted, calibration_targets, load_raw, rake_rows, v9_quality_tables  # noqa: E402
from semantic_judge import review as semantic_review, SemanticUnavailable

CALIBRATED_TREND_FLOOR = 0.30



def item(report, key):
    row = next((x for x in report.get("items", []) if x.get("item") == key), None)
    return float(row.get("earned", 0)) if row else 0.0


def scaled(report, key, old_max, new_max):
    return new_max * item(report, key) / old_max


def locate(book, groups):
    """Find tables by semantic header groups, allowing title rows before headers."""
    found = []
    for sheet, rows in book.items():
        for ri, header in enumerate(rows[:20]):
            cols = []
            for aliases in groups:
                # 取最具体的命中，不取最左的：标注列排在被描述列的左边且会被短别名
                # 子串命中，取第一个就会读错列。完全相等优先，其次别名越长越优先。
                candidates = []
                for i, cell in enumerate(header):
                    # 表头是列名，不是句子。备注列里整句的说明文字会含有列名词，
                    # 让数据行被当成表头，下面按行数就全错位了。
                    if len(norm(cell)) > 48: continue
                    hits = [norm(a) for a in aliases if norm(a) == norm(cell) or norm(a) in norm(cell)]
                    if hits:
                        best = max(hits, key=len)
                        candidates.append(((best == norm(cell), len(best)), i))
                cols.append(max(candidates)[1] if candidates else None)
            if all(c is not None for c in cols):
                found.append((sheet, ri, header, cols))
    return found


def equivalent(raw, expected):
    actual = number(raw)
    if actual is None:
        return False
    return any(close(actual, expected * scale, 2e-5) for scale in (1, 5, 100))


def all_text(book, notes):
    return notes.lower() + "\n" + "\n".join(str(cell).lower() for rows in book.values() for row in rows for cell in row if isinstance(cell, str))


def semantic_evidence(root: Path):
    """Structure-neutral evidence used to repair legal title/header and alias variants."""
    materials = root / "materials"; output = root / "output"
    raw, meta = load_raw(materials)
    clean = workbook(output / "cleaned_samples.xlsx") if (output / "cleaned_samples.xlsx").exists() else {}
    analysis = workbook(output / "engagement_analysis.xlsx") if (output / "engagement_analysis.xlsx").exists() else {}
    text = all_text(analysis, "")
    privacy_source = text + "\n" + all_text(clean, "")
    privacy_scrubbed = re.sub(r"(?i)\b[0-9a-f]{32,}\b", "", privacy_source)
    privacy_violation = any(re.search(p, privacy_scrubbed) for p in (r"(?<!\d)1[3-9]\d{9}(?!\d)", r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}", r"(?<!\d)\d{17}[\dXx](?!\d)"))

    ledgers = locate(clean, [["source_file", "源文件"], ["source_row", "source_sheet_row", "source_row_num", "源行"], ["response_key", "响应键"]])
    physical = max((sum(bool(str(value(r, cols[2])).strip()) for r in clean[s][ri + 1:]) for s, ri, _, cols in ledgers), default=0)
    # 按响应键去重来数被采纳的人数，不数行数。台账可以按响应级发布，也可以按
    # 响应×题目发布——后者一个人占十几行，行数直接和"人口膨胀"的阈值撞上，
    # 于是一份算得完全正确的作答会被当成扩大了口径而整体封顶。粒度不同不是错误。
    adopted_counts = []
    for s, ri, header, cols in ledgers:
        for alias in ("main_adopted", "logical_adopted", "adopted_for_main", "canonical_export_record", "is_canonical", "adoption_status"):
            ci = column(header, [alias])
            if ci is None:
                continue
            def is_adopted(raw_value):
                token = norm(raw_value)
                return raw_value is True or number(raw_value) == 1 or token in {"yes", "true", "是", "adopted", "adoptedlatestexport"} or token.startswith("adopted")
            adopted_counts.append(len({
                str(value(r, cols[2])).strip() for r in clean[s][ri + 1:]
                if is_adopted(value(r, ci)) and str(value(r, cols[2])).strip()
            }))
    # 问的是"有没有把应答口径认对"，所以看有没有哪张表给出了正确人口，而不是取最大值。
    # 取最大值会惩罚多发布证据的作答：物理台账本来就该有全部记录，它一出现就顶掉了
    # 旁边那张正确的应答表。口径被放大的情形由 inflated 单独判。
    logical_counts = set()
    for s, ri, _, cols in locate(clean, [["wave_code", "wave", "波次"], ["response_key", "响应键"]]):
        keys = {(str(value(r, cols[0])).strip(), str(value(r, cols[1])).strip()) for r in clean[s][ri + 1:] if str(value(r, cols[1])).strip()}
        if len(keys) <= 800: logical_counts.add(len(keys))
    logical = 739 if 739 in logical_counts else max(logical_counts, default=0)
    # ID-01 is a response-key relationship, not a physical-table layout rule.
    # Accept the three fields in one table or in separate keyed tables.
    identity_keys = []
    for aliases in (["match_grade", "匹配等级"], ["allowed_use", "允许用途"], ["frame_band", "结构分组"]):
        keys = set()
        for s, ri, _header, cols in locate(clean, [aliases, ["response_key", "响应键"]]):
            keys.update(str(value(row, cols[1])).strip() for row in clean[s][ri + 1:]
                        if str(value(row, cols[0])).strip() and str(value(row, cols[1])).strip())
        identity_keys.append(keys)
    identity = bool(all(identity_keys) and set.intersection(*identity_keys))

    # POP-01 and ID-01 do not say whether the 13 canonical responses submitted
    # outside their employment dates remain in calibration. Both readings obey
    # the published survey fields: the inclusive profile uses survey-side frame
    # bands; the employment-valid profile excludes those 13 before raking.
    profiles = {"survey_frame": raw, "employment_valid": deepcopy(raw)}
    for row in profiles["employment_valid"]:
        if row["canonical"] and row["core_link"] == "time_impossible":
            row["calibration_adopted"] = False
            row["calibration_weight"] = 0.0
    targets = calibration_targets(materials)
    expected_profiles = {}
    for profile_name, profile_rows in profiles.items():
        expected_weights = {}; expected_weight_diagnostics = {}
        for wave in ("alpha", "beta"):
            rows = [r for r in profile_rows if r["wave"] == wave and r["calibration_adopted"]]
            weights, diagnostics = rake_rows(rows, targets)
            expected_weights.update(weights)
            for row in profile_rows:
                if row["wave"] == wave and row["canonical"]:
                    row["calibration_weight"] = weights.get(row["response_key"], 0.0)
            _, reverse_diagnostics = rake_rows(rows, dict(reversed(list(targets.items()))))
            expected_weight_diagnostics[wave] = [diagnostics, reverse_diagnostics]
        expected_profiles[profile_name] = (expected_weights, expected_weight_diagnostics)

    candidate_weight_columns = []
    for s, ri, _, cols in locate(clean, [["response_key", "响应键"], ["final_weight", "final_calibration_weight", "最终权重"]]):
        seen = {}
        for row in clean[s][ri + 1:]:
            key = str(value(row, cols[0])).strip(); val = number(value(row, cols[1]))
            if key and val is not None: seen[key] = val
        candidate_weight_columns.append(seen)
    weight_rows = max((len(seen) for seen in candidate_weight_columns), default=0)
    if weight_rows < 700:
        for s, ri, _, cols in locate(clean, [["response_key", "响应键"], ["analysis_weight", "calibration_weight", "权重"]]):
            count = sum(bool(str(value(r, cols[0])).strip()) and number(value(r, cols[1])) is not None for r in clean[s][ri + 1:])
            weight_rows = max(weight_rows, count)
    # 最终权重列按数值认，不按列名认。同一列的写法是开放集合——final_weight、
    # weight_final、weight_stage_5_final_normalised——而权重链是所有释放闸的前置，
    # 认不出这一列就整份作答归零。做法：在带 response_key 的表里逐列比对期望权重，
    # 取对得最多的那一列。权重是耙平算出来的十几位小数，误命中不成立。
    for s, ri, _, cols in locate(clean, [["response_key", "响应键"]]):
        rows = clean[s][ri + 1:]
        width = max((len(r) for r in rows), default=0)
        for ci in range(width):
            if ci == cols[0]: continue
            seen = {}
            for row in rows:
                key = str(value(row, cols[0])).strip(); val = number(value(row, ci))
                if key and val is not None: seen[key] = val
            candidate_weight_columns.append(seen)
            weight_rows = max(weight_rows, len(seen))

    profile_matches = []
    for profile_name, (expected_weights, diagnostics) in expected_profiles.items():
        best_hits = best_extra = 0
        for seen in candidate_weight_columns:
            hits = sum(key in expected_weights and close(val, expected_weights[key], 2e-5) for key, val in seen.items())
            extra = sum(key not in expected_weights or not close(val, expected_weights[key], 2e-5) for key, val in seen.items())
            if hits > best_hits or (hits == best_hits and extra < best_extra):
                best_hits, best_extra = hits, extra
        exact = best_hits >= len(expected_weights) - 4 and best_extra <= 4
        profile_matches.append((exact, best_hits, -best_extra, profile_name))
    final_exact, exact_weights, _, selected_profile = max(profile_matches)
    raw = profiles[selected_profile]
    expected_weights, expected_weight_diagnostics = expected_profiles[selected_profile]
    advanced = advanced_tables(raw, materials, meta)
    quality = v9_quality_tables(raw, materials, meta)

    p = advanced["primary_trend"][1]
    primary_exact = any(sum(equivalent(cell, expected) for cell in row for expected in (p[4], p[5], p[6])) >= 3 for rows in analysis.values() for row in rows)
    uncertainty_exact = any(sum(equivalent(cell, expected) for cell in row for expected in (p[6], p[7], p[8], p[9])) >= 4 for rows in analysis.values() for row in rows)
    replicate_exact = 0
    expected_reps = {int(r[0]): r for r in advanced["jackknife_replicates"][1:]}
    for s, ri, _, cols in locate(analysis, [["variance_group", "deleted_group", "replicate_group", "方差组"], ["alpha_estimate", "alpha_percent", "alpha_anchor_pct", "alpha_score_pct", "alpha估计"], ["beta_estimate", "beta_percent", "beta_anchor_pct", "beta_score_pct", "beta估计"], ["difference", "change", "变化"]]):
        ok = 0
        for row in analysis[s][ri + 1:]:
            g = number(value(row, cols[0]))
            if g in expected_reps:
                exp = expected_reps[int(g)]
                ok += equivalent(value(row, cols[1]), exp[3]) and equivalent(value(row, cols[2]), exp[4]) and equivalent(value(row, cols[3]), exp[5])
        replicate_exact = max(replicate_exact, ok)
    # 再按数值判一次。复本表的列名写法是开放集合——alpha_estimate / estimate_alpha /
    # period_1_estimate / alpha_anchor_pct 指的是同一个量——别名表枚举不全，
    # 枚举不到就把算对的判成没做。一行里同时出现某复本组编号和它的三个期望值，
    # 这一组就是算对了；十几位有效数字下误命中不成立。
    if replicate_exact < len(expected_reps):
        rows_all = [row for rows in analysis.values() for row in rows]
        by_value = sum(
            any(all(any(equivalent(cell, x) for cell in row) for x in (exp[3], exp[4], exp[5]))
                and any(number(cell) == group for cell in row) for row in rows_all)
            for group, exp in expected_reps.items()
        )
        replicate_exact = max(replicate_exact, by_value)

    org_exact = org_se_exact = 0
    expected_org = {str(r[0]): r for r in quality["org_small_domain"][1:]}
    for s, ri, header, cols in locate(analysis, [["survey_org", "调查组织", "组织"], ["direct_change", "change_pp", "变化_pp", "直接变化"]]):
        oc, dc = cols; sec = column(header, ["jackknife_se", "jk_se_pp", "direct_jk_se", "标准误"])
        rows = {str(value(r, oc)): r for r in analysis[s][ri + 1:]}
        hit = sehit = 0
        for org, exp in expected_org.items():
            row = rows.get(org, []); hit += equivalent(value(row, dc), exp[3]); sehit += sec is not None and equivalent(value(row, sec), exp[4])
        org_exact = max(org_exact, hit); org_se_exact = max(org_se_exact, sehit)

    panel_exact = panel_uncertainty = False
    pt = advanced["panel_anchor"]
    panel_values = {r[0]: r[1] for r in pt[1:]}
    for rows in analysis.values():
        for row in rows:
            if any(number(c) == 107 for c in row):
                panel_exact = panel_exact or sum(equivalent(c, panel_values[k]) for c in row for k in ("alpha_anchor_pct", "beta_anchor_pct", "paired_change_pct")) >= 3
                panel_uncertainty = panel_uncertainty or sum(equivalent(c, panel_values[k]) for c in row for k in ("person_delta_se", "normal_ci_low", "normal_ci_high")) >= 3
    for s, ri, _, cols in locate(analysis, [["metric", "指标"], ["estimate_pct", "value", "数值"]]):
        metrics = {norm(value(r, cols[0])): r for r in analysis[s][ri + 1:]}
        alpha_row = next((r for k, r in metrics.items() if "alphapanelanchorpct" in k), [])
        beta_row = next((r for k, r in metrics.items() if "betapanelanchorpct" in k), [])
        change_row = next((r for k, r in metrics.items() if "pairedchange" in k), [])
        if alpha_row and beta_row and change_row:
            panel_exact = equivalent(value(alpha_row, cols[1]), panel_values["alpha_anchor_pct"]) and equivalent(value(beta_row, cols[1]), panel_values["beta_anchor_pct"]) and equivalent(value(change_row, cols[1]), panel_values["paired_change_pct"])
            panel_uncertainty = panel_uncertainty or any(equivalent(cell, panel_values["normal_ci_low"]) for cell in change_row) and any(equivalent(cell, panel_values["normal_ci_high"]) for cell in change_row)

    # Read analysis-owned outputs independently. Correct audit weights are not
    # evidence that the release actually used them or computed valid diagnostics.
    primary_quality, _ = primary_checks(analysis, advanced["primary_trend"])
    diagnostic_aliases = {
        "n": ["n", "样本数"], "sum_w": ["sum_w", "sum_weights", "权重和"],
        "min_w": ["min_w", "min_weight", "最小权重"], "max_w": ["max_w", "max_weight", "最大权重"],
        "ess": ["kish_ess", "effective_sample_size", "ess"],
        "design_effect": ["design_effect", "deff", "设计效应"],
        "margin_error": ["max_margin_error", "margin_error", "最大边际误差"],
        "preliminary_iterations": ["preliminary_iterations", "初步迭代次数"],
        "post_trim_iterations": ["post_trim_iterations", "截尾后迭代次数"],
    }
    diagnostic_correct = {wave: set() for wave in expected_weight_diagnostics}
    for sheet, ri, header, cols in locate(analysis, [["wave", "wave_code", "波次"], ["sum_w", "sum_weights", "权重和"]]):
        wc = cols[0]
        for row in analysis[sheet][ri+1:]:
            wave = str(value(row, wc)).strip().lower()
            if wave not in expected_weight_diagnostics: continue
            for key, aliases in diagnostic_aliases.items():
                col = column(header, aliases)
                actual = number(value(row, col)) if col is not None else None
                profiles = expected_weight_diagnostics[wave]
                if key in {"preliminary_iterations", "post_trim_iterations"}:
                    # Resolve the pair together: unrelated counts must not be
                    # assembled into a fictitious calibration profile.
                    pair = []
                    for stage in ("preliminary_iterations", "post_trim_iterations"):
                        ci = column(header, diagnostic_aliases[stage])
                        pair.append(number(value(row, ci)) if ci is not None else None)
                    valid_pair = any(
                        pair == [profile[stage] for stage in ("preliminary_iterations", "post_trim_iterations")]
                        for profile in profiles
                    )
                    if final_exact and valid_pair:
                        diagnostic_correct[wave].add(key)
                elif actual is not None and actual >= 0 and any(
                    close(actual, profile[key], 2e-5) for profile in profiles
                ):
                    diagnostic_correct[wave].add(key)
    diagnostic_fraction = sum(len(v) for v in diagnostic_correct.values()) / (len(expected_weight_diagnostics)*len(diagnostic_aliases))

    return {
        "physical": physical >= 795, "logical": logical == 739, "inflated": bool(adopted_counts) and min((count for count in adopted_counts if count), default=0) > 750, "identity": identity,
        "weights_present": weight_rows >= 700, "final_exact": final_exact,
        "analysis_applies_weights": primary_quality == 6, "analysis_weight_diagnostics": diagnostic_fraction,
        "primary_exact": primary_exact, "replicate_exact": replicate_exact >= 20, "uncertainty_exact": uncertainty_exact,
        "cronbach_present": "cronbach" in text or "内部一致" in text, "measurement_boundary": ("测量" in text and ("不证明" in text or "不等于" in text)),
        "org_exact": org_exact >= 6, "org_se_exact": org_se_exact >= 6,
        "panel_exact": panel_exact, "panel_uncertainty": panel_uncertainty,
        "action_doc": "action" in text or "行动" in text,
        "privacy_safe": not privacy_violation,
        "boundary": all(term in text for term in ("因果", "正式响应率", "外部常模")),
        "calibration_population_profile": selected_profile,
        "calibration_population_exact": bool(final_exact),
        "_selected_raw": raw,
    }


def release_limit(floor, full, prereqs):
    """依赖放行额度，按前置完成度连续给，而不是全有全无。

    二值放行会把整段压在地板上：前置差一点点和完全没做拿到同样的额度，段内做对的
    部分完全不体现，好坏也不再可分。前置没做好确实该限流，但限流强度应随完成度变化。

    prereqs 为 (earned, required) 列表；取各项完成比例的最小值作为放行比例，
    保留"短板决定放行"的原意，同时消除悬崖。
    """
    ratios = [min(1.0, e / r) for e, r in prereqs if r > 0]
    frac = min(ratios) if ratios else 0.0
    return floor + (full - floor) * frac


def evaluate(root: Path):
    contract = json.loads(PARAMS.read_text(encoding="utf-8"))
    owners = contract.get("owners")
    policy = contract.get("numeric_policy")
    policy_fields = {"classification", "uniqueness", "provenance", "dependency", "root_cause_dedup", "missing_vs_wrong"}
    if (not isinstance(policy, dict) or set(policy) != policy_fields
            or not all(isinstance(value, str) and value.strip() for value in policy.values())):
        raise ValueError("numeric policy invalid")
    fields = {"points", "severity", "residual_value", "root_cause_dedup", "evaluates", "importance", "weight_reason", "prerequisites", "calculation", "missing_vs_wrong"}
    if not isinstance(owners, dict) or set(owners) != set("ABCDEF") or sum(v.get("points", 0) for v in owners.values()) != 100:
        raise ValueError("owner contract coverage or point total invalid")
    for key, detail in owners.items():
        if (not isinstance(detail, dict) or set(detail) != fields
                or not all(isinstance(detail[name], str) and detail[name].strip()
                           for name in fields - {"points", "prerequisites"})
                or not isinstance(detail["prerequisites"], list) or not detail["prerequisites"]
                or not all(isinstance(value, str) and value.strip() for value in detail["prerequisites"])):
            raise ValueError(f"owner contract invalid: {key}")
    sem = semantic_evidence(root)
    selected_raw = sem.pop("_selected_raw")
    # Reuse the established v7-v9 exact-value checks against the profile that
    # the candidate's response weights actually implement. This keeps C/D/E
    # on the same population instead of accepting B and then scoring downstream
    # tables against the other interpretation.
    original_loaders = (v9.load_raw, v9.v8.load_raw, v9.v8.v7.load_raw)
    selected_loader = lambda _materials: (selected_raw, load_raw(_materials)[1])
    v9.load_raw = v9.v8.load_raw = v9.v8.v7.load_raw = selected_loader
    try:
        old = v9.evaluate(root)
    finally:
        v9.load_raw, v9.v8.load_raw, v9.v8.v7.load_raw = original_loaders
    score = Score()
    analysis_book = workbook(root / "output/engagement_analysis.xlsx")
    candidate_text = "\n".join(" | ".join(str(v) for v in row if v not in (None, ""))
                               for rows in analysis_book.values() for row in rows)
    source_facts = (HERE / "ground_truth.json").read_text(encoding="utf-8")
    semantic_owners, semantic_key = semantic_review(candidate_text, source_facts)

    # A: compact prerequisite audit.
    score.add("A1", 2, max(scaled(old, "A1", 3, 1) + scaled(old, "A2", 2, 1), 2 if sem["physical"] else 0), "physical rows, mapping and version roles")
    score.add("A2", 1, max(scaled(old, "A2", 2, 1), 1 if sem["logical"] else 0), "logical response population")
    score.add("A3", 2, max(scaled(old, "A3", 3, 1) + scaled(old, "A4", 2, 1), 2 if sem["identity"] and sem["logical"] else 0), "purpose identity, as-of fields and strict panel")

    # B: fixed-reference point and variance chain. Exact, reproducible values
    # carry more weight than prose-only evidence.
    score.add("B1", 10, (4 if sem["final_exact"] else 0) + (6 if sem["final_exact"] and sem["analysis_applies_weights"] else 0), "4 independently recomputed audit-weight points + 6 independently recomputed analysis-application points")
    score.add("B2", 4, 4 * sem["analysis_weight_diagnostics"], "analysis-owned weight-stage diagnostics recomputed from materials")
    score.add("B3", 6, max(scaled(old, "B3", 5, 6), 6 if sem["primary_exact"] and sem["final_exact"] else 0), "fixed-reference anchor trend")
    score.add("B4", 7, max(scaled(old, "B4", 7, 7), 7 if sem["replicate_exact"] and sem["final_exact"] else 0), "matched recalibrated replicates")
    score.add("B5", 3, max(scaled(old, "B5", 3, 3), 2.5 if sem["uncertainty_exact"] and sem["replicate_exact"] else 0), "replicate-centered uncertainty")
    b_start = sum(x["earned"] for x in score.items if x["item"].startswith("B"))
    b_limit = 30
    if not sem["final_exact"] and item(old, "B1") < 6.95:
        b_limit = min(b_limit, 3)
    if not sem["replicate_exact"] and item(old, "B4") < 6.8:
        b_limit = min(b_limit, 18)

    # C: a complete psychometric release chain, not isolated alpha values.
    score.add("C1", 5, 2.5 * item(old, "C1") / 4 + 2.5 * item(old, "C2") / 5, "two alphas and delete-item alphas")
    score.add("C2", 3, scaled(old, "C3", 2, 3), "corrected item-total correlations")
    score.add("C3", 4, scaled(old, "C4", 5, 4), "recalibrated reliability replicates")
    score.add("C4", 3, scaled(old, "C5", 4, 3), "alpha-change uncertainty and interpretation")
    c_limit = release_limit(2, 15, [
        (7.0 if (sem["final_exact"] or item(old, "B1") >= 6.95) else item(old, "B1"), 6.95),
        (item(old, "C1"), 3.95), (item(old, "C2"), 4.95), (item(old, "C3"), 1.95),
        (item(old, "C4"), 4.95), (item(old, "C5"), 3.95),
    ])

    # D: direct estimates earn independent credit; advanced family procedures remain gated.
    score.add("D1", 11, max(scaled(old, "D1", 5, 11), 11 if sem["org_exact"] and sem["org_se_exact"] else 7.7 if sem["org_exact"] else 0), "domain direct changes and paired-replicate SEs")
    score.add("D2", 4, scaled(old, "D2", 4, 4), "domain replicate ledger")
    score.add("D3", 6, scaled(old, "D3", 5, 6), "empirical prior and EB estimates")
    score.add("D4", 7, scaled(old, "D4", 4, 7), "empirical max-t simultaneous intervals")
    score.add("D5", 2, 2 * semantic_owners["D5"]["score"], "source-bound LLM decision interpretation")
    d_limit = release_limit(11, 30, [
        (7.0 if (sem["final_exact"] or item(old, "B1") >= 6.95) else item(old, "B1"), 6.95),
        (item(old, "D1"), 4.95), (item(old, "D2"), 3.95),
        (item(old, "D3"), 4.95), (item(old, "D4"), 3.95),
    ])

    # E: decomposition and multiplicity remain joint release dependencies.
    score.add("E1", 3, max(scaled(old, "E1", 4, 3), 2.8 if sem["panel_exact"] and sem["panel_uncertainty"] else 2.4 if sem["panel_exact"] else 0), "strict panel analytic uncertainty")
    score.add("E2", 4, scaled(old, "E2", 4, 4), "symmetric repeat/nonrepeat Kitagawa")
    score.add("E3", 1, scaled(old, "E3", 3, 1), "panel selection diagnostic")
    score.add("E4", 4, scaled(old, "E4", 3, 4), "paired-replicate BH family")
    score.add("E5", 3, 1.5 * item(old, "E5") / 3 + 1.5 * semantic_owners["E6"]["score"], "sensitivity plus source-bound LLM boundaries")
    e_limit = release_limit(3, 15, [
        (7.0 if (sem["final_exact"] or item(old, "B1") >= 6.95) else item(old, "B1"), 6.95),
        (item(old, "E2"), 3.95), (item(old, "E4"), 2.95),
    ])

    score.add("F1", 1, scaled(old, "F1", 1, 1), "two distinct workbooks")
    score.add("F2", 2, scaled(old, "F2", 2, 2), "recalculation navigation")
    score.add("F3", 2, max(scaled(old, "F3", 2, 2), 2 if sem["privacy_safe"] else 0), "privacy minimization")

    # Apply dependency release gates by reducing earned section totals.
    for prefix, observed, limit in (("B", b_start, b_limit), ("C", sum(x["earned"] for x in score.items if x["item"].startswith("C")), c_limit), ("D", sum(x["earned"] for x in score.items if x["item"].startswith("D")), d_limit), ("E", sum(x["earned"] for x in score.items if x["item"].startswith("E")), e_limit)):
        if observed > limit:
            factor = limit / observed
            for row in score.items:
                if row["item"].startswith(prefix):
                    row["earned"] = round(row["earned"] * factor, 4)
            score.total = sum(float(x["earned"]) for x in score.items)

    # Preserve only literal global caps from the underlying semantic audit.
    for cap in old.get("caps", []):
        reason = cap.get("reason", "")
        if "identity bridge misused" in reason:
            score.cap(30, "purpose-limited identity bridge misused for panel")
        elif "wrong logical response population" in reason and (not sem["logical"] or sem["inflated"]):
            score.cap(30, "wrong logical response population")

    output = root / "output"
    files = [output / n for n in ("cleaned_samples.xlsx", "engagement_analysis.xlsx")]
    present = all(x.exists() for x in files)
    distinct = present and hashlib.sha256(files[0].read_bytes()).digest() != hashlib.sha256(files[1].read_bytes()).digest()
    if not present:
        score.cap(50, "missing deliverable")
    if present and not distinct:
        score.cap(20, "two XLSX files identical")
    text = ""
    if present:
        text = ""
        for path in files:
            for rows in workbook(path).values():
                text += "\n" + "\n".join(str(v) for row in rows for v in row if isinstance(v, str))
    privacy_text = re.sub(r"(?i)\b[0-9a-f]{32,}\b", "", text)
    privacy_violation = any(
        re.search(pattern, privacy_text)
        for pattern in (
            r"(?<!\d)1[3-9]\d{9}(?!\d)",
            r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}",
            r"(?<!\d)\d{17}[\dXx](?!\d)",
        )
    )
    if privacy_violation:
        score.cap(0, "privacy disclosure")

    trend_rows = [row for row in score.items if row["item"].startswith("B")]
    trend_maximum = sum(float(row["maximum"]) for row in trend_rows)
    trend_earned = sum(float(row["earned"]) for row in trend_rows)
    calibrated_trend_ratio = trend_earned / trend_maximum if trend_maximum else 0.0
    lenient_checks = {
        "two_workbooks": present,
        "distinct_workbooks": distinct,
        "physical_export_ledger": sem["physical"],
        "logical_population": sem["logical"],
        "purpose_limited_identity": sem["identity"],
        "response_weights_present": sem["weights_present"],
        "management_action_present": semantic_owners["D5"]["score"] == 1,
        "disclosure_boundaries": semantic_owners["E6"]["score"] == 1,
        "privacy_safe": sem["privacy_safe"] and not privacy_violation,
        "calibrated_trend_quality": calibrated_trend_ratio >= CALIBRATED_TREND_FLOOR,
    }
    lenient = 1.0 if all(lenient_checks.values()) else 0.0
    final = score.final()
    strict = round(final / 100, 4)
    dimension_scores = {}
    for prefix in "ABCDEF":
        rows = [row for row in score.items if row["item"].startswith(prefix)]
        maximum = sum(float(row["maximum"]) for row in rows)
        earned = sum(float(row["earned"]) for row in rows)
        dimension_scores[prefix.lower()] = round(earned / maximum, 6) if maximum else 0.0

    return {
        "reward": strict,
        "rewards": {"strict": strict, "lenient": lenient},
        "reward_formulas": {
            "strict": "rubric points after dependency gates and global caps / 100",
            "lenient": "1 iff every delivery and privacy check passes and calibrated-trend quality is at least 0.30",
        },
        "score": round(final, 4),
        "uncapped_score": round(score.total, 4),
        "caps": score.caps,
        "section_limits": {"B": b_limit, "C": c_limit, "D": d_limit, "E": e_limit},
        "dimension_scores": dimension_scores,
        "owner_contract": owners,
        "numeric_policy": policy,
        "lenient_checks": lenient_checks,
        "lenient_quality_floor": {
            "dimension": "calibrated_trend",
            "score": round(calibrated_trend_ratio, 6),
            "floor": CALIBRATED_TREND_FLOOR,
            "independence_note": "reuses strict section B evidence; lenient is not independent of strict",
        },
        "items": score.items,
        "semantic_judge": {"cache_key": semantic_key, "owners": semantic_owners},
    }


def score_submission(submission: Path):
    if submission.is_file():
        materials = HERE.parent / "environment" / "workspace" / "materials"
        if not materials.is_dir():
            raise FileNotFoundError(f"task materials not found: {materials}")
        with tempfile.TemporaryDirectory(prefix="q12-validator-") as temp_dir:
            root = Path(temp_dir)
            os.symlink(materials, root / "materials", target_is_directory=True)
            os.symlink(submission.parent, root / "output", target_is_directory=True)
            return evaluate(root)

    root = submission
    if root.name == "output" and (root.parent / "materials").is_dir():
        root = root.parent
    return evaluate(root)


def main():
    submission = Path(sys.argv[1] if len(sys.argv) > 1 else "/workspace").resolve()
    try:
        report = score_submission(submission)
    except SemanticUnavailable as exc:
        report = {"status":"unmeasured","measurement_complete":False,
                  "error_type":type(exc).__name__,"error":str(exc),"business_zero_inferred":False}
    except Exception as exc:
        report = {
            "reward": 0.0,
            "rewards": {"strict": 0.0, "lenient": 0.0},
            "reward_formulas": {
                "strict": "rubric points after dependency gates and global caps / 100",
                "lenient": "1 iff every delivery and privacy check passes and calibrated-trend quality is at least 0.30",
            },
            "score": 0.0,
            "uncapped_score": 0.0,
            "caps": [{"maximum": 0, "reason": f"verifier error: {type(exc).__name__}: {exc}"}],
            "dimension_scores": {key: 0.0 for key in "abcdef"},
            "lenient_checks": {},
            "items": [],
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
