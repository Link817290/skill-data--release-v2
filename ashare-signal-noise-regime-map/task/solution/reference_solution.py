#!/usr/bin/env python3
"""Hidden reference solution: independent-evidence-cluster oracle."""
from __future__ import annotations

import csv
import argparse
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TASK = HERE.parents[0]
TESTS = next((path for path in (HERE, TASK / "tests", Path("/tests"))
              if (path / "workbook.py").is_file()), TASK / "tests")
sys.path.insert(0, str(TESTS))
import workbook  # noqa: E402


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def quantile(values: list[float], p: float) -> float:
    v = sorted(values)
    i = (len(v) - 1) * p
    lo = int(i)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (i - lo)

def oracle_thresholds(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Sample-relative cut points for the hidden oracle.

    Every cut is a quantile of the frozen panel itself, so a disciplined agent that
    calibrates against the same panel can approach them without seeing this file.
    """
    def q(key: str, p: float) -> float:
        return quantile([float(r[key]) for r in rows], p)
    return {
        'trend_ret_hi': q('hs300_63d_return', 0.60), 'trend_ret_lo': q('hs300_63d_return', 0.40),
        'recent_lo': q('hs300_21d_return', 0.28), 'recent_hi': q('hs300_21d_return', 0.62),
        'breadth_hi': q('industry_breadth_proxy', 0.58), 'breadth_lo': q('industry_breadth_proxy', 0.42),
        'earn_hi': q('earnings_cycle_proxy', 0.64), 'earn_lo': q('earnings_cycle_proxy', 0.36),
        'drawdown': q('hs300_drawdown_252d', 0.45), 'valq_lo': q('valuation_percentile_proxy', 0.45),
        'valq_hi': q('valuation_percentile_proxy', 0.72), 'valq_mid': q('valuation_percentile_proxy', 0.60),
        'erp_lo': q('erp_proxy', 0.30), 'erp_hi': q('erp_proxy', 0.68), 'erp_tight': q('erp_proxy', 0.50),
        'liq_hi': q('liquidity_turnover_proxy', 0.74), 'liq_lo': q('liquidity_turnover_proxy', 0.26),
        # 事件簇记的是"极端"，取高分位。原先取 0.45 会让过半窗口都记为冲击，
        # 与簇的语义不符，也与方法要求的"极端事件取高分位"相反。
        'vol_shock': q('hs300_volatility_21d_ann', 0.85),
        # 这三条原为绝对常数，与"切线取自面板自身分位数"的要求冲突。改为等价分位：
        # 0.10≈52 分位、1.6≈81 分位、0.055≈74 分位（按 |style|），行为不变。
        'credit_easing': q('credit_easing_proxy', 0.52),
        'noise_hi': q('noise_event_intensity', 0.81),
        'style_div': quantile([abs(float(r['style_momentum_growth_vs_large'])) for r in rows], 0.74),
    }

def classify_reference(rows: list[dict[str, Any]], event_rows: list[dict[str, Any]], thresholds=None) -> list[dict[str, Any]]:
    """Independent-evidence-cluster oracle.

    Eight raw dimensions collapse into four mutually independent clusters. The trend
    cluster absorbs price / breadth / earnings because those three proxies are near
    collinear by construction (corr > 0.94 against the underlying index returns), so
    counting them separately would fake cross-dimensional confirmation.
    """
    by_sample_events: dict[str, list[dict[str, Any]]] = {}
    for e in event_rows:
        by_sample_events.setdefault(e['sample_id'], []).append(e)

    T = oracle_thresholds(rows) if thresholds is None else thresholds
    raw: list[dict[str, Any]] = []
    for r in rows:
        sid = r['sample_id']
        ret = float(r['hs300_21d_return'])
        ret63 = float(r['hs300_63d_return'])
        dd = float(r['hs300_drawdown_252d'])
        valq = float(r['valuation_percentile_proxy'])
        erp = float(r['erp_proxy'])
        liq = float(r['liquidity_turnover_proxy'])
        credit = float(r['credit_easing_proxy'])
        earn = float(r['earnings_cycle_proxy'])
        breadth = float(r['industry_breadth_proxy'])
        style = float(r['style_momentum_growth_vs_large'])
        pol = int(float(r['policy_event_intensity']))
        noise = float(r['noise_event_intensity'])
        vol = float(r['hs300_volatility_21d_ann'])

        anchors: list[str] = []

        def add(cond: bool, eid: str) -> bool:
            if cond:
                anchors.append(eid)
            return cond

        # --- Trend cluster: collinear proxies vote once. ---
        trend_vote = 0
        if add(ret63 > T['trend_ret_hi'] and ret > T['recent_lo'], 'E_PRICE_PERSISTENCE'):
            trend_vote += 1
        elif add(ret63 < T['trend_ret_lo'] and ret < T['recent_hi'], 'E_PRICE_PERSISTENCE'):
            trend_vote -= 1
        if add(breadth > T['breadth_hi'], 'E_BREADTH_CONFIRM'):
            trend_vote += 1
        elif add(breadth < T['breadth_lo'], 'E_BREADTH_NARROW'):
            trend_vote -= 1
        if add(earn > T['earn_hi'], 'E_EARNINGS_PULSE'):
            trend_vote += 1
        elif add(earn < T['earn_lo'], 'E_EARNINGS_PULSE'):
            trend_vote -= 1
        trend_dir = 1 if trend_vote >= 2 else (-1 if trend_vote <= -2 else 0)

        # --- Odds cluster: valuation / drawdown / equity risk premium. ---
        odds_vote = 0
        if add(dd < T['drawdown'] and valq < T['valq_lo'], 'E_BOTTOM_ODDS'):
            odds_vote += 1
        if add(valq > T['valq_hi'] and erp < T['erp_lo'], 'E_VALUATION_STRETCHED'):
            odds_vote -= 1
        if add(erp > T['erp_hi'] and valq < T['valq_mid'], 'E_EQUITY_RISK_PREMIUM'):
            odds_vote += 1
        odds_dir = 1 if odds_vote > 0 else (-1 if odds_vote < 0 else 0)

        # --- Funding cluster: liquidity and credit. ---
        fund_vote = 0
        if add(liq > T['liq_hi'], 'E_LIQUIDITY_CONFIRM'):
            fund_vote += 1
        elif add(liq < T['liq_lo'] and ret < 0, 'E_LIQUIDITY_WITHDRAW'):
            fund_vote -= 1
        if add(credit > T['credit_easing'], 'E_CREDIT_EASING'):
            fund_vote += 1
        elif add(credit <= 0.0 and erp < T['erp_tight'], 'E_CREDIT_TIGHTENING'):
            fund_vote -= 1
        fund_dir = 1 if fund_vote > 0 else (-1 if fund_vote < 0 else 0)

        # --- Event cluster: magnitude only, no direction. ---
        event_load = 0
        if add(pol >= 4, 'E_POLICY_SUPPORT'):
            event_load += 1
        if add(noise >= T['noise_hi'], 'E_EVENT_NOISE'):
            event_load += 1
        if add(vol > T['vol_shock'], 'E_VOLATILITY_SHOCK'):
            event_load += 1

        add(abs(style) > T['style_div'], 'E_STYLE_DIVERGENCE')
        anchors = list(dict.fromkeys(anchors))

        directed = [d for d in (trend_dir, odds_dir, fund_dir) if d != 0]
        positive = sum(1 for d in directed if d > 0)
        negative = sum(1 for d in directed if d < 0)
        contradiction = positive > 0 and negative > 0

        if event_load >= 1 and trend_dir == 0:
            label = 'NOISE'
        elif len(directed) < 2:
            label = 'REVIEW'
        elif contradiction:
            label = 'MIXED'
        else:
            label = 'SIGNAL'

        # Action depends on the FINAL label, which regime persistence may change, so
        # resolve the mapping for every label up front using this window's evidence.
        if 'E_STYLE_DIVERGENCE' in anchors:
            mixed_action = 'ROTATE_STYLE'
        elif 'E_BREADTH_CONFIRM' in anchors or 'E_BREADTH_NARROW' in anchors:
            mixed_action = 'ROTATE_INDUSTRY'
        else:
            mixed_action = 'HOLD'
        if positive >= negative:
            if 'E_STYLE_DIVERGENCE' in anchors and style > 0 and valq > T['valq_mid']:
                signal_action = 'ROTATE_STYLE'
            elif 'E_POLICY_SUPPORT' in anchors and breadth < T['breadth_hi']:
                signal_action = 'ROTATE_INDUSTRY'
            else:
                signal_action = 'ADD_RISK'
        else:
            signal_action = 'REDUCE_RISK'
        action_by_label = {
            'REVIEW': 'REVIEW_ONLY',
            'NOISE': 'REDUCE_RISK' if ret < T['recent_lo'] else 'HOLD',
            'MIXED': mixed_action,
            'SIGNAL': signal_action,
        }

        raw.append({
            'sample_id': sid,
            'raw_label': label,
            'action_by_label': action_by_label,
            'anchors': list(dict.fromkeys(anchors)),
            'event_ids': [e['event_id'] for e in by_sample_events.get(sid, [])],
            'contradiction_flag': 'TRUE' if contradiction else 'FALSE',
            'trend_dir': trend_dir,
            'odds_dir': odds_dir,
            'fund_dir': fund_dir,
            'event_load': event_load,
        })

    return _apply_regime_persistence(raw)


def _apply_regime_persistence(raw):
    """惯性层 + 换手约束，按 skill 的两遍写法。"""
    out = []
    prev_raw = None
    prev_final = None
    prev_action = None
    prev_anchors = None
    for rec in raw:
        rr = rec['raw_label']
        if prev_final is None:
            final = rr
        elif rr == prev_final:
            final = rr
        elif rr == prev_raw:
            final = rr                      # 连续两窗口一致，确认切换
        else:
            supported = True
            if prev_final == 'NOISE':
                supported = rec['event_load'] > 0
            elif prev_final == 'SIGNAL':
                dirs = [rec['trend_dir'], rec['odds_dir'], rec['fund_dir']]
                supported = sum(1 for d in dirs if d) >= 2
            elif prev_final in ('MIXED', 'REVIEW'):
                # Historical conflict/uncertainty persists until two raw readings confirm resolution.
                supported = True
            final = prev_final if supported else rr
        action = rec['action_by_label'].get(final) if isinstance(rec['action_by_label'], dict) else rec['action_by_label']
        if action in ('ADD_RISK', 'REDUCE_RISK') and prev_action is not None:
            opposite = 'REDUCE_RISK' if action == 'ADD_RISK' else 'ADD_RISK'
            if prev_action in (action, opposite, 'REVIEW_ONLY'):
                action = 'HOLD'
        cur = list(dict.fromkeys(rec['anchors']))
        if prev_anchors is None:
            change = cur                      # 首窗口没有前一窗，带完整锚点集
        else:
            added = [a for a in cur if a not in prev_anchors]
            gone = [a for a in prev_anchors if a not in cur]
            change = added + gone
            if not change:
                change = cur                  # 相邻两窗相同则回落到完整集
        out.append({**rec, 'regime_label': final, 'action': action,
                    'evidence_ids': change + rec['event_ids'],
                    'review_flag': 'TRUE' if final == 'REVIEW' else 'FALSE'})
        prev_raw, prev_final, prev_action, prev_anchors = rr, final, action, cur
    return out

def main():
    parser = argparse.ArgumentParser()
    default_workspace = Path('/workspace') if (Path('/workspace') / 'market_snapshots.csv').is_file() else TASK / 'environment' / 'workspace'
    parser.add_argument('--workspace', type=Path, default=default_workspace)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    rows = read_csv(args.workspace / 'market_snapshots.csv')
    events = read_csv(args.workspace / 'events.csv')
    out = []
    for rec in classify_reference(rows, events):
        out.append({
            'sample_id': rec['sample_id'],
            'regime_label': rec['regime_label'],
            'action': rec['action'],
            'evidence_ids': '|'.join(rec['evidence_ids']),
            'contradiction_flag': rec['contradiction_flag'],
            'review_flag': rec['review_flag'],
            'rationale': '基于冻结指标的独立证据簇综合判定。',
        })
    dest = args.output if args.output is not None else args.workspace / 'regime_map.xlsx'
    workbook.write_workbook(dest, out, {'generated_by': 'hidden reference solution', 'samples': len(out)})
    print(dest)


if __name__ == '__main__':
    main()
