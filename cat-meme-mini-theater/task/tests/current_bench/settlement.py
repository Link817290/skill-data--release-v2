"""Transparent weighted settlement of independent substantive observations."""
import math

class Unmeasured(ValueError):
    pass

ROLE_AUDIO = ('boss_small_request','boss_rework','puzzled','shocked','mocking_colleague')
NATIVE = ('media_delivery','reproducible_project','truthful_plan','story','intended_cast',
          'developing_performance','readable_dialogue','required_visual_devices','audible_audio')

def integrated_delivery_v1(base,completion,policy):
    gap=number(policy['reference_gap'],'integrated reference gap')
    exponent=number(policy['gap_exponent'],'integrated gap exponent')
    owner_count=policy['owner_count']
    source_owner=policy['source_dependency_owner']
    source_power=policy['source_dependency_power']
    if not 0 < gap < 1 or not 0 < exponent < 1 or owner_count != len(completion):
        raise Unmeasured('Invalid integrated delivery contract')
    if source_owner not in completion or type(source_power) not in (int,float) or source_power <= 0:
        raise Unmeasured('Invalid source dependency contract')
    if base == 1:
        utility=1.
    else:
        integrated_base=1-gap*((1-base)/gap)**exponent
        utility=integrated_base**owner_count
    source=completion[source_owner]
    if source < 1:
        utility *= source**source_power
    return utility

def number(value, label):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise Unmeasured(label+' must be a measured number in [0,1]')
    return float(value)

def boolean(value,label):
    if type(value) is not bool:
        raise Unmeasured(label+' must be independently measured')
    return value

def settle(detail,audio,soundtrack,params):
    if detail.get('status') != 'measured' or detail.get('missing_items') or detail.get('unmeasured_weight') != 0:
        raise Unmeasured('Incomplete native measurements')
    items=detail['items']
    leaves={key:number(items[key]['completion'],key) for key in ('P01','P02','P03','P04','P05','P06','P07','P08','P09','P10','P11','P12','P13','P14','P15')}
    deduplications=[]
    for group in detail.get('positive_deduplications',[]):
        if group.get('same_operation') is not True or sorted(group.get('check_ids',[])) != ['P07.0','P07.1'] or leaves['P07'] != 0 or not group.get('evidence'):
            raise Unmeasured('Unqualified shared framing diagnostic')
        leaves['P07']=.5
        deduplications.append(group)
    # Damage reports remain evidence. Failed checks retain their own loss.
    must_have={'native_'+key:{'passed':boolean(detail['must_have'][key],key)} for key in NATIVE}
    role_values={}
    for key in ROLE_AUDIO:
        row=audio[key]
        identity=boolean(row.get('identity_preserved',row.get('identity')),key+' identity')
        beat=row.get('correct_story_beat',row.get('beat'))
        if identity:
            beat=boolean(beat,key+' narrative placement')
        expression=boolean(row.get('meaningful_original_performance'),key+' original expression') if identity and beat else False
        role_values[key]=float(identity and beat and expression)
        must_have['audio_'+key]={'passed':bool(identity and beat and expression),'evidence':row}
    if soundtrack.get('status') != 'measured':
        raise Unmeasured('Soundtrack semantics are unresolved')
    design=number(soundtrack['completion'],'soundtrack design')
    must_have['intentional_soundtrack']={'passed':all(boolean(c['passed'],'soundtrack check') for c in soundtrack['checks']),'evidence':soundtrack}
    completion={
      'N01_story_context_and_overtime':(leaves['P01']+leaves['P03']+leaves['P04'])/3,
      'N02_rework_reveal':leaves['P02'],
      'N03_cast_and_performance':leaves['P05'],
      'N04_visual_craft':sum(leaves[k] for k in ('P06','P07','P09','P13','P14','P15'))/6,
      'N05_readable_dialogue':leaves['P08'],
      'N06_encoded_delivery':leaves['P12'],
      'N07_reproducible_source_and_plan':leaves['P11'],
      'N08_role_original_audio':sum(role_values.values())/len(role_values),
      'N09_key_effects':min(leaves['P10'],design)}
    weights={k:number(v,k+' weight') for k,v in params['weights'].items()}
    if set(weights)!=set(completion) or abs(sum(weights.values())-1)>1e-10 or params['family']!='weighted-substantive':
        raise Unmeasured('Invalid substantive scoring contract')
    base=sum(weights[k]*completion[k] for k in weights)
    policy=params.get('strict_settlement_policy')
    if policy != 'integrated_delivery_v1':
        raise Unmeasured('Unsupported strict settlement policy')
    strict=round(integrated_delivery_v1(base,completion,params['integrated_delivery']),12)
    required=params['lenient_policy']['must_have']
    if not required or len(set(required))!=len(required) or not set(required)<=set(must_have):
        raise Unmeasured('Invalid independent completion contract')
    failed=[k for k in required if not must_have[k]['passed']]
    return {'status':'measured','reward':strict,'rewards':{'strict':strict,'lenient':int(not failed)},
            'completion':completion,'weighted_completion':completion,'must_have':{k:must_have[k] for k in required},
            'quality_requirements':must_have,'failed_must_have':failed,
            'settlement':{'family':'weighted-substantive','policy':policy,
                          'formula':'versioned integrated-delivery utility over the weighted professional owners',
                          'weighted_base':base,
                          'weights':weights,'positive_deduplications':deduplications,
                          'damage_observations':detail.get('settlement',{}).get('damage_instances',[])}}
