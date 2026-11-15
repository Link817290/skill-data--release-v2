"""One causal owner per source-grounded decision; independent minimum usability."""
import math
import statistics


def settle(measured, params):
    v = {key: item['completion'] for key, item in measured.items()}
    def unit(name):
        analysis = v['unit__' + name + '__analysis']
        return .5 * analysis + .25 * v['unit__' + name + '__source'] + .25 * v['unit__' + name + '__action']
    blocked = not v['chen_affirmative_correction_consistency']
    clock = not v['benefit_affirmative_execution_consistency']
    correction = 1 if blocked else v['chen_known_record_correction']
    trigger = 1 if clock else v['benefit_execution_trigger_consistency']
    stage_analysis = 1 if not v['harm_he_current_stage'] else v['he_current_stage_analysis']
    domains = {
        'zhou': {'actual_night': unit('zhou_actual_night'),
            'payroll': statistics.mean([unit('zhou_pay'), v['zhou_performance_record']]),
            'protection': unit('zhou_protection'), 'event_action': v['zhou_event_review']},
        'he': {'P03': unit('he_task_conflict'),
            'P09a': .5 * v['he_full_period_scope_analysis'] + .25 * v['he_full_period_source_binding'] + .25 * v['he_full_period_executable_action'],
            'P16': v['he_prior_reconfirmation_scope'],
            'P09c': .5 * stage_analysis + .25 * v['he_current_stage_source'] + .25 * v['he_current_evidence_action'],
            'P18': v['he_current_operational_control'], 'P11': unit('he_contract_hold')},
        'chen': {'payroll': statistics.mean([v['chen_pay_conditional_analysis'], correction, v['chen_payroll_source_bridge']]),
            'maternity_calendar_system': statistics.mean([v['chen_calendar_conditional_analysis'], unit('chen_system')]),
            'benefit_reconciliation': statistics.mean([v['chen_receipt_followup'], trigger, v['chen_final_payment_responsibility_path']]),
            'september_phase': statistics.mean([v['chen_september_phase_handoff'], v['chen_postreturn_nursing_work_time'], v['chen_postreturn_no_night_overtime']])},
        'zhao': {'actual_night': unit('zhao_actual_night'),
            'payroll': statistics.mean([unit('zhao_pay'), v['zhao_deduction_period_link']]),
            'protection': unit('zhao_protection'),
            'historical_actual_use': statistics.mean(v['zhao_' + episode + '_' + ability]
                for episode in ('may18_22', 'july14', 'aug8') for ability in ('evidence_boundary', 'retrospective_verification'))},
        'wang': {'P12': v['wang_contract_conditional_analysis'], 'P17': v['wang_nursing_schedule_correction']}}
    completion = {'zhou_current': statistics.mean(domains['zhou'].values()),
        'he_historical': domains['he']['P09a'],
        'he_current': statistics.mean(domains['he'][key] for key in ('P03', 'P16', 'P09c', 'P18', 'P11')),
        'chen_payroll': domains['chen']['payroll'],
        'chen_calendar': domains['chen']['maternity_calendar_system'],
        'chen_benefit': domains['chen']['benefit_reconciliation'],
        'chen_postreturn': domains['chen']['september_phase'],
        'zhao_current': statistics.mean(domains['zhao'][key] for key in ('actual_night', 'payroll', 'protection')),
        'zhao_historical': domains['zhao']['historical_actual_use'],
        'wang_contract': domains['wang']['P12'],
        'wang_nursing': domains['wang']['P17'],
        'delivery_controls': statistics.mean([
            v['usable_evidence_truth'], v['usable_accountable_open_controls'],
            v['delivery_cross_file_consistency'], v['delivery_reference_resolution'],
            v['delivery_timeline_integrity'], v['delivery_source_inventory'],
        ])}
    keys = {
        'chen_affirmative_correction_consistency': ('HZ220031:known_freeze_correction_blocked', 'D_BLOCKING_OPERATION'),
        'benefit_affirmative_execution_consistency': ('HZ220031:final_reconciliation_clock', 'D_BLOCKING_OPERATION'),
        'safe_chen_current_wage_execution': ('HZ220031:payroll', 'D_BLOCKING_OPERATION'),
        'he_prior_confirmation_evidence_truth': ('HZ230086:unsupported_prior_nonperformance', 'D_FACT_DETAIL'),
        'harm_chen_calendar': ('HZ220031:calendar', 'D_FACT_DETAIL'),
        'harm_wang_calendar': ('HZ240052:calendar', 'D_FACT_DETAIL'),
        'harm_he_current_stage': ('HZ230086:unsupported_current_stage', 'D_FACT_DETAIL'),
        'safe_zhou_medical_arithmetic': ('HZ240117:medical_timeline', 'D_FACT_DETAIL'),
        'safe_zhao_aug08_source_field': ('HZ230144:aug08_schedule_vs_actual', 'D_FACT_DETAIL'),
        'safe_zhou_protection_decision': ('HZ240117:night_work', 'D_BLOCKING_OPERATION'),
        'safe_zhou_payroll_decision': ('HZ240117:payroll', 'D_BLOCKING_OPERATION'),
        'safe_zhao_protection_decision': ('HZ230144:night_work_and_nursing', 'D_BLOCKING_OPERATION'),
        'safe_zhao_payroll_decision': ('HZ230144:payroll', 'D_BLOCKING_OPERATION'),
        'safe_chen_leave_decision': ('HZ220031:leave_protection', 'D_BLOCKING_OPERATION'),
        'safe_he_operational_decision': ('HZ230086:work_adjustment', 'D_BLOCKING_OPERATION'),
        'safe_he_contract_decision': ('HZ230086:contract', 'D_BLOCKING_OPERATION'),
        'safe_wang_contract_decision': ('HZ240052:contract', 'D_BLOCKING_OPERATION')}
    events = [{'damage_key': key, 'tier': tier, 'predicate': ident} for ident, (key, tier) in keys.items() if v[ident] == 0]
    assert len({event['damage_key'] for event in events}) == len(events)
    weights = params['fixed_weights']
    assert set(completion) == set(weights) and abs(math.fsum(weights.values()) - 1) < 1e-12
    raw = math.fsum(weights[key] * completion[key] for key in weights)
    debit = math.fsum(params['penalties'][event['tier']] for event in events)
    final = max(0.0, raw - debit)
    must = {key: v[key] for key in v if key.startswith('usable_')}
    return {'completion': completion, 'case_abilities': domains, 'raw_quality_B': raw,
        'positive_utility': raw, 'independent_damage': debit, 'damage_events': events,
        'reward_strict': final, 'reward_lenient': int(all(must.values())), 'must_haves': must,
        'formula': 'R=max(0,B-sum(unique event debit))',
        'parameters': params, 'same_cause_ownership': {'known_record_correction': 'Only the known-state correction atom is conditional when its affirmative erroneous prerequisite is owned by D.',
            'final_clock': 'Only adopted trigger consistency is conditional when its affirmative conflict is owned by D.',
            'current_stage': 'Only current-stage analysis correctness is conditional under its affirmative-certainty detail owner; actual source binding and missing clinical inquiry retain their measured values.',
            'prior_truth': 'Independent omitted original historical inquiry retains its measured partial; an added false assertion cannot fill that work.'}}
