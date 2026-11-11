"""Small, inspectable relation recognizers; no workbook formulas are executed.

The arithmetic recognizer accepts equivalent ratios using a bounded AST and exact
rational arithmetic. It never evaluates Python or reads external files.
"""
import ast
from fractions import Fraction
import re


def sentences(text):
    return re.split(r'\n|(?<=[.!?;])\s+(?=[A-Za-z])', text)


def polynomial_add(a,b):
    out=dict(a)
    for term,value in b.items(): out[term]=out.get(term,Fraction(0))+value
    return {k:v for k,v in out.items() if v}


def polynomial_multiply(a,b):
    out={}
    for x,left in a.items():
        for y,right in b.items():
            term=tuple(sorted(x+y))
            if len(term)>12: raise ValueError('Polynomial degree bound')
            out[term]=out.get(term,Fraction(0))+left*right
    if len(out)>200: raise ValueError('Polynomial term bound')
    return {k:v for k,v in out.items() if v}


class RationalExpression:
    def __init__(self,numerator,denominator=None):
        self.n=numerator if isinstance(numerator,dict) else {():Fraction(str(numerator))}
        self.d={():Fraction(1)} if denominator is None else denominator
        if not self.d: raise ZeroDivisionError()
    @staticmethod
    def coerce(other):
        return other if isinstance(other,RationalExpression) else RationalExpression(other)
    def __add__(self,other):
        other=self.coerce(other)
        return RationalExpression(polynomial_add(polynomial_multiply(self.n,other.d),polynomial_multiply(other.n,self.d)),polynomial_multiply(self.d,other.d))
    def __sub__(self,other): return self+(-1*self.coerce(other))
    def __mul__(self,other):
        other=self.coerce(other)
        return RationalExpression(polynomial_multiply(self.n,other.n),polynomial_multiply(self.d,other.d))
    __rmul__=__mul__
    def __truediv__(self,other):
        other=self.coerce(other)
        return RationalExpression(polynomial_multiply(self.n,other.d),polynomial_multiply(self.d,other.n))
    def equivalent(self,other):
        other=self.coerce(other)
        return polynomial_multiply(self.n,other.d)==polynomial_multiply(other.n,self.d)


ATOMS = [
    (r'(?:number of |count of )?(?:all |total (?:number of )?)?(?:attempted commands|command attempts|attempts|commands attempted|utterances)', 't'),
    (r'(?:number of |count of )?(?:(?:correctly|successfully) (?:recognized|transcribed) (?:commands|attempts|utterances)|correct (?:intents|recognitions|transcriptions))', 'r'),
    (r'(?:number of |count of )?(?:(?:correctly|successfully) (?:executed|performed) (?:commands|attempts|actions)|correct actions)', 'a'),
    (r'(?:quiet|baseline|clean) (?:success |recognition )?(?:rate|accuracy|score)', 'q'),
    (r'(?:noise|noisy|perturbed) (?:success |recognition )?(?:rate|accuracy|score)', 'n'),
    (r'(?:number of |count of )?(?:reference|total reference) words', 'w'),
    (r'substitutions?', 's'), (r'deletions?', 'd'), (r'insertions?', 'i'),
]


def expression(text):
    text=text.lower().strip()
    # Protect multiword numerator atoms before the generic attempts atom.
    for pattern,atom in ATOMS[1:]:
        text=re.sub(r'\b'+pattern+r'\b',atom,text)
    pattern,atom=ATOMS[0]
    text=re.sub(r'\b'+pattern+r'\b',atom,text)
    text=re.sub(r'\b(?:divided by|over|out of)\b','/',text)
    text=re.sub(r'\bminus\b','-',text)
    text=re.sub(r'\bplus\b','+',text)
    text=re.sub(r'\b(?:times|multiplied by)\b','*',text)
    text=text.replace('×','*').replace('÷','/').replace('−','-')
    text=re.sub(r'\s*(?:;|\.(?:\s|$)|,\s*(?:where|with|if)|\s+where\b|\s+if\b|\s+and\s+\w+(?:\s+\w+){0,2}\s*(?:\(\s*%\s*\))?\s*=).*','',text)
    return text.strip().rstrip('.,')


def arithmetic_status(text, wanted, variables, percent=True):
    try:
        tree=ast.parse(expression(text),mode='eval').body
        if sum(1 for _ in ast.walk(tree))>60:
            return False
        names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
        if not names <= set('ratqnsdiw'):
            return None
        if names != set(variables):
            return False
        def calculate(node,values):
            if isinstance(node,ast.Name): return values[node.id]
            if isinstance(node,ast.Constant) and type(node.value) in (int,float):
                return RationalExpression(node.value)
            if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
                return calculate(node.operand,values)*(1 if isinstance(node.op,ast.UAdd) else -1)
            if isinstance(node,ast.BinOp):
                left,right=calculate(node.left,values),calculate(node.right,values)
                if isinstance(node.op,ast.Add): return left+right
                if isinstance(node.op,ast.Sub): return left-right
                if isinstance(node.op,ast.Mult): return left*right
                if isinstance(node.op,ast.Div): return left/right
            raise ValueError('Unsupported arithmetic')
        values={key:RationalExpression({(key,):Fraction(1)}) for key in 'ratqnsdiw'}
        actual=calculate(tree,values)
        expected=wanted(values)
        return any(actual.equivalent(scale*expected) for scale in ([1,100] if percent else [1]))
    except (SyntaxError,ValueError,KeyError,ZeroDivisionError,OverflowError,TypeError):
        return None


def arithmetic_equal(text,wanted,variables,percent=True):
    return arithmetic_status(text,wanted,variables,percent) is True


def wrong_metric_formula(text,label,wanted,variables):
    """Unsupported natural language is not evidence of a reversed equation."""
    for _,m in adopted_relation(label+r'\s*(?:\(\s*%\s*\))?\s*(?:=|:|is defined as|is|equals|calculated as)\s*([^;\n]+)',text):
        if arithmetic_status(m.group(1),wanted,variables) is False:return True
    return False


def metric(text,label,wanted,variables):
    results=[]
    for _,m in adopted_relation(label+r'\s*(?:\(\s*%\s*\))?\s*(?:=|:|is defined as|is|equals|calculated as|,\s*(?:compute|calculate))\s*([^;\n]+)',text):
        candidate=expression(m.group(1))
        # Copulas also introduce cautions such as "WER is not command success"
        # and "relative loss is undefined"; those are not rival formulas.
        prefix=m.group(0)[:m.start(1)-m.start()]
        if re.fullmatch(r'[ratqnsdiw0-9.\s+*/()\-]+',candidate) or '=' in prefix:
            results.append(arithmetic_equal(m.group(1),wanted,variables))
    if results: return all(results)
    # A ratio written without an equals sign still specifies its direction.
    for _,m in adopted_relation(r'(?:compute|calculate|report|define)\s+.+?\s+(?:as|using)\s+(.+)',text):
        if re.search(label,m.group(0),re.I) and arithmetic_equal(m.group(1),wanted,variables):return True
    return False


def change_loss_distinction(text):
    """Recognize the public metric distinction without requiring redundant math.

    A named percentage-point change is a standard difference of the reported
    rates. Explicit change equations can use either sign convention; an explicit
    drop/loss equation retains quiet-minus-noise direction. Adopted incorrect
    equations cannot be rescued by a qualitative metric label.
    """
    relative=r'relative (?:loss|drop)'
    wanted=lambda v:(v['q']-v['n'])/v['q']
    if wrong_metric_formula(text,relative,wanted,'qn') or not metric(text,relative,wanted,'qn'):return False
    label=r'(?:percentage[ -]point|absolute) (?:drop|change|loss|difference)'
    definitions=[]
    for _,m in adopted_relation(label+r'\s*(?:\(\s*%\s*\))?\s*(?:=|:|is defined as|is|equals|calculated as)\s*([^;\n]+)',text):
        candidate=expression(m.group(1))
        prefix=m.group(0)[:m.start(1)-m.start()]
        if not re.fullmatch(r'[qn0-9.\s+*/()\-]+',candidate) and not re.search(r'=|:|equals|defined as|calculated as',prefix,re.I):continue
        positive=arithmetic_equal(m.group(1),lambda v:v['q']-v['n'],'qn')
        signed=bool(re.search(r'\b(?:change|difference)\b',prefix,re.I)) and arithmetic_equal(m.group(1),lambda v:v['n']-v['q'],'qn')
        definitions.append(positive or signed)
    if definitions:return all(definitions)
    return any(re.search(r'\b(?:compute|calculate|report|record|compare|distinguish)\b',clause,re.I) for clause,_ in adopted_relation(label,text))


def semantic_check(key,text,steps=None):
    if steps is not None and key in ['bt-absent','before-manual-pair','cec-isolation','acoustic-level']:
        text=steps
    if key=='two-rates':
        return (metric(text,r'(?:recognition|transcription) (?:accuracy|success rate|rate)',lambda v:v['r']/v['t'],'rt')
                and metric(text,r'(?:action|execution) (?:accuracy|success rate|rate)',lambda v:v['a']/v['t'],'at'))
    if key=='wer-distinction':
        return metric(text,r'(?:wer|word error rate)',lambda v:(v['s']+v['d']+v['i'])/v['w'],'sdiw')
    if key=='drop-definition':
        return change_loss_distinction(text)
    if key=='bt-absent':
        if re.search(r'\b(?:BT|Bluetooth)\b.{0,30}(?:not unavailable|remains? connected|kept connected)|\bkeep\b.{0,20}\b(?:BT|Bluetooth)\b.{0,20}\bconnected\b',text,re.I):return False
        explicit=any(re.search(r'\b(?:verify|confirm|establish|check)\b.{0,90}\b(?:BT|Bluetooth)\b.{0,75}\b(?:unavailable|disconnected|off|disabled)\b',s,re.I) for s in sentences(text))
        # Moving until the already active pointer stops is an observed loss,
        # unlike merely moving to a distance presumed to disconnect the link.
        observed_loss=bool(re.search(r'\bpointer\b.{0,35}\bactive\b',text,re.I) and re.search(r'\b(?:move|walk)\b.{0,40}\bbeyond\b.{0,30}\b(?:BT|Bluetooth)\b.{0,15}\brange\b.{0,35}\buntil\b.{0,25}\b(?:it|pointer)\b.{0,15}\b(?:stops|ceases|disappears)\b',text,re.I))
        return explicit or observed_loss
    if key=='before-manual-pair':
        power=bool(re.search(r'power.cycle|interrupt power|restore power|remove.{0,30}(?:batter|cells)|disconnect.{0,25}power',text,re.I))
        prior=bool(re.search(r'before (?:pressing|holding|performing|initiating|starting|attempting).{0,35}(?:OK|wheel|manual|re.pair).{0,50}(?:test|check|verify|observe).{0,80}binding|(?:test|check|verify|observe).{0,70}binding.{0,65}before.{0,40}(?:manual|re.pair|pressing)|without.{0,30}(?:manual|re.pair).{0,60}(?:test|check|verify).{0,50}binding',text,re.I))
        return power and prior
    if key=='cec-isolation':
        if re.search(r'(?:keep|leave).{0,25}(?:CEC|SimpLink).{0,25}enabled|(?:CEC|SimpLink).{0,30}(?:must|should|is).{0,10}not.{0,15}disabled|(?:while|with).{0,25}(?:CEC|SimpLink).{0,25}enabled',text,re.I):return False
        return bool(re.search(r'\bdisable\b.{0,30}(?:CEC|SimpLink)|(?:CEC|SimpLink)(?:[, /\w-]{0,100})(?:disabled|off)',text,re.I))
    if key=='acoustic-level':
        if re.search(r'(?:by|use|using).{0,25}(?:re.labell|volume percentage).{0,70}(?:dB|SPL|directly)|instead of measuring acoustic.{0,50}use.{0,30}volume percentage',text,re.I):return False
        return bool(re.search(r'sound.level meter|SPL meter|acoustic meter|calibrated.{0,30}(?:meter|microphone)|measure.{0,60}(?:dB|SPL)',text,re.I))
    if key=='unlearned-baseline':
        if re.search(r'(?:target|external) (?:device )?(?:is |was |has been )?(?:powered|switched|turned) off.{0,100}(?:unlearned|baseline|key)|baseline.{0,60}(?:target|external).{0,35}(?:powered|switched|turned) off',text,re.I):
            return False
        for sentence in sentences(text):
            if re.search(r'unlearned|before learning|pre.learn',sentence,re.I):
                if re.search(r'(?:already|still|does|can) controls? (?:that|the|this)?\s*target',sentence,re.I):
                    return False
        return any(re.search(r'unlearned|before learning|pre.learn',s,re.I) and
                   re.search(r'(?:does not|cannot|must not|should not) (?:control|operate|respond)|no (?:response|reaction|effect)|(?:fails? to|unable to) control|(?:key|button).{0,25}(?:does not|cannot|must not|should not).{0,20}(?:control|operate)',s,re.I)
                   for s in sentences(text))
    if key=='matched-corpus':
        distances={}
        for m in re.finditer(r'(?=\b(quiet|noise|noisy)\b([^;.!?\n]{0,150}))',text,re.I):
            span=re.split(r'\b(?:quiet|noise|noisy)\b',m.group(2),maxsplit=1,flags=re.I)[0]
            if re.search(r'\b(?:speaking|speaker|distance|geometry)\b',span,re.I):
                values=re.findall(r'\b(\d+(?:\.\d+)?)\s*(mm|cm|m|degrees?)\b',span,re.I)
                for amount,unit in values:
                    kind='angle' if unit.lower().startswith('degree') else 'distance'
                    value=float(amount)*{'mm':.001,'cm':.01,'m':1}.get(unit.lower(),1)
                    distances.setdefault(kind,{}).setdefault('quiet' if m.group(1).lower()=='quiet' else 'noise',set()).add(value)
        if any('quiet' in v and 'noise' in v and v['quiet']!=v['noise'] for v in distances.values()): return False
        relevant=[s for s in sentences(text) if re.search(r'quiet|reference|baseline|conditions',s,re.I) and re.search(r'nois|conditions',s,re.I)]
        if any(re.search(r'(?:different|change|vary).{0,45}(?:corpus|corpora|command|geometry)',s,re.I) for s in relevant):
            return False
        direct=any(re.search(r'\b(?:run|test|compare|repeat|use|present|keep|hold)\b',s,re.I) and
                   re.search(r'(?:same|matched|identical|unchanged).{0,45}(?:corpus|corpora|command|test set)|(?:corpus|corpora|command|test set).{0,40}(?:unchanged|identical|constant|matched)',s,re.I)
                   for s in relevant)
        # A declared reference followed by identical repeated noise trials is an
        # explicit paired comparison even when the control list is a new sentence.
        distributed=bool(re.search(r'quiet|reference|baseline',text,re.I) and re.search(r'noise|noisy',text,re.I) and re.search(r'(?:same|identical|matched).{0,40}(?:corpus|utterance|command|test set)|(?:utterance|corpus|command).{0,35}(?:fixed|constant|identical)',text,re.I))
        return direct or distributed
    if key=='local-cloud':
        return bool(re.search(r'(?:local|cloud|network.dependent).{0,180}(?:latency|response limit|action endpoint|response time)|(?:latency|action endpoint).{0,180}(?:local|cloud|network.dependent)',text,re.I)) and bool(re.search(r'\b(?:local)\b',text,re.I) and re.search(r'cloud|network.dependent',text,re.I))
    if key=='bt-route':
        # Isolation needs actual obstruction, not a photograph taken without it.
        for s in sentences(text):
            cleaned=re.sub(r'\bwithout\b.{0,40}\b(?:block(?:ing|ed)?|occlud(?:ing|ed)?)\b.{0,35}\b(?:IR|infrared)\b[^,;]*','',s,flags=re.I)
            if re.search(r'\b(?:block|occlude|cover|disable)\b.{0,30}\b(?:IR|infrared)\b|\b(?:IR|infrared)\b.{0,30}\b(?:blocked|occluded|covered|disabled)\b',cleaned,re.I):
                return True
        return False
    return True


def affirmative(sentence,match):
    """Reject negation of this proposition, without hiding other affirmative clauses."""
    before=sentence[max(0,match.start()-65):match.start()]
    # Coordinated clauses can have independent polarity.
    before=re.split(r'\band\b|\bbut\b|[,;]',before,flags=re.I)[-1]
    fragment=match.group(0)
    after=sentence[match.end():]
    if re.search(r'^.{0,50}\b(?:is|are|remains?)\s+(?:unsupported|unsubstantiated|unproven|invalid|not established|not supported)\b',after,re.I): return False
    if re.search(r'\b(?:not|never|no|cannot|can\x27t|isn\x27t|aren\x27t|doesn\x27t)\b[^,;:]{0,45}$',before,re.I):
        return False
    if re.search(r'\b(?:not|never|cannot|can\x27t|isn\x27t|aren\x27t|doesn\x27t)\b',fragment,re.I):
        return False
    return True


def remote_power_action(steps,conditions=''):
    """An actual remote-supply operation; construction labels are not actions."""
    for clause in relation_clauses(steps):
        explicit=r'\b(?:power[ -]cycle(?:/reboot)?|power off|interrupt(?:ion)?(?: of)?(?: the)? power(?: supply)?(?: to)?)\s+(?:(?:the|approved|confirmed|actual)\s+){0,3}(?:DUT|remote)\b|\b(?:DUT|remote)(?:[ -]only|[ -]side)?\s+(?:(?:approved|actual|confirmed)\s+)?(?:power[ -]cycle|power interruption|power removal|power restoration)\b|\b(?:remove|refit|reinsert|replace)\b[^.;:]{0,25}\b(?:cells|batteries)\b|remove (?:the )?power source from (?:the )?remote'
        if list(adopted_relation(explicit,clause)):return True
        implicit=bool(re.search(r'\bpower[ -]cycle\b.{0,35}\b(?:its |the )?approved method\b',clause,re.I))
        if implicit and re.search(r'learning.memory variant|stored code|stored command',clause,re.I) and not re.search(r'\b(?:host|TV)\b',clause,re.I):return True
        if re.search(r'apply.{0,25}power.interrupt step.{0,50}confirmed hardware branch',clause,re.I) and re.search(r'DUT|remote|pointer|pairing',steps+' '+conditions,re.I):return True
        if re.search(r'\binterrupt device power\b|\brestore device power\b',clause,re.I) and re.search(r'\bremote\b',steps,re.I) and not re.search(r'\b(?:host|TV)\b',clause,re.I):return True
        if re.search(r'\bestablish (?:the )?(?:documented |approved )?power.off condition\b',clause,re.I) and re.search(r'\bremote\b',steps+' '+conditions,re.I) and not re.search(r'\b(?:host|TV)\b',clause,re.I):return True
        if re.search(r'remove (?:the )?power source by.{0,25}branch.appropriate method',clause,re.I) and re.search(r'remove cells.{0,30}replaceable branch|replaceable branch.{0,30}remove cells',conditions,re.I) and re.search(r'fit cells|reconnect power',steps,re.I):return True
    return False


def business_evidence(key,cases):
    """Recognize a complete business relation in its operative case roles.

    No product threshold, case ID, sheet name, model condition or artifact hash
    selects credit. Common setup supplies conditions, never missing actions.
    Every component returns its actual native-role and setup locators.
    """
    if key in NEW_BUSINESS_LEAVES:
        return new_business_evidence(key,cases)
    def found(pattern,text): return re.search(pattern,text,re.I)
    def all_of(text,*patterns): return all(found(p,text) for p in patterns)
    def any_of(text,*patterns): return any(found(p,text) for p in patterns)
    def data(case):
        v=case['business_text']
        t,p,o,a,r,m=(v[x] for x in ['steps','preconditions','expected','acceptance','remarks','metrics'])
        return t,p,o,a,r,m,' '.join([t,p,o,a,r])
    def result(case,component=None):
        loc=[case['locators'][r] for r in ['steps','preconditions','expected','acceptance','remarks'] if case['fields'].get(r)]
        if key=='risk-priority' and case['fields'].get('priority'):
            loc.append(case['locators']['priority'])
        loc+=case.get('shared_setup_locators',[])
        if key in ['two-rates','wer-distinction','attempt-ledger']:loc+=case.get('metric_locators',[])
        return {'case_key':case['case_key'],'component':component or key,
            'clauses':[{'locators':list(dict.fromkeys(loc)),'matched_relations':[key],
                'predicate':'role-bound-business-relation-v5'}]}
    def local(case,check):
        t,p,o,a,r,m,b=data(case)
        lp=case['business_text'].get('resolved_preconditions',case['business_text'].get('local_preconditions',''))
        outcome=o+' '+a
        voice=bool(found(r'\b(?:utterance|speak|voice|microphone|mic|recogniz|recognition|transcript|ai button)',t) or (found(r'commands?',t) and found(r'\b(?:microphone|mic)\b',lp)) or (all_of(t,r'\b(?:press|hold|release|actuate)\b.{0,30}\bAI\b',r'listening|waveform|speech|speak')))
        related=[c for c in cases if str(c['case_key']).upper() in case.get('related_case_keys',[])]
        remote_power=remote_power_action(t,lp)
        sealed_context=t+' '+r+' '+lp
        false_sealed_cycle=bool(list(adopted_relation(r'(?:disconnect|unplug).{0,50}(?:charg|USB)',t+' '+lp))) and found(r'sealed|non.removable|built.in|branch s',sealed_context)
        false_sealed_cycle=false_sealed_cycle or all_of(t,r'rechargeable.{0,80}(?:means|disconnect)',r'(?:disconnect).{0,30}(?:the )?supply')
        false_sealed_cycle=false_sealed_cycle and not found(r'approved.{0,50}(?:shutdown|service|power.off)|charger alone does not interrupt|not equate.{0,40}charger.{0,50}interrupt|disconnecting a charger.{0,80}does not interrupt',t+' '+r)
        if check=='power-branch':
            return all_of(p+' '+r+' '+a+' '+t,r'(?:actual|physical|inspect|label|identif|confirm|observed).{0,90}(?:power|construction|batter|variant|hardware)',r'(?:USB.?C|sealed|AAA|labeled battery|labelled battery|correct power source|power architecture)') and any_of(p+' '+a+' '+r+' '+t,r'before|until|only|approved|confirmed|correct|label')
        if check=='host-distinction':
            s=p+' '+a+' '+r
            explicit=all_of(s,r'\b(?:host|TV|display)\b',r'(?:does not|do not|not infer|not establish|not prove|not a remote|rather than|only to qualify|not automatically|not identify).{0,140}(?:DUT|remote|accessory|microphone|compatib)|(?:DUT|remote).{0,100}(?:separate|distinct|not inferred)')
            labelled=all_of(s,r'(?:host|TV).{0,100}(?:Bluetooth\s*5\.1|MRM24|webOS\s*24|bundle)',r'(?:DUT|AKB\d+).{0,100}(?:Bluetooth\s*5\.0|AAA|webOS\s*23|validated|compatib|separate|model)')
            return explicit or labelled
        if check=='decision-gate':
            s=p+' '+a+' '+r
            return all_of(s,r'(?:N/?A|not applicable).{0,130}(?:reason|basis|evidence|record)|(?:unsupported|absent|unavailable).{0,100}(?:N/?A|not applicable)|(?:reason|basis|evidence|record).{0,80}(?:N/?A|not applicable)',r'(?:unresolved|unconfirmed|conflict|pending|unknown).{0,160}(?:blocked|pending|pass.?fail|acceptance|decision|stop|withhold)|(?:blocked|pending).{0,100}(?:authority|confirmation|requirement|unresolved|conflict)')
        if check=='pair-endpoints':
            trigger=all_of(t,r'(?:record|timestamp|time|timing).{0,150}(?:OK|wheel|press)|(?:OK|wheel).{0,80}(?:record|timestamp|time)',r'first.{0,40}(?:pairing |registration )?indication',r'registration.{0,30}(?:confirmation|completion)|completion message',r'first.{0,40}(?:successful|usable).{0,30}(?:control|pointer|button)')
            sequence=all_of(t,r'(?:record|time).{0,70}(?:registration|confirmation)',r'(?:record|time|until).{0,70}(?:pointer|control).{0,30}(?:usable|available)',r'observe.{0,35}LED.{0,40}(?:whole|sequence|throughout)') and all_of(o,r'unpaired',r'pairing',r'paired',r'blink',r'solid')
            actual_pair=all_of(t,r'\b(?:press|release)\b.{0,55}\b(?:OK|wheel)\b|\bwheel\b.{0,30}\bpress|press and hold Home and Quick Settings together',r'pair|register|registration|unregistered|unpaired')
            objects=all_of(t+' '+o,r'LED|indicator|indication',r'registration|registered|pairing (?:complete|confirmation)',r'pointer|usable control')
            verification=all_of(t,r'move.{0,45}(?:remote|pointer)|pointer.{0,30}(?:tracks|responds)|verify.{0,45}(?:pointer|control)|select.{0,30}(?:tile|target)',r'record|observe|time|capture|verify|confirm|stopwatch')
            return trigger or sequence or bool(actual_pair and objects and verification)
        if check=='pair-authority':
            s=t+' '+a+' '+r
            # A prohibition on conflating clocks is itself a scope guard.
            # A prohibition on adopting the source/event statement is not.
            s=' '.join(clause for clause in relation_clauses(s) if not re.match(r'^(?:do not|never)\b',clause,re.I) or re.match(r'^(?:do not|never)\s+(?:conflate|equate|substitute|interchange|merge)\b',clause,re.I))
            if not all_of(s,r'pair|registration',r'completion|confirmation',r'timeout',r'applicab|source|SOP|authority|approved|pending|scope'): return False
            if found(r'timeout.{0,100}(?:same|identical).{0,30}(?:completion|confirmation).{0,15}clock',s):return False
            separate=any(any_of(clause,r'(?:timeout.{0,160}(?:distinct|separate)|(?:distinct|separate).{0,160}timeout)',r'(?:not|never).{0,45}(?:substitut|interchange|equate).{0,100}(?:timeout|completion)',r'timeout.{0,80}(?:is not|not a|not the).{0,50}(?:completion|confirmation)',r'timeout observation,? not a completion') for clause in relation_clauses(s) if found(r'timeout',clause))
            separate=separate or (all_of(s,r'timeout',r'different quantities.{0,40}not merged|each.{0,25}own endpoint') and all_of(t,r'no success|unsuccessful',r'stops trying|give.up|advertising.{0,30}stop|return.{0,30}unpaired'))
            # Negated absence of a separate observation is not separation.
            if found(r'no separate.{0,30}timeout|timeout.{0,60}not.{0,20}(?:separate|distinct)',s):separate=False
            events=all_of(s,r'first.{0,35}(?:screen|response|indication)|(?:screen|response).{0,35}first',r'complet|confirm')
            return separate
        if check=='pair-repeats':
            resets=all_of(t,r'(?:repeat|each|between).{0,110}(?:unpair|deregister|clear.{0,25}binding)|(?:cleared binding|unpaired state).{0,100}(?:repeat|attempt)')
            series=found(r'repeat.{0,70}(?:three|five|\d+).{0,60}(?:unpaired|clean|cleared)|repeat attempts from.{0,25}cleared binding|(?:each|between).{0,60}(?:pairing trial|pairing attempt|attempt).{0,60}(?:unpair|deregister|binding)',t)
            resets=resets or all_of(t,r'repeat',r'(?:restore|restoring).{0,30}unpaired.{0,40}between')
            failed_retry=all_of(t,r'first.{0,35}(?:attempt|registration)|attempt.{0,25}once',r'fail|prevent completion|no registration',r'repeat|retry|re.pair|restore.{0,50}(?:condition|Bluetooth|BT)') and all_of(t+' '+lp,r'unpaired|unregistered|clear.{0,40}(?:registration|binding)',r'pair|register|registration|wheel')
            retained=all_of(t+' '+outcome+' '+r,r'(?:record|retain|all|remain).{0,90}(?:fail|attempt|result|observation)|successes.?/.?attempts|fail.{0,70}(?:record|retain|population|denominator)|record both|record.{0,40}(?:individual|every).{0,25}(?:time|value)|record.{0,35}(?:retry|interruption).{0,30}(?:time|method)|observe for up to.{0,15}\d+.{0,15}without another key press')
            return bool(retained and ((resets and series) or failed_retry))
        if check=='bt-absent':
            # A local methodological imperative remains an operative action
            # when placed in Remarks; an expected or quoted state alone does not.
            observation_notes=' '.join(s for s in sentences(r) if found(r'\b(?:confirm|verify|check|observe)\b.{0,90}pointer.{0,50}(?:absent|unavailable|loss|not|no )',s))
            test=t+' '+observation_notes
            if all_of(test,r'before.{0,30}(?:Bluetooth|BT).{0,20}ready|(?:Bluetooth|BT).{0,30}(?:unavailable|down)',r'(?:confirm|verify|observe|check).{0,90}pointer.{0,50}(?:absent|unavailable|loss|does not)'):return True
            if not semantic_check('bt-absent',test+' '+p,test):
                return all_of(t,r'deregister|disable.{0,45}(?:BT|Bluetooth)|forced? IR|hold power.{0,25}volume',r'(?:verify|confirm|observe|check).{0,90}(?:pointer.{0,40}(?:unavailable|absent|disappear|loss|does not|no |gone)|no pointer.{0,20}available)') or (all_of(t,r'interrupt.{0,30}Bluetooth',r'attempt pointer movement') and all_of(outcome,r'no pointer movement',r'verified.{0,25}(?:BT|Bluetooth).{0,20}loss'))
            return all_of(t+' '+p,r'pointer|connection state|link state|status|host.{0,40}(?:no.remote|unregistered)')
        if check=='ir-negative-control':
            if found(r'learned|learning|learn a',t):return False
            if found(r'(?:BT|Bluetooth).{0,35}(?:loss|state).{0,45}(?:not established|not verified)|(?:BT|Bluetooth).{0,35}not established as unavailable|host connection remains as found',t+' '+lp):return False
            if not all_of(t+' '+lp,r'\b(?:IR|infrared)\b'):return False
            if not all_of(t,r'block|occlud|opaque|cover|line.of.sight.{0,20}broken',r'Volume|Power|basic|same (?:key|button|command)',r'repeat|compare|blocked.{0,70}restor|line.of.sight.{0,20}broken'): return False
            disabled=all_of(t+' '+lp,r'(?:BT|Bluetooth).{0,70}(?:off|disabled|unavailable|disconnect)|deregister|unpaired',r'pointer.{0,60}(?:unavailable|absent|disappear|loss)|(?:connection|registration|link).{0,40}(?:off|disabled|absent|unregistered)|TV.{0,20}(?:BT|Bluetooth).{0,20}disabled') or semantic_check('bt-absent',t,t)
            if not disabled:return False
            if found(r'without.{0,40}(?:block|occlud).{0,40}\bIR\b',t): return False
            restore=found(r'(?:restore|re.enable).{0,35}(?:BT|Bluetooth)|(?:BT|Bluetooth).{0,35}restored',t)
            block=found(r'(?:block|cover|occlud).{0,45}\bIR\b|\bIR\b.{0,45}(?:block|cover|occlud)',t)
            if restore and block and restore.start()<block.start() and not found(r'unpaired.{0,80}(?:block|state)|both.{0,40}(?:paired|unpaired)|paired and unpaired|Bluetooth remains disabled|BT remains disabled|dual.disabled',t[restore.start():]+' '+outcome):return False
            return all_of(outcome,r'(?:no|not|none|0/|stop|disappear|does not).{0,80}(?:response|action|effect|control|work|Power|Volume|execute)|(?:blocked).{0,100}(?:no|not|none|stop)|(?:response).{0,70}(?:absent|disappear|cease)|(?:IR.only|unpaired.{0,30}blocked).{0,60}fails?')
        if check=='fallback-recovery':
            causal=all_of(t,r'\bIR\b|infrared',r'block|occlud|opaque|cover',r'(?:remove|restore|unblock|uncover|reconnect)')
            restored=all_of(t+' '+outcome,r'pointer',r'Volume|Power|basic|button',r'(?:restore|recover|return|reconnect).{0,120}(?:pointer|basic|BT|Bluetooth|baseline|response)|(?:pointer|basic|BT|Bluetooth).{0,100}(?:restore|recover|return|reconnect)')
            loss=all_of(t,r'loss|disconnect|boot|disable|deregister|off|block|cover',r'restore|return|reconnect|uncover|recover')
            route_restore=bool(list(adopted_relation(r'\b(?:restore|reconnect|re.enable|unblock|uncover)\b.{0,55}\b(?:IR|infrared|BT|BLE|Bluetooth|route|path|connection|paired state)\b|\b(?:IR|BT|BLE|Bluetooth)\b.{0,35}(?:reconnects?|re.establishes?|recovers?|restored)',t)))
            # Uncovering restores the very optical barrier established in this
            # experiment; returning a disconnected remote into range restores
            # its radio opportunity. Neither is a mere record-recovery label.
            route_restore=route_restore or bool(causal and list(adopted_relation(r'\buncover\b|remove.{0,25}(?:barrier|cover|obstruction)',t)))
            route_restore=route_restore or bool(list(adopted_relation(r'\breturn\b.{0,35}(?:DUT|remote)?.{0,20}(?:within|to).{0,20}(?:\d+\s*m|range)|\bmove\b.{0,35}(?:remote|DUT).{0,15}back.{0,25}(?:within|range)|move only enough to allow automatic recovery',t)))
            route_restore=route_restore or bool(remote_power and list(adopted_relation(r'\brestore\s+power\b',t)))
            complete_restart=bool(list(adopted_relation(r'\b(?:replug|plug.{0,15}back|reconnect).{0,35}(?:TV|host|power)|\b(?:restart|reboot)\s+(?:the\s+)?(?:TV|host)\b|\b(?:perform|complete|execute)\b.{0,30}(?:TV|host).{0,15}(?:restart|reboot)',t)))
            complete_restart=complete_restart or any(bool(list(adopted_relation(r'\b(?:disconnect|unplug|switch off)\b.{0,25}(?:TV|host).{0,25}(?:mains|AC|power)',clause))) and bool(list(adopted_relation(r'\b(?:reconnect|replug)\b|plug.{0,15}back',clause))) for clause in relation_clauses(t))
            return bool(restored and (causal or loss) and (route_restore or complete_restart))
        if check=='target-observation':
            return all_of(t,r'interference|stress|RF',r'non.?target|unintended',r'observe|monitor|record',r'concurrent|simultaneous|same (?:command|attempt)|at the same time')
        if check=='route-classification':
            return all_of(t+' '+a+' '+r,r'interference|stress|RF',r'\b(?:BT|Bluetooth)\b.{0,100}(?:address|binding|misbind|wrong.target)',r'\bIR\b.{0,100}(?:broadcast|shared)|(?:broadcast|shared).{0,60}\bIR\b')
        if check=='interference-controls':
            baseline=found(r'baseline|reference|no stress source|(?:interference|stress) sources off|quiet RF setup',t)
            stress=found(r'enable.{0,55}(?:headphone|hotspot|interfer|stress)|introduce.{0,50}(?:interfer|stress)|(?:apply|activate).{0,35}(?:interfer|stress)',t)
            if baseline and stress and baseline.start()>stress.start() and not found(r'enable.{0,55}(?:headphone|hotspot|interfer|stress)|introduce.{0,50}(?:interfer|stress)|(?:apply|activate).{0,35}(?:interfer|stress)',t[baseline.end():]):return False
            return bool(baseline) and all_of(t,r'interfer|stress',r'(?:remove|off|restor|disable).{0,80}(?:interfer|stress|source)|(?:interfer\w*|stress).{0,70}(?:remove|off)|post.removal',r'compare|repeat|recovery|post',r'attempt|count|latenc|timing|sample|press|response time|input|response')
        if check=='safe-power':
            removable_trial=remote_power and all_of(t,r'remove.{0,25}power source',r'reconnect power.{0,30}fit cells') and found(r'remove cells.{0,30}replaceable branch',lp)
            if false_sealed_cycle and not removable_trial:return False
            safe_stop=remote_power and all_of(t+' '+lp,r'(?:sealed|non.removable)',r'(?:stop|N/?A|Not Executed|hold).{0,90}(?:power|case|removal)|(?:power|removal).{0,90}(?:stop|N/?A|Not Executed)',r'construction|APP|PRQ|identified|recorded') and found(r'restore|permitted|applicable',t)
            method=found(r'normal.{0,20}(?:method|procedure|power)|(?:approved|confirmed).{0,50}(?:power|method|shutdown|construction|hardware branch)|(?:power.cycle|restore power).{0,80}appropriate|(?:means|method).{0,50}construction|where (?:the )?construction allows|remove.{0,35}(?:cells|batteries)|documented.{0,25}power.interrupt method|method pending confirmation for the unit variant|branch.appropriate method',t+' '+lp)
            return bool(safe_stop or (remote_power and method and found(r'actual construction|inspected construction|confirmed construction|confirmed hardware branch|confirmed power method|variant|removable|sealed|AAA|identified hardware',t+' '+p)))
        if check=='before-manual-pair': return semantic_check('before-manual-pair',t,t)
        if check=='retention-authority':
            ambiguous=found(r'DUT/host|remote/host|host/remote|TV/remote|host or remote|TV or remote',t)
            unqualified=found(r'(?:power restoration|recovery).{0,50}(?:proves|establishes|guarantees).{0,50}(?:binding|pairing persistence)|(?:all|any).{0,30}(?:variant|construction).{0,40}(?:reconnect|recover).{0,20}(?:within|<=)',a+' '+r)
            recovery=all_of(t,r'(?:remove|interrupt).{0,25}(?:the )?power source|remote.{0,25}power.off',r'restore|reconnect',r'observe|record|check|verify|confirm') and all_of(t+' '+outcome,r'remote|DUT',r'resum|recover|pair|binding|registration') and not found(r'power.cycle (?:the )?(?:host|TV)',t)
            # A planned conditional experiment need not execute the resolved
            # hardware branch or satisfy the separate safe-operation leaf.
            # Its operative event, recovery observation and authority guard
            # must nevertheless coexist in this case; a bare pending policy
            # cannot stand in for a missing event or observation.
            conditional_event=any(
                found(r'\b(?:on|for|if|when)\b.{0,45}\b(?:sealed|non.removable|built.in)\b',clause)
                and not found(r'\b(?:host|TV|television|display)\b',clause)
                for clause,_ in adopted_relation(r'\b(?:use|perform|apply|execute|follow|carry out)\b.{0,45}\b(?:approved|documented|confirmed)\b.{0,45}\b(?:power[ -]cycle|power interruption|power.off.{0,15}(?:and|then).{0,15}(?:on|restor))\b',t))
            recovery_observation=bool(list(adopted_relation(r'\b(?:observe|record|check|verify|distinguish|classify|separate|compare)\b.{0,100}\b(?:retained binding|binding retention|auto.reconnect|manual re.pair|recovery outcomes?)\b',t+' '+o)))
            pending_authority=bool(list(adopted_relation(r'\b(?:retain|mark|keep|leave|treat)\b.{0,45}\b(?:unresolved|unconfirmed|uncertain)\b.{0,65}\b(?:pending|non.pass|not executed|hold)\b',a+' '+r)))
            conditional_recovery=conditional_event and recovery_observation and pending_authority and found(r'\b(?:remote|DUT)\b',t+' '+p)
            return bool((remote_power or recovery or conditional_recovery) and not ambiguous and not unqualified)
        if check=='motion-metric':
            return all_of(t+' '+o,r'physical.{0,35}(?:motion|movement)|remote movement|movement.to.(?:display|update)|motion.to.pointer',r'(?:first|corresponding|screen|pointer).{0,35}(?:update|displacement|move|pixel|coordinate change)|movement.to.(?:display|update)') and all_of(t+' '+lp,r'high.speed|high.frame|synchroniz|240|resolution|common.clock|one time base|instrument') and all_of(t,r'measure|calculat|record|compute')
        if check=='click-denominator':
            coordinates=found(r'coordinates?|pixels?|\bpx\b|(?:known|marked|recorded|predefined).{0,40}target.{0,20}cent(?:er|re)|target.{0,20}cent(?:er|re).{0,40}(?:known|marked|recorded)|(?:measure|record).{0,55}(?:deviation|click position).{0,65}(?:icon|target|cent(?:er|re))|record.{0,55}pointer position.{0,65}(?:icon|target).{0,15}cent(?:er|re).{0,50}deviation|measure click.to.pointer.center deviation|measure.{0,35}selected point.{0,35}(?:pointer|target).{0,15}center',t)
            click_input=bool(list(adopted_relation(r'\bclick\b.{0,40}(?:target|icon|tile)|\bpress\b.{0,40}\b(?:OK|wheel)\b|\b(?:perform|execute|repeat)\b.{0,45}(?:click|target selection)|\bselect\b.{0,30}(?:target|icon|tile)',t)))
            ledger=t+' '+a
            successes=r'(?:successful.{0,25}(?:clicks?|selections?|activations?|hits?)|(?:target )?hits?|success(?:es| rate)?|correct.{0,25}(?:clicks?|selections?|activations?))'
            ratio=bool(list(adopted_relation(successes+r'.{0,35}(?:/|divided by|over|out of).{0,25}(?:(?:all|total)\s+)?(?:attempts?|clicks?)',ledger)))
            count=r'(?:[1-9]\d*|one|two|three|four|five|six|seven|eight|nine|ten|twenty|thirty|forty|fifty|hundred)'
            population=bool(list(adopted_relation(r'\b(?:click|repeat|attempt|press|select)\b.{0,55}\b'+count+r'\b.{0,12}(?:times|attempts|clicks|consecutively)|\b'+count+r'\b.{0,25}(?:consecutive )?(?:clicks|attempts|selections)|\b'+count+r'\s*/\s*'+count+r'\b',ledger)))
            success_record=bool(list(adopted_relation(r'(?:record|count|report|retain|calculate|compute).{0,60}(?:'+successes+r'|miss(?:es)?|failures?|whether.{0,55}(?:select|activat|hit))|success (?:rate|ratio)|\b100\s*%.{0,25}(?:click|selection|activation|success)',ledger)))
            per_attempt=bool(list(adopted_relation(r'(?:each|every|all).{0,25}(?:attempt|click).{0,70}(?:success|fail|miss|activation)|(?:success|fail|miss|activation).{0,70}(?:each|every).{0,25}(?:attempt|click)',ledger)))
            return bool(coordinates and click_input and (ratio or (population and success_record) or per_attempt))
        if check=='hide-clock':
            test=t+' '+' '.join(clause for clause in sentences(r) if found(r'\brecord\b.{0,35}(?:observed )?hide time',clause))
            return all_of(test,r'(?:last.{0,40}(?:motion|movement)|(?:place|leave|keep|hold).{0,50}(?:still|motionless|stable))',r'time|measure|record',r'(?:pointer|cursor).{0,70}(?:hid(?:e|ing|den)|disappear|absent|no longer (?:visible|rendered))|(?:hide|disappear).{0,50}(?:pointer|cursor)')
        if check=='wake-clock':
            hidden=all_of(t+' '+lp,r'pointer.{0,45}(?:hidden|absent|hide|idle|disappear|not visible|no longer rendered)|(?:hide|hidden|absent).{0,35}pointer|reappear',r'shake|physical motion|physical movement|wake stimulus|move.{0,30}laterally|motion start')
            timed=all_of(t,r'(?:time|measure|timing|stopwatch|latency|record (?:the )?(?:time|elapsed|latency|interval)).{0,90}(?:pointer.{0,25}(?:reappear|appear|visible|rendered again)|(?:reappear|appear|visible|rendered again).{0,35}pointer|first.{0,30}pointer)|(?:shake|stimulus).{0,80}(?:start timing|(?:time|measure) reappearance)|(?:reappear|appear|return).{0,25}(?:latency|time)|measure return latency|(?:shake|motion|stimulus).{0,35}(?:to|-to-).{0,35}(?:visible|rendered).{0,20}pointer.{0,25}(?:latency|time)')
            framed=all_of(t,r'motion start',r'record.{0,30}first visible pointer frame') and found(r'video|synchroniz|camera|frame',lp)
            return bool(hidden and (timed or framed))
        if check=='power-timer-distinction':
            s=t+' '+a+' '+r
            if business_damage('false-electrical-state',case):return False
            if found(r'low.power state.{0,50}evidenced by.{0,50}pointer|observable consequence.{0,60}pointer.{0,60}used instead',s):return False
            experiment=all_of(t,r'pointer',r'idle|still|sleep|hide|disappear')
            withheld=any_of(s,r'(?:do not|cannot|does not|must not|not valid to).{0,75}(?:infer|prove|equate|establish|claim).{0,70}(?:power|current|sleep)',r'(?:power.sleep|power sleep|current).{0,90}(?:not measured|not inferred|unmeasured|pending|withheld|unproven)')
            withheld=withheld or bool(found(r'(?:visibility|pointer.hide).{0,50}(?:is not|not automatically|neither source).{0,100}(?:low.power|sleep|power)',s))
            withheld=withheld or bool(found(r'separate the pointer visibility timer from.{0,50}(?:current|power sleep)',s))
            withheld=withheld or bool(found(r'(?:visibility|pointer.hide).{0,65}\bnot\b.{0,35}(?:low.power|power.sleep|power timer)',s))
            measured=any(all_of(sentence,r'measure|record|capture',r'current|power consumption') for sentence in sentences(t)) and bool(found(r'separate|independent|timestamp',t))
            return experiment and all_of(s+' '+lp,r'power.sleep|power sleep|low.power|current|power state') and (withheld or measured)
        if check=='wheel-context':
            # Bind the comparison state to the scrolled object. A pointer's
            # coordinates or Home focus do not establish a list's scroll offset.
            scroll_state=' '.join(sentence for sentence in sentences(t+' '+lp+' '+a+' '+r)
                if not found(r'(?:pointer|cursor).{0,30}position|Home.{0,35}(?:position|focus)',sentence))
            start=any_of(scroll_state,r'(?:initial|starting|known|marked|reference|same|restore).{0,40}(?:scroll|list).{0,25}(?:position|offset)',r'(?:list|page|viewport).{0,80}(?:known|marked|initial|reference|recorded).{0,25}(?:position|mark|offset)',r'(?:first|top).{0,20}item.{0,30}(?:top|initial|known)')
            start=start or all_of(scroll_state,r'list|page|viewport',r'(?:hold|restore|keep).{0,35}(?:initial|start(?:ing)?|known|marked|same|reference).{0,25}position')
            start=start or all_of(scroll_state,r'list|page|viewport',r'(?:record|mark).{0,35}(?:top item|scroll position)|same recorded position|recorded (?:top|first) item')
            if found(r'no (?:list|scroll|viewport).{0,70}(?:established|restored)|(?:scroll|list).{0,30}(?:position|offset).{0,40}(?:not established|not restored)',t+' '+lp):start=False
            return bool(start and all_of(t,r'wheel|scroll',r'forward|backward|direction|detent|reverse|flick|release') and found(r'scrollable|(?:support|expos)\w*.{0,40}(?:scroll|wheel|inertia)|(?:app|player).{0,70}support|browser page|app list|static list',t+' '+lp+' '+a))
        if check=='press-context':
            short=found(r'short.{0,40}press|press.{0,20}short|press.{0,45}duration under|single.press',t)
            long=found(r'(?:press and hold|hold|long.press).{0,100}(?:\d|duration|timed)|(?:\d|duration).{0,70}long.press',t)
            actor=r'(Quick Settings|Settings|Home Hub|Home|Back|Exit|Input|Wheel/OK|OK|Accessibility|AI|Netflix)\b'
            short_actor=found(r'(?:short.press|press)\s+(?:the\s+)?'+actor,t)
            long_actor=found(r'(?:press and hold|hold|long.press)\s+(?:the\s+)?'+actor,t)
            if short_actor and long_actor and short_actor.group(1).lower()!=long_actor.group(1).lower():return False
            fragment=t[short.end():long.start()] if short and long and short.end()<long.start() else ''
            restorations=list(re.finditer(r'\b(?:restore|reset|dismiss|return|close)\b',fragment,re.I))
            between=bool(restorations) and not found(r'\b(?:press|hold|launch|open)\b',fragment[restorations[-1].end():])
            resumed=bool(short and long and found(r'(?:single.press|press).{0,35}(?:OK|wheel).{0,20}again',fragment) and all_of(t+' '+outcome,r'while (?:video is )?playing',r'paus',r'resum'))
            resumed=resumed or bool(short and long and all_of(t,r'single.press.{0,40}OK.{0,20}again',r'while video is playing') and all_of(outcome,r'paus',r'resum'))
            global_reset=found(r'(?:reset|restore).{0,50}(?:stated |recorded |same )?initial state.{0,35}between (?:trials|attempts)',p)
            contextual=all_of(t,r'(?:from|starting).{0,30}(?:Home|live TV|app)',r'hold.{0,35}\d+(?:\.\d+)?\s*s',r'reset context',r'compare.{0,45}short press',r'repeat.{0,30}(?:duration|times|each)')
            return bool(between or resumed or contextual) or bool(found(r'short.press.{0,150}restore\s*,?\s*then hold',t)) or all_of(t,r'short.{0,30}press',r'long.press|hold.{0,20}\d',r'dismiss.{0,70}same element|(?:restore|reset|return).{0,80}between.{0,35}(?:branch|press|trial|attempt)|(?:restore|reset).{0,70}(?:before each|each branch)') or bool(short and long and global_reset)
        if check=='back-component':
            return all_of(t,r'\bBack\b',r'press|hold') and all_of(t+' '+outcome,r'one.(?:UI.)?level|previous.level|one navigation|exactly one|one level')
        if check=='exit-component':
            return all_of(t,r'\bExit\b',r'press',r'app|menu|screen|overlay|Settings|context') and all_of(t+' '+outcome,r'clos|leave|leav|exit.{0,30}(?:app|context|screen)|clears? overlays')
        if check=='ui-component':
            return voice and all_of(t,r'(?:time|measure|stopwatch|latency|elapsed).{0,100}(?:press|actuation|button|key.down)|(?:press|actuation|key.down).{0,100}(?:time|measure|stopwatch)',r'(?:to|until|stop).{0,70}(?:waveform|voice UI|listening UI|voice interface|first.{0,15}UI)')
        if check=='action-component':
            if not all_of(t,r'issue|speak|say|execute|command.{0,30}(?:measure|time)|measure.{0,30}command'):return False
            if found(r'(?:LED|indicator).{0,80}\bor\b.{0,40}(?:button|press|UI|waveform)|(?:button|press).{0,60}\bor\b.{0,40}(?:LED|indicator)',t): return False
            return voice and all_of(t,r'(?:time|measure|start|latency).{0,100}(?:microphone[ -]LED|mic[ -]LED|LED.on|LED.{0,20}(?:on|lights)|listening indicator).{0,150}(?:action|execut|final.state)|(?:LED.on|LED.{0,20}(?:on|lights)).{0,60}(?:to|until|stop).{0,100}(?:action|execut)',r'time|measure|start|latency')
        if check=='local-cloud':
            return local(case,'action-component') and all_of(t+' '+a,r'local',r'cloud|network.dependent',r'(?:separate|classif|corresponding).{0,100}(?:series|endpoint|limit|latency)|(?:local).{0,90}(?:500\s*ms|0\.5\s*s).{0,150}(?:cloud|network)|(?:500\s*ms|0\.5\s*s).{0,65}local.{0,130}(?:cloud|network)')
        if check=='voice-repeats':
            return voice and all_of(t,r'repeat|five|5.{0,15}(?:trial|attempt|observation)|each observation|series') and all_of(t+' '+a,r'mean|average') and all_of(p+' '+t,r'network|service',r'paired|registered|Bluetooth|\bBT\b|connection|normally connected')
        if check=='attempt-ledger':
            if not voice:return False
            record=all_of(t,r'record|retain|archive',r'(?:recognized|recognition|transcript|intent)',r'executed action|actual action|action.{0,30}(?:correct|outcome|executed)|correct.{0,30}(?:action|operation)|operation.{0,30}(?:executed|observed)|observed operation|whether.{0,30}executed')
            ref=all_of(t+' '+a,r'reference|utterance|command.{0,35}(?:set|corpus)|(?:100|ten|10).{0,35}commands|10.command')
            population=any_of(t+' '+a+' '+m,r'(?:all|every|each).{0,35}(?:attempt|command|outcome)|each.{0,30}once|(?:95|9) of (?:100|10)|(?:100|10).{0,70}(?:fail|timeout)|(?:fail|timeout).{0,70}(?:denominator|population|attempt)|accuracy across the 10 commands')
            # A transcript case may explicitly refer to the command experiment
            # whose attempt rows it extends. Do not borrow unrelated cases.
            linked_ledger=any(all_of(c['business_text']['steps'],r'record',r'each|every|all',r'executed|action',r'correct|incorrect',r'not recogniz|recogniz|transcript') for c in related)
            return (record and ref and population) or (linked_ledger and all_of(t,r'recogniz.{0,30}transcript|transcript',r'each|every',r'reference|utterance',r'word|WER'))
        if check=='two-rates':
            if not voice:return False
            # A global formula can define this experiment's metric only after
            # the operative row actually records recognition/action outcomes.
            if not all_of(t,r'record|compute|count|score|derive',r'recogniz|recognition|transcript|intent',r'executed action|actual action|action.{0,35}(?:correct|outcome|executed)|record.{0,100}action|correct.{0,30}action|observed operation|operation actually observed|action rate'):return False
            s=t+' '+a+' '+m
            if all_of(lp,r'definition of.{0,10}correct',r'recogniz.{0,30}AND.{0,50}action executed'):return False
            for label,wanted,variables in [
                (r'(?:recognition|transcription) (?:accuracy|success rate|rate)',lambda v:v['r']/v['t'],'rt'),
                (r'(?:action|execution) (?:accuracy|success rate|rate)',lambda v:v['a']/v['t'],'at')]:
                explicit=found(label+r'\s*(?:\(\s*%\s*\))?\s*(?:=|is defined as|equals|calculated as|(?::|is)\s*[^;.]{0,100}(?:/|divided by|over|out of))',s)
                if explicit and wrong_metric_formula(s,label,wanted,variables):return False
            if semantic_check('two-rates',s,t): return True
            combined=any_of(t+' '+a,r'correct recognition\s*/\s*action.{0,20}(?:percentage|rate)',r'(?:recognition|intent).{0,40}(?:rate|accuracy|correctness).{0,15}(?:defined|requires|only if|both).{0,70}(?:execut|action)')
            if combined and not all_of(t,r'record three separate outcomes',r'recogniz.{0,30}as intended',r'EXECUTED ACTION.{0,30}match'):return False
            return all_of(t+' '+a+' '+m,r'(?:recogniz|recognition|transcript|intent).{0,110}(?:correct|rate|scor|intended)|recogniz.{0,30}as.intended',r'action.{0,80}(?:correct|rate|scor|match)|correct.{0,30}(?:final )?action',r'(?:separate|separately|distinct|independently|own columns).{0,80}(?:recogniz|recognition|action|outcome|metric|scor)|(?:outcome|recogniz|recognition|action).{0,100}(?:separate|separately|distinct|independently|own columns)',r'(?:out of|/|denominator|every intended|all intended|all.{0,20}attempt).{0,70}(?:10|100|attempt)|(?:all|every).{0,30}(?:attempt|intended|outcome)|all (?:\d+ )?commands|all utterances|denominator.{0,40}timeout')
        if check=='wer-distinction':
            s=t+' '+a+' '+r+' '+m+' '+p
            if not wer_used(t+' '+a+' '+r):return False
            if semantic_check('wer-distinction',s,t):return True
            return all_of(s,r'reference.{0,20}words?|word population',r'(?:divid|denominator|/).{0,60}(?:reference|word)|(?:reference words|word population).{0,60}(?:denominator|separate|distinct)|word.{0,70}(?:population|denominator)',r'distinct|separate|not.{0,50}(?:command|success)|lower is better|word.{0,70}(?:error|population)')
        if check=='matched-corpus':
            context=t+' '+lp+' '+' '.join(c['business_text']['steps'] for c in related)
            paired_noise=all_of(t,r'noise|noisy|\bdB\b',r'run|repeat|compare|speak')
            inherited_corpus=all_of(t,r'(?:run|repeat).{0,30}(?:the corpus|the same|the identical|the utterance)',r'repeat|re.run') and all_of(lp,r'corpus',r'fixed|unchanged|same|controlled')
            inherited_corpus=inherited_corpus or all_of(t,r'create.{0,30}fixed.{0,25}utterance set',r'quiet baseline',r'run the identical set',r'noise')
            return voice and paired_noise and all_of(context,r'quiet|reference|baseline|repeat',r'noise|noisy|\bdB\b',r'same|identical|matched|unchanged|fixed',r'corpus|utterance|command|test set',r'geometry|distance|10\s*cm',r'pace|level|speaker|speaking') and all_of(t+' '+p,r'network|service',r'fixed|same|constant|stable|unchanged') and (semantic_check('matched-corpus',context,context) or inherited_corpus)
        if check=='acoustic-level':
            if found(r'(?:meter|measurement|SPL).{0,50}(?:not at|away from).{0,35}(?:remote |DUT )?(?:microphone|mic)',t+' '+lp):return False
            positioned=any_of(t+' '+lp,r'(?:measure|record|meter|SPL|noise level|ambient level).{0,65}(?:at (?:the )?(?:remote |DUT )?(?:microphone|mic)|microphone position)',r'(?:microphone|mic).{0,30}(?:SPL|noise level|acoustic level)',r'(?:measure|record).{0,50}(?:SPL|dB).{0,25}at the (?:remote|DUT)\b',r'\bdB.{0,15}at the (?:microphone|DUT)',r'At the (?:remote )?microphone position.{0,50}(?:measure|establish|record).{0,50}(?:noise|SPL|dB)')
            positioned=positioned or all_of(lp,r'(?:place|position).{0,30}(?:sound level |SPL )?meter.{0,70}near (?:the )?(?:DUT |remote )?microphone',r'sampling point') and all_of(t,r'measure|record',r'sampling point')
            positioned=positioned or bool(found(r'(?:measure|record|verify).{0,35}(?:ambient|noise|sound|acoustic).{0,65}at (?:the )?(?:remote|DUT)\b|(?:set|play).{0,70}calibrated.{0,35}(?:noise|SPL).{0,35}at (?:the )?(?:remote|DUT)\b',t))
            measurement=found(r'(?:measure|record|re.measure|establish calibrated).{0,90}(?:SPL|dB|sound|acoustic|ambient level|noise level|pink noise|LAeq)|(?:SPL|sound.level).{0,40}meter',t)
            # Setting a calibrated acoustic field at the sampling location with
            # a declared meter is a measurement operation, not a UI percentage.
            measurement=measurement or (all_of(t,r'(?:set|adjust|calibrat|verify).{0,65}(?:\bdB[AC]?\b|SPL)',r'noise|acoustic|ambient') and found(r'sound.level meter|SPL meter|calibrated.{0,30}meter',lp))
            return bool(voice and positioned and measurement and found(r'noise|quiet|ambient',t) and semantic_check('acoustic-level',t+' '+lp,t+' '+lp))
        if check=='drop-definition':
            return all_of(t+' '+a,r'zero|undefined',r'baseline|quiet',r'absolute|success|attempt') and semantic_check('drop-definition',t+' '+a+' '+m,t)
        if check=='unlearned-baseline':
            negative=semantic_check('unlearned-baseline',t+' '+outcome,t+' '+outcome)
            negative=negative or all_of(t,r'unlearned reference',r'observe.{0,30}target',r'learn') and all_of(outcome,r'response.{0,30}only after learning',r'clearing.{0,40}removes')
            original=all_of(t+' '+lp,r'original.{0,40}(?:remote|handset)|(?:known.good|working).{0,25}(?:remote|handset)',r'learn',r'target|external')
            original=original or any(all_of(c['business_text']['steps']+' '+c['business_text']['local_preconditions'],r'original.{0,40}(?:remote|handset)',r'learn') and str(case['case_key']).upper() in c.get('related_case_keys',[]) for c in cases)
            return original and negative
        if check=='cec-isolation':
            s=t+' '+lp
            restored=found(r'(?:restore|re.enable).{0,30}(?:CEC|SimpLink)',t)
            blocked=found(r'(?:block|occlud|opaque|obstruct).{0,55}\bIR\b|\bIR\b.{0,35}(?:block|occlud)',t)
            learned_context=found(r'code learned onto the remote|learned.{0,25}(?:key|mapping|code)|\blearn\b',t+' '+lp)
            route_matrix=bool(learned_context and all_of(t,r'disable.{0,25}(?:SIMPLINK|CEC)',r'verify.{0,25}disabled state',r're.issue.{0,35}command.{0,35}IR path clear',r'IR path.{0,15}AND disable CEC|disable both routes'))
            if restored and blocked and restored.start()<blocked.start() and not route_matrix:return False
            absent=all_of(t,r'verify|confirm|check',r'no CEC connection|CEC.{0,25}(?:not connected|absent)')
            return route_matrix or (all_of(t,r'\blearn\b',r'\bIR\b|infrared',r'block|occlud|opaque|obstruct') and (absent or semantic_check('cec-isolation',t,t)))
        if check=='persistence-evidence':
            if false_sealed_cycle:return False
            ambiguous_owner=r'(?:DUT/host|remote/host|host/remote|TV/remote|host or remote|TV or remote)'
            cycle=remote_power and not found(r'(?:power[ -]cycle|power off|interrupt.{0,15}power)\s+(?:the\s+)?'+ambiguous_owner+r'|'+ambiguous_owner+r'\s+power[ -]cycle',t)
            # A named state owner may be resolved separately for each approved
            # mapping branch. Cycling a host alone still cannot prove DUT NVM.
            owner_cycle=all_of(t,r'(?:record|identify|confirm).{0,55}(?:storage|config|state).{0,20}owner',r'(?:power.cycle|reboot|power.interruption).{0,50}(?:that|the recorded|the identified).{0,25}(?:state |storage )?owner',r'before.{0,55}(?:repair|recreat|relearn|pair)',r'same.{0,25}command|every.{0,25}mapping|each.{0,25}mapping') and all_of(lp,r'IR|learning|learned|mapping',r'approved|internal|passed') and not found(r'host.{0,35}(?:proves|establishes|guarantees).{0,40}(?:remote|DUT).{0,20}(?:memory|storage|persist)',outcome)
            cycle=cycle or owner_cycle
            related_text=' '.join(c['business_text']['steps']+' '+c['business_text']['acceptance'] for c in related)
            return bool(cycle) and all_of(t+' '+p,r'actual|inspected|hardware|variant|appropriate|approved|confirmed',r'stored|mapping|non.volatile|learned',r'again|retest|re.test|verify.{0,40}after|before.{0,40}(?:pairing|relearning|re.learning)|send it again|transmit the learned') and all_of(t+' '+a+' '+o+' '+related_text,r'overwrite|mapping|unrelated key|learned code|learned key|stored code')
        if check=='bt-route':
            intrinsic=all_of(t,r'(?:pointer movement|move.{0,30}(?:remote|pointer)|pointer.{0,25}(?:motion|tracking|sweep)|physical.{0,30}(?:motion|movement))',r'pointer') and all_of(p+' '+t,r'paired|registered|Bluetooth.{0,30}(?:connected|connection)|BT.only')
            if intrinsic and not found(r'pointer.{0,35}(?:absent|unavailable|disappear)|(?:disable|deregister).{0,35}(?:BT|Bluetooth)',t):return True
            return all_of(t,r'pointer|smart',r'(?:operate|verify|confirm|check|test|repeat).{0,90}(?:pointer|smart)|(?:pointer).{0,40}(?:remain|track|move)') and all_of(o+' '+a,r'pointer.{0,70}(?:remain|continue|work|track|available)|(?:Bluetooth|BT).{0,60}(?:unaffected|operation|survive)|(?:results?|response|operation).{0,60}attributable to.{0,15}(?:BT|Bluetooth)') and semantic_check('bt-route',t,t)
        if check=='ir-route':
            return local(case,'ir-negative-control') and all_of(t+' '+p,r'line.of.sight|optical|IR path|IR.only|direct IR emitter|direct.ir|IR window')
        if check=='geometry-series':
            fixed=found(r'(?:hold|keep|fixed|constant).{0,70}(?:distance|angle|orientation|geometry)|(?:distance|angle|orientation|geometry).{0,70}(?:fixed|constant|same|unchanged)|keep.{0,35}(?:pointed|aimed)|(?:aim|point|oriented).{0,25}(?:at|toward).{0,20}(?:host|TV)|keep the same orientation',t+' '+lp+' '+r)
            points=found(r'each.{0,30}(?:distance|point|angle)|per.{0,20}(?:distance|point|angle)|(?:1|one).{0,12}m.{0,70}(?:3|three).{0,12}m',t)
            fixed=fixed or found(r'align.{0,35}(?:remote|DUT).{0,25}target.{0,25}(?:unobstructed )?line.of.sight',t)
            operation=all_of(t,r'pointer movement|pointer move|move the pointer|Volume|Power|(?:basic|defined|same|fixed|learned).{0,30}(?:command|operation)',r'press|send|perform|execute|repeat|operate|move|adjust|invoke',r'count|attempt|trial|\d+ times|record.{0,35}(?:each|every|response|result|command)|record.{0,50}(?:success|failure)')
            learning=found(r'learn.{0,30}(?:distance|spacing)|(?:distance|spacing).{0,30}learn',t) and not found(r'host.{0,40}(?:response|success)',t)
            return bool(fixed and points and operation and not learning)
        if check=='nominal-not-guarantee':
            s=o+' '+a+' '+r
            inherited=' '.join(c['business_text']['steps'] for c in related if found(r'\brepeat\b.{0,30}'+re.escape(str(c['case_key'])),t))
            if not all_of(t+' '+lp+' '+inherited,r'\d\s*m\b|distance point|each distance|each marked distance',r'pointer|Volume|Power|basic|command') or not found(r'operate|perform|press|send|repeat|test|move|adjust',t):return False
            adopted_angle=any(list(adopted_relation(pattern,s)) for pattern in [r'(?:100\s*%).{0,60}(?:30.{0,10}(?:degree|deg)|all angle)',r'(?:normal(?: operation)?|normally).{0,50}60.{0,10}(?:degree|deg)',r'30.{0,12}(?:degree|deg).{0,60}100\s*%'])
            scoped=all_of(s+' '+lp,r'line.of.sight|recorded geometry|aimed|pointed|oriented|angular|angle|orientation',r'loss.{0,25}(?:permitted|tolerat|occasional)|(?:occasional|permitted).{0,25}(?:packet )?loss|not.{0,60}(?:guarantee|100%|universal|all.angle)|does not imply perfect|exploratory|pending|undefined.{0,30}(?:loss|rate)|loss.{0,30}undefined')
            return bool(scoped and found(r'SOP|source|authority|applicab|specification|BFS|\bspec\b|design range',s+' '+p) and not adopted_angle)
        if check=='shortcut-context':
            entitlement=any_of(t+' '+lp,r'entitl|subscription|(?:app|service|Netflix|shortcut).{0,25}account|(?:app|application|service)s?[^.;]{0,45}installed and signed in|(?:app|application|service)s?[^.;]{0,30}(?:sign.in|signed in)|(?:Netflix|Prime|Disney|YouTube)[^.;]{0,65}installed and signed in|corresponding services/apps installed and signed in|account available for launch testing')
            regional=found(r'(?:record|confirm|check|test|applicable).{0,35}(?:region|market)|(?:region|market).{0,35}(?:recorded|confirmed|approved|applies|support)|regional.{0,25}(?:support|availability)|(?:services? (?:are )?available|available services?).{0,35}(?:region|market)|(?:region|market).{0,25}(?:services?|apps?).{0,35}(?:support|available)',t+' '+lp)
            installed=found(r'install|inside.{0,20}(?:Netflix|Disney|Prime)|in Netflix',t+' '+lp)
            return bool(entitlement and regional and installed) and all_of(t+' '+lp,r'(?:physical|fitted|printed|actual|present|label).{0,80}(?:key|button|inventory|icon|shortcut)|(?:key|button).{0,30}(?:present|fitted|inventory)|recorded which shortcut keys exist|records every branded service key',r'key|button|shortcut') and all_of(t,r'app|service|Netflix|shortcut')
        if check=='shortcut-branches':
            related_actions=' '.join(c['business_text']['steps'] for c in related)
            workflow=t+' '+related_actions
            per_key=all_of(t,r'(?:for each|inventory every).{0,35}(?:physical service shortcut|service button|shortcut key|present key|key)',r'installed.{0,30}(?:state|app)|(?:app|service).{0,30}installed',r'press.{0,35}(?:key|service button)',r'shortcut|streaming|dedicated|service')
            app_input=found(r'(?:press|hold|launch).{0,40}(?:Netflix|Prime|Disney|dedicated app|shortcut|service (?:key|button))',t) or per_key
            comparison=all_of(workflow+' '+lp,r'installed',r'not.installed|uninstalled|unavailable.{0,25}(?:app|service)|(?:app|service).{0,25}unavailable') or (per_key and found(r'(?:app.{0,30}absent|app.{0,30}missing|uninstalled).{0,70}|store page.{0,40}(?:absent|missing)',o))
            reset_context=' '.join(clause for clause in relation_clauses(workflow+' '+lp) if not found(r'(?:do not|never).{0,55}(?:Home|starting|reset|restore|common)|Home.{0,35}(?:only|accessible)|only.{0,45}Home.{0,35}accessible|blocked and unblocked|IR|optical barrier',clause))
            reset=found(r'(?:restore|return|reset).{0,40}(?:Home|initial|starting|same).{0,25}(?:screen|state)|(?:Home|initial|starting).{0,25}(?:screen|state).{0,25}between|return home between',reset_context)
            reset=reset or (per_key and found(r'\bfrom\s+(?:the\s+)?Home\b|\bhost\b.{0,20}\bat\b.{0,15}\bHome\b',t+' '+lp)) or (found(r'host at home',lp) and found(r'return to home',t))
            reset=reset or all_of(t,r'from Home',r'return (?:to )?Home')
            return bool(app_input and comparison and reset and all_of(t+' '+o+' '+a,r'store|unavailable|not.installed|missing.app',r'record|observe|verify|check'))
        if check=='launch-endpoint':
            if not found(r'(?:press|actuate|physical).{0,45}(?:Netflix|Prime|Disney|shortcut|dedicated|service.{0,15}(?:key|button))|shortcut key.{0,55}press',t):return False
            interval=found(r'(?:time|interval|latency).{0,35}(?:from )?(?:press|actuation).{0,70}(?:app|application|service).{0,30}(?:foreground|ready|interactive|usable|on.screen)|(?:press|actuation).{0,90}(?:to|until).{0,50}(?:app|application|service).{0,30}(?:foreground|ready|interactive|usable|on.screen)',t)
            interval=interval or all_of(t,r'press.{0,45}(?:service|shortcut).{0,15}key',r'measure.{0,55}usable app screen')
            return bool(interval and all_of(a+' '+r,r'authority|applicab|source|pending|approved|SOP'))
        return False
    components={'hide-wake-endpoints':['hide-clock','wake-clock'],
        'back-exit-depth':['back-component','exit-component'],
        'ui-versus-action':['ui-component','action-component']}
    if key in components:
        evidence=[]
        for component in components[key]:
            matching=[result(c,component) for c in cases if local(c,component)]
            # Components are independent observations.  Keep the evidence that
            # is present so the semantic judge can decide partial completion;
            # one omitted endpoint must not erase the other endpoint before
            # semantic adjudication.
            evidence.extend(matching)
        return evidence
    if key=='ir-negative-control':
        evidence=[result(c) for c in cases if local(c,key)]
        if evidence:return evidence
        def command_set(case):
            text=case['business_text']['steps']+' '+case['business_text']['expected']
            commands=set()
            if found(r'Volume',text):commands.add('volume')
            if found(r'Power',text):commands.add('power')
            if found(r'basic (?:key|button|command|control)',text):commands.add('basic')
            return commands
        opened=[];blocked=[]
        for case in cases:
            if not local(case,'bt-absent'):continue
            t=case['business_text']['steps'];outcome=case['business_text']['expected']+' '+case['business_text']['acceptance']
            commands=command_set(case)
            if commands and all_of(t,r'\bIR\b|infrared',r'open|unobstruct|line.of.sight|without.{0,25}(?:block|cover)') and found(r'respond|works?|action|control',outcome):
                opened.append((case,commands))
            if commands and all_of(t,r'\bIR\b|infrared',r'block|cover|occlud|opaque') and found(r'(?:no|not|none|stop|does not).{0,80}(?:response|action|effect|control|work)',outcome):
                blocked.append((case,commands))
        pairs=[(a,b) for a,ac in opened for b,bc in blocked if a is not b and ac&bc]
        if pairs:
            selected={case['case_key']:case for pair in pairs for case in pair}
            return [result(case,'complementary-open-blocked-control') for case in selected.values()]
        return []
    if key=='risk-priority':
        def rank(value):
            value=str(value or '')
            numbered=re.search(r'\bP\s*([0-4])\b',value,re.I)
            if numbered:return int(numbered.group(1))
            named=re.search(r'\b(critical|urgent|high|medium|moderate|low)\b',value,re.I)
            return {'critical':0,'urgent':0,'high':1,'medium':2,'moderate':2,'low':3}.get(named.group(1).lower()) if named else None
        ranked=[(case,rank(case['fields'].get('priority'))) for case in cases]
        if not ranked or any(value is None for _,value in ranked) or len({value for _,value in ranked})<2:return []
        consequence=[];routine=[]
        for case,value in ranked:
            text=' '.join(case['fields'].get(role,'') for role in ['category','objective','steps','expected','acceptance'])
            (consequence if found(r'fallback|pair(?:ing)?|binding|power[ -]cycle|unsafe|primary control|motion.to.pointer|click endpoint',text) else routine).append((case,value))
        if not consequence or not routine or min(value for _,value in consequence)>=max(value for _,value in routine):return []
        selected=[case for case,value in consequence if value==min(v for _,v in consequence)]
        selected += [case for case,value in routine if value==max(v for _,v in routine)]
        return [result(case,'consequence-and-dependency-order') for case in selected]
    if key=='pair-endpoints':
        evidence=[result(c) for c in cases if local(c,key)]
        # Complementary pairing procedures may supply separate events. Do not
        # require a separate timestamp for every LED state: the public relation
        # asks that indication, registration and usable control remain distinct.
        pairing=[c for c in cases if all_of(c['business_text']['steps'],
            r'\b(?:press|release)\b.{0,45}\b(?:OK|wheel)\b',
            r'pair|register|registration|unpaired')]
        clocks=[c for c in pairing if all_of(c['business_text']['steps'],
            r'(?:start|record|time).{0,45}(?:stopwatch|timer|press)',
            r'(?:stop|record|time).{0,85}(?:registration|confirmation)',
            r'pointer.{0,45}(?:usable|respond|track|available)|(?:move|check|verify|confirm).{0,55}pointer')]
        indications=[c for c in pairing if all_of(c['business_text']['steps'],
            r'(?:observe|record).{0,70}LED',
            r'LED.{0,40}(?:state|sequence|behavio)|(?:sequence|state).{0,30}LED')]
        if clocks and indications:
            evidence.extend(result(c,'trigger-registration-usable-control') for c in clocks)
            evidence.extend(result(c,'pairing-indication-sequence') for c in indications)
        return evidence
    if key=='pair-authority':
        evidence=[result(c) for c in cases if local(c,key)]
        def starts_pair_clock(case):
            steps=re.split(r'\b\d{1,2}\.\s+|\n',case['business_text']['steps'])
            for i,step in enumerate(steps):
                if found(r'\b(?:press|release)\b.{0,50}\b(?:OK|wheel)\b|\b(?:OK|wheel)\b.{0,40}\b(?:press|release)\b',step):
                    clock=step+' '+(steps[i+1] if i+1<len(steps) else '')
                    if found(r'(?:start|record|measure|time).{0,45}(?:stopwatch|timer|timing|elapsed)|start.{0,40}(?:press|release)|(?:press|release).{0,45}start.{0,30}stopwatch',clock):return True
            return False
        # Explicit completion and deliberately unsuccessful timeout experiments
        # can be separate rows; each retains its own endpoint and source scope.
        completion=[c for c in cases if found(r'\bpress\b.{0,50}\b(?:OK|wheel)\b',c['business_text']['steps']) and all_of(c['business_text']['steps']+' '+c['business_text']['expected'],r'\b(?:unpaired|pairing|registration|register|registered)\b',r'complet|confirm') and all_of(c['business_text']['acceptance']+' '+c['business_text']['remarks'],r'SOP|source|authority|approved|pending|scope',r'complet|confirm')]
        def timeout_trial(c):
            v=c['business_text'];steps=v['steps']
            attempted=all_of(steps,r'\bpress\b.{0,50}\b(?:OK|wheel)\b',r'wait|observe|time|stopwatch',r'pair|register|registration|advertis')
            prevented=found(r'non.responsive|cannot acknowledge|(?:host|TV).{0,40}(?:off|disabled)|advertis.{0,35}stop|stop.{0,35}advertis|no (?:TV|host).{0,30}(?:available|confirm)|without.{0,35}(?:host|TV).{0,25}(?:response|acknowledg)',steps+' '+v['resolved_preconditions'])
            # A timeout source note or an initial unpaired state alone is not
            # an observed unsuccessful terminal event in this experiment.
            terminal=any(all_of(clause,r'times?\s*out|timeout|search ends|no (?:TV|host).{0,25}confirms?',r'returns?.{0,35}unpaired|exits?.{0,35}unpaired|(?:times?\s*out|search ends).{0,60}(?:unpaired|no unintended|no false success)|unsuccessful terminal') for clause in relation_clauses(v['expected']+' '+v['acceptance']))
            terminal=terminal or (found(r'until.{0,40}(?:stops?|ceases?).{0,20}advertis',steps) and all_of(v['expected']+' '+v['acceptance'],r'timeout',r'returns?.{0,35}unpaired'))
            return bool(attempted and prevented and terminal)
        timeout=[c for c in cases if timeout_trial(c)]
        if completion and timeout:
            evidence.extend(result(c,'completion-clock') for c in completion)
            evidence.extend(result(c,'timeout-clock') for c in timeout)
        return evidence
    if key=='press-context':
        evidence=[result(c) for c in cases if local(c,key)]
        for actor in ['Settings','Back','OK','Home','Exit','Input']:
            actuator=r'\s*(?:\([^)]*\)\s*)?(?:the\s+)?'+actor+r'\b'
            def home(c):return found(r'from (?:the )?Home (?:screen|dashboard)|host.{0,20}at Home (?:screen|dashboard)|TV On - Home',c['business_text']['steps']+' '+c['business_text']['resolved_preconditions'])
            short=[c for c in cases if home(c) and any(found(r'\bshort.press'+actuator,clause) and not found(r'\b(?:long.press|hold)'+actuator,clause) for clause in relation_clauses(c['business_text']['steps'])) and not found(r'\b(?:long.press|hold)'+actuator,c['business_text']['steps'])]
            long=[c for c in cases if home(c) and all_of(c['business_text']['steps'],r'(?:long.press|hold)'+actuator,r'\d|timed|duration|time the hold')]
            if short and long:
                evidence.extend(result(c,'same-key-short-from-Home') for c in short)
                evidence.extend(result(c,'same-key-long-from-Home') for c in long)
        return evidence
    if key=='power-timer-distinction':
        if any(business_damage('false-electrical-state',c) for c in cases):return []
        evidence=[result(c) for c in cases if local(c,key)]
        pointer=[c for c in cases if all_of(c['business_text']['steps'],r'pointer',r'hide|idle|still',r'time|record|measure')]
        current=[c for c in cases if all_of(c['business_text']['steps'],r'remote|DUT',r'(?:measure|record).{0,40}(?:series )?current',r'current.{0,70}(?:sleep|over time|idle|inactivity)|(?:sleep|idle|inactivity).{0,70}current') and all_of(c['business_text']['steps']+' '+c['business_text']['local_preconditions'],r'meter|current probe|supply',r'series|measure')]
        if pointer and current:
            evidence.extend(result(c,'pointer-visibility-clock') for c in pointer)
            evidence.extend(result(c,'independent-current-sleep') for c in current)
        return evidence
    if key=='shortcut-branches':
        evidence=[result(c) for c in cases if local(c,key)]
        def app_input(c):return found(r'\bpress\b.{0,50}(?:Netflix|Disney|Prime|shortcut|dedicated.?service)',c['business_text']['steps'])
        def start(c):
            source=c['business_text']['resolved_preconditions']+' '+c['business_text']['steps']
            return any(found(r'\b(?:from|at)\b.{0,12}\bHome\b(?: screen| dashboard)?|(?:same|stated|recorded|known|initial|starting).{0,30}(?:screen|state)',clause) for clause in relation_clauses(source) if not found(r'(?:do not|never).{0,55}(?:Home|starting|reset|restore|common)|Home.{0,35}accessible',clause))
        installed=[c for c in cases if app_input(c) and start(c) and found(r'installed',c['business_text']['local_preconditions']) and not found(r'not.installed|uninstalled',c['business_text']['local_preconditions'])]
        absent=[c for c in cases if app_input(c) and start(c) and found(r'uninstall|not.installed|disable.{0,30}(?:app|service)',c['business_text']['steps']+' '+c['business_text']['local_preconditions']) and found(r'store|unavailable|missing.app',c['business_text']['expected']+' '+c['business_text']['acceptance'])]
        for missing in absent:
            generic=found(r'corresponding.{0,25}(?:shortcut|service|dedicated)|one.{0,30}shortcut app',missing['business_text']['steps']+' '+missing['business_text']['local_preconditions'])
            names=set(re.findall(r'Netflix|Disney|Prime',missing['business_text']['steps']+' '+missing['business_text']['local_preconditions'],re.I))
            same=[c for c in installed if c is not missing and (generic or names&set(re.findall(r'Netflix|Disney|Prime',c['business_text']['steps'],re.I)))]
            if same:evidence.extend([result(missing,'uninstalled-branch')]+[result(c,'installed-branch') for c in same])
        for app in ['Netflix','Disney','Prime','dedicated app','shortcut app']:
            installed=[c for c in cases if all_of(c['business_text']['steps'],app,r'from Home|from the Home|(?:restore|return).{0,30}Home',r'press|launch')]
            absent=[c for c in cases if all_of(c['business_text']['steps']+' '+c['business_text']['local_preconditions'],app,r'uninstall|disable.{0,30}(?:app|service)|not.installed',r'press|launch') and found(r'store|missing.app|unavailable',c['business_text']['expected']+' '+c['business_text']['acceptance']) and found(r'(?:restore|return|reset).{0,35}(?:Home|initial|starting).{0,20}(?:screen|state)|reset.{0,35}initial state.{0,30}between',c['business_text']['steps']+' '+c['business_text']['preconditions'])]
            if installed and absent:
                evidence.extend(result(c,'installed-branch') for c in installed)
                evidence.extend(result(c,'uninstalled-branch') for c in absent)
        return evidence
    if key=='nominal-not-guarantee':
        # A nominal design range does not affirm a hard failure boundary. This
        # public qualification governs the submitted range conclusions together.
        for c in cases:
            t,p,o,a,r,m,b=data(c)
            if not all_of(t,r'\d\s*m\b|distance',r'IR|infrared',r'press|perform|send|repeat|operate'):continue
            hard=r'(?:beyond|outside|over).{0,20}\d+\s*m.{0,45}(?:IR.{0,20}(?:is )?(?:lost|fails?|ceases)|loss of IR)|IR.{0,25}(?:control|operation)?.{0,25}(?:loss|lost|fails?).{0,35}beyond.{0,20}\d+\s*m'
            if any(list(adopted_relation(hard,s)) for s in [o,a]):return []
    return [result(c) for c in cases if local(c,key)]


NEW_BUSINESS_LEAVES={
    'wheel-inertia','audio-external-state','pointer-restored-location',
    'guide-tune','offline-cloud-branch',
    'bt-distance-ledger','ir-distance-ledger','volume-clamp','audio-audible',
    'cec-positive-ir-blocked'}


def relation_clauses(text):
    return [s.strip() for s in re.split(r'\b\d{1,2}[.)]\s+|(?<=[.!?;])\s+(?=[a-z])|\s+-\s+(?=the |an? |it )',text) if s.strip()]


def adopted_relation(pattern,text):
    """Match an affirmative local clause, including postposed scope denials."""
    for clause in relation_clauses(text):
        if re.search(r'for comparison only|describes? a rejected|quoted (?:alternative|claim)|hypothetical',clause,re.I):continue
        for match in re.finditer(pattern,clause,re.I):
            if not affirmative(clause,match):continue
            after=clause[match.end():]
            if re.search(r'^.{0,65}\b(?:is|are|was|were|remains?)\s+(?:not (?:required|observed|measured|tested|performed)|untested|unmeasured|out of scope)',after,re.I):continue
            if re.search(r'^.{0,35}\b(?:does not govern|do not govern|intentionally not tested)\b',after,re.I):continue
            yield clause,match


def new_business_evidence(key,cases):
    """Bind operative experiment objects and observations by their field roles.

    A conditional repeat inherits the explicit actions it repeats. Document
    citations and source registers never supply an absent experiment.
    """
    def f(pattern,text):return bool(list(adopted_relation(pattern,text)))
    def all_of(text,*patterns):return all(f(p,text) for p in patterns)
    def audible_workflow(case):
        t=case['business_text']['steps'];linked=[]
        if f(r'repeat',t) and f(r'external|soundbar|AVR',t):
            for other in cases:
                ident=str(other['case_key'])
                if ident.upper() not in case.get('related_case_keys',[]):continue
                if re.search(r'\brepeat\s+'+re.escape(ident)+r'\b',t,re.I):
                    linked.append(other);t+=' '+other['business_text']['steps']
        return t,linked
    def matching(case):
        v=case['business_text']
        t,p,o,a,r=(v[k] for k in ['steps','resolved_preconditions','expected','acceptance','remarks'])
        lp=v['local_preconditions']
        outcome=o+' '+a
        if key=='wheel-inertia':
            return all_of(t,r'wheel|scroll',r'release|let go',r'rapid|flick|fast|brisk',r'observe|record|confirm|check|capture') and all_of(t+' '+outcome,r'inertia|inertial|continues? (?:to )?(?:slide|scroll|smoothly)|continuation|post.release (?:motion|movement)',r'decelerat|smooth.{0,30}stop|gradual.{0,30}stop')
        if key=='audio-external-state':
            endpoint_pattern=r'(?:observe|observing|record|confirm|check|verify|compare).{0,65}(?:external|soundbar|AVR|audio receiver|audio.device).{0,45}(?:volume|mute|level|state|display)|(?:volume|mute|level).{0,35}(?:on|of|at).{0,20}(?:external|soundbar|AVR)|record.{0,100}audible output at the selected endpoint|observe which device.{0,25}volume changes'
            endpoint=any(not re.search(r'OSD.{0,30}(?:reflects|shows|reports).{0,30}(?:external|soundbar|AVR)',match.group(0),re.I) or re.search(r'own|directly|actually',match.group(0),re.I) for _,match in adopted_relation(endpoint_pattern,t))
            endpoint=endpoint or (all_of(t,r'select.{0,35}(?:external|soundbar|AVR).{0,30}(?:sound output|audio)|select.{0,25}(?:HDMI.CEC )?(?:soundbar|AVR)',r'(?:compare|observe|verify|record).{0,35}physical device state',r'Volume|Mute'))
            # The endpoint must actually change/produce sound; generic menu,
            # input, cross-control or receiver-response observations do not
            # become an audio-volume experiment through global setup words.
            target_change=all_of(t,r'adjust.{0,20}(?:its|soundbar|external).{0,20}volume',r'verify.{0,45}external device state')
            return all_of(t+' '+lp,r'external|soundbar|AVR|audio receiver',r'volume|mute',r'CEC|IR|infrared') and (endpoint or target_change)
        if key=='pointer-restored-location':
            comparison=f(r'(?:compare|confirm|check|verify|record).{0,130}(?:last|previous|original|before.hide|recorded|noted).{0,50}(?:location|coordinates|position)|(?:confirm|check).{0,25}restored pointer location|(?:return\w*|restor\w*).{0,50}(?:last|previous|original).{0,30}(?:location|coordinates|position)|record where.{0,40}reappears relative to.{0,30}noted position',t)
            expected=f(r'(?:restor|return).{0,80}(?:last|previous|original).{0,30}(?:coordinates|location|position)',outcome) and f(r'(?:confirm|check|record).{0,100}(?:return|reappear)|(?:return|reappear).{0,60}(?:check|record)',t)
            return all_of(t,r'pointer|cursor',r'hid(?:e|ing|den)|disappear|deactivate|no longer rendered',r'shak\w*|wake motion|move the remote') and (comparison or expected)
        if key=='guide-tune':
            selection=all_of(t,r'(?:guide|EPG|channel.list|listed channel|within (?:the )?list|from (?:the )?list)',r'(?:select|switch|change|tune).{0,80}(?:different|another|other|channel)|(?:different|another|listed).{0,40}channel.{0,60}(?:select|switch|tune)|channels? can be switched from (?:the )?list')
            # Reopening Guide after an unrelated channel change tests highlighting.
            if f(r'change channel.{0,25}re.open',t) and not f(r'(?:from|within|through).{0,25}(?:guide|list)',t):return False
            return selection and f(r'(?:confirm|verify|check|observe).{0,65}(?:actual )?tun|confirm the actual programme|(?:confirm|verify).{0,50}(?:channel|switch).{0,30}takes effect|(?:selected|chosen).{0,40}channel.{0,40}(?:tun|becomes active)|channels? (?:can be |are )?(?:switched|changed)|channel selection (?:works|changes)',t+' '+outcome)
        if key=='offline-cloud-branch':
            offline=False
            # A named offline trial can inherit its actually selected command
            # population. An isolated outcome-recording instruction cannot
            # create either that population or an issued cloud request.
            classified=f(r'classif\w*.{0,100}(?:local|network.dependent|cloud).{0,100}commands?',t)
            command_trial=f(r'\buse\b.{0,35}(?:controlled|fixed|selected).{0,30}command|\b(?:speak|say|issue|execute|try|test|repeat)\b.{0,70}(?:command|request|query)',t)
            for clause in relation_clauses(t):
                if f(r'(?:disconnect|remove|disable).{0,50}(?:network|Wi.Fi|Ethernet|WAN)|network.{0,25}(?:removed|disconnected)|offline (?:trial|attempts?)|while still offline',clause):offline=True
                if f(r'(?:restore|reconnect).{0,35}(?:network|Wi.Fi|Ethernet|WAN)',clause):offline=False
                if offline and f(r'(?:issue|execute|speak|say|send|submit|try|test|verify|repeat).{0,60}(?:cloud|network.only query|online information (?:request|query))',clause):return True
                if offline and classified and command_trial and f(r'record unavailable cloud behavior',clause):return True
            return False
        if key in ['bt-distance-ledger','ir-distance-ledger']:
            distance=f(r'\d+\s*,\s*\d+.{0,35}\bm\b|each (?:chosen |marked )?distance|distance points?|each point',t) or all_of(t,r'\b(?:1|one)\s*m\b',r'\b(?:3|three|5|five|8|eight|10|ten)\s*m\b')
            counted=all_of(t,r'(?:\d+|ten|twenty|N)\s*(?:(?:defined|supported) )?(?:trials?|attempts?|presses|operations?|cycles?|basic.key commands?|pointer moves?|pointer movements?|pointer trajectories|pointer sweeps|Volume)|(?:\d+|ten|twenty).{0,20}(?:times|alternations)|at least \d+ operations|(?:same|fixed).{0,80}(?:number|count)',r'record|count|log|report')
            # An enumerated action set fixes its own population (one per listed
            # action is sufficient). No minimum repeat count is published.
            enumerated=all_of(t,r'pointer movement|pointer move|move the pointer|press power',r'volume',r'channel',r'perform|press|adjust|send')
            retained=f(r'record.{0,100}(?:each|every|per|at each).{0,30}(?:distance|action|command|response)|each distance.{0,100}record',t)
            attempts=counted or (enumerated and (retained or all_of(t,r'record the response',r'repeat at|repeat the identical|same.{0,35}(?:script|set)')))
            repeated=f(r'each (?:marked |chosen |[\d, .and]+)?(?:point|position|distance)|per (?:action and )?distance|at every distance|repeat.{0,90}(?:3|three).{0,70}(?:5|five)|identical (?:set|script).{0,90}(?:3|three)',t)
            if not(distance and attempts and repeated):return False
            if key=='bt-distance-ledger':
                physical=f(r'(?:perform|execute|repeat|make|send|issue).{0,140}pointer (?:move|movement|motion|target acquisition|trajector|sweep)|move (?:the )?(?:physical )?remote|move the pointer',t) or all_of(t,r'operate remote at marked',r'at each distance.{0,30}pointer movement')
                return physical and all_of(t,r'pointer',r'respon\w*|success|fail|outcome|result|count|attempt|observed|loss') and (f(r'paired|registered|pairing verified|Bluetooth.{0,30}(?:connect|route)|pointer.{0,20}(?:active|visible)|verify (?:BT|Bluetooth).{0,40}(?:pointer|IR)',p+' '+t) or all_of(t+' '+p,r'pointer movement|move the pointer',r'line.of.sight|pointed at|aimed at'))
            if re.search(r'keep Bluetooth connected|Bluetooth remains connected.{0,40}can carry',t+' '+lp,re.I):return False
            isolated=f(r'confirm.{0,30}IR.only state|(?:Bluetooth|BT).{0,30}(?:deregister|unavailable|disabled|off|disconnected|absent)|deregister.{0,30}(?:Bluetooth|BT)',t+' '+lp)
            return isolated and all_of(t,r'Volume|Power|basic',r'respon[ds]|success|fail|outcome|result|count') and not f(r'learned.{0,50}(?:device|target|command)',t)
        if key=='volume-clamp':
            high_endpoint=r'maximum|\bmax\b|\b100\b|upper limit'
            low_endpoint=r'minimum|\bmin\b|(?<![\d.])0(?![\d.])|lower limit'
            endpoints=all_of(t,r'volume|\bUp\b|\bDown\b',high_endpoint,low_endpoint)
            # Negating overflow/wrap affirms a clamp; it is not a denied clamp.
            clamp=f(r'stop|clamp|rather than wrapping|respects?.{0,35}bounds',outcome) or bool(re.search(r'(?:does? not|do not|must not|never)\s+(?:exceed|wrap)|no wrapping|not below|no (?:value|level|volume).{0,15}exceeds?',outcome,re.I))
            bounds=[part for clause in relation_clauses(outcome) for part in re.split(r'\b(?:and|but|while)\b',clause,flags=re.I)]
            high_clamp=any(re.search(r'maximum|\bmax\b|\b100\b',clause,re.I) and re.search(r'stop|clamp|not exceed|no wrap|rather than wrapping',clause,re.I) for clause in bounds)
            low_clamp=any(re.search(r'minimum|\bmin\b|(?<![\d.])0(?![\d.])',clause,re.I) and re.search(r'stop|clamp|not below|no wrap|rather than wrapping',clause,re.I) for clause in bounds)
            bounded=(high_clamp and low_clamp) or (clamp and f(r'boundaries|each limit|both limits|between 0 and 100|0.?100 (?:range|bound|limit)',outcome))
            bounded=bounded or bool(re.search(r'no (?:value|level|volume).{0,20}exceeds?.{0,35}(?:displayed )?0\s*[-–]\s*100\s*(?:limits?|bounds?|range)',outcome,re.I))
            direction=None;reached=set()
            for clause in relation_clauses(t):
                if f(r'Volume\s*(?:Up\b|\+)',clause):direction='up'
                if f(r'Volume\s*(?:Down\b|-)',clause):direction='down'
                if f(r'volume up/down|volume up and down',clause):direction='both'
                high=f(high_endpoint,clause);low=f(low_endpoint,clause)
                if direction=='up' and high:reached.add('up')
                if direction=='down' and low:reached.add('down')
                if direction=='both' and high:reached.add('up')
                if direction=='both' and low:reached.add('down')
                if all_of(clause,r'Up',r'Down',r'maximum|\bmax\b|\b100\b',r'minimum|\bmin\b|\b0\b'):reached.update(['up','down'])
            if all_of(t,r'Volume Up',r'Volume Down',r'repeat.{0,35}(?:at|for|until).{0,25}(?:0|minimum|100|maximum).{0,25}(?:100|maximum|0|minimum)'):
                reached.update(['up','down'])
            actual=reached=={'up','down'}
            return actual and endpoints and bounded
        if key=='audio-audible':
            t,linked=audible_workflow(case)
            external=all_of(t+' '+p,r'external|soundbar|AVR|audio receiver|CEC',r'volume|mute')
            direct=all_of(t,r'observe|confirm|verify|check|record|measure',r'listen|audible|\baudio\b(?![ -]device.{0,25}display).{0,35}(?:silenc|restor)|(?:silenc|restor).{0,35}\baudio\b|\bsound\b.{0,35}(?:silenc|restor)|(?:silenc|restor).{0,35}\bsound\b')
            repeat=f(r'(?:external|CEC|soundbar|AVR|audio output).{0,100}repeat|repeat.{0,100}(?:external|CEC|soundbar|AVR|audio output)',t)
            audible=f(r'\baudio\b.{0,35}(?:silenc|restor)|(?:silenc|restor).{0,35}\baudio\b|audible|\bsound\b.{0,35}(?:silenc|restor)',t+' '+outcome)
            repeat=repeat and not f(r'disable CEC.{0,40}repeat|repeat one (?:DUT|negative|control) input',t)
            limited_repeat=f(r'repeat steps?\s*\d+\s*[-–]\s*\d+|repeat one volume|repeat step\s*\d+|repeat only.{0,50}(?:OSD|display)',t)
            external_direct=direct and f(r'(?:listen|measure|observe|confirm|verify|record).{0,100}(?:external.{0,25}(?:\baudio\b(?![ -]device)|\bsound\b)|selected endpoint)|(?:external|soundbar|AVR).{0,70}(?:silence|audible|\bsound\b|audio output)',t)
            return external and (external_direct or (repeat and audible and not limited_repeat))
        if key=='cec-positive-ir-blocked':
            # Resolved setup contains only explicitly invoked setup rows. Its
            # enabled route is a trial condition, unlike unreferenced globals.
            operative_setup=p
            s=t+' '+operative_setup
            blocked=f(r'(?:block|cover|occlud|obstruct).{0,35}\b(?:IR|infrared)\b|\b(?:IR|infrared)\b.{0,35}(?:blocked|covered|occluded|disabled|obstructed)|disable.{0,40}\b(?:IR|infrared)\b',s)
            active=f(r'\bCEC\s+(?:is\s+|mode\s+)?(?:enabled\b|on\b(?!\s+(?:the|a|an)\b))|\benabl(?:e|ed)\b.{0,30}(?:CEC|SIMPLINK)|\b(?:select|set|verify)\b.{0,70}(?:CEC|System Audio)|\bexercise HDMI.CEC|CEC.{0,35}(?:should still arrive|delivered command still arrives)|HDMI.CEC.{0,30}(?:system audio|route)',s+' '+outcome)
            ir_restore=r'(?:remove|unblock)\s+(?:the\s+)?(?:IR|infrared|barrier|obstruction)|restore\s+(?:the\s+)?(?:IR|infrared)\s+(?:path|route)|IR.{0,25}(?:open again|unblocked)'
            # Track the route in operation order. An earlier enabled trial or a
            # hypothetical CEC response cannot supply a later disabled trial.
            # The parser resolves only operative references in this case's
            # prerequisites. Such a setup supplies initial trial conditions;
            # its invocation need not repeat a particular "first/maintain" form.
            resolved_setup=case.get('resolved_setup','')
            cec_state=None;ir_state=f(r'(?:block|cover|occlude|obstruct|disable).{0,40}\b(?:IR|infrared)\b|\b(?:IR|infrared)\b.{0,35}(?:blocked|covered|occluded|disabled)',resolved_setup)
            if f(r'(?:with|while).{0,20}\bIR\b.{0,20}(?:blocked|covered|occluded|disabled)',lp):ir_state=True
            active_blocked_command=False
            if f(r'CEC.{0,25}(?:enabled|on)|SIMPLINK.{0,25}enabled|enable.{0,20}(?:CEC|SIMPLINK)|select.{0,35}CEC.{0,35}(?:system audio|audio)|System Audio.{0,25}(?:enabled|on)',operative_setup):cec_state=True
            if f(r'disable.{0,25}(?:CEC|SIMPLINK)|(?:CEC|SIMPLINK).{0,25}(?:disabled|off)',lp):cec_state=False
            if re.search(r'(?:original|restored).{0,30}(?:CEC|SIMPLINK).{0,35}(?:unknown|not established)|(?:CEC|SIMPLINK).{0,60}(?:retained as unknown|not been established as enabled)|keep it disabled throughout|disabled throughout',lp,re.I):cec_state=None
            if f(r'\bIR\b.{0,70}(?:blocked|disabled|occluded)|all IR routes disabled|IR paths disabled',lp):ir_state=True
            if f(ir_restore+r'|\bIR\b.{0,25}(?:open|unobstructed)',lp):ir_state=False
            original_cec_state=cec_state
            # A route-state event needs an actual device input. In particular,
            # repeating setup inspection cannot borrow a later Volume command.
            # Resolve repeats from the preceding command or an explicit step
            # reference rather than accepting the repetition verb by itself.
            input_object=r'(?:Power|Volume|Mute|command|key|button)\b'
            def explicit_input(segment):
                return f(r'^(?:press|send|issue|re.issue|resend)\b.{0,65}'+input_object+r'|^hold\s+(?:the\s+)?(?:Power|Volume|Mute|(?:(?:remote|DUT)\s+)?(?:key|button))\b|^exercise HDMI.CEC|^operate\b.{0,25}(?:remote|DUT)\b|^confirm\b.{0,30}CEC.{0,35}command works',segment)
            numbered_inputs={}
            for numbered in re.finditer(r'(?:^|\s)(\d{1,2})[.)]\s+(.*?)(?=\s+\d{1,2}[.)]\s+|$)',t,re.S):
                body=numbered.group(2)
                numbered_inputs[int(numbered.group(1))]=any(explicit_input(body[match.start():]) for _,match in adopted_relation(r'\b(?:press|hold|send|issue|re.issue|resend|exercise|operate|confirm)\b',body))
            preceding_input=False
            input_route=None
            ongoing_input=False
            expected_response=all_of(outcome,r'CEC|external|soundbar|AVR|device|target',r'respond|response|change|control|mute|volume|power|establish.{0,20}route')
            for clause in relation_clauses(t):
                during_input=f(r'\bduring\s+(?:(?:the|this|same)\s+)?command\b|\bwhile\b.{0,40}(?:key|button|command|input).{0,25}(?:held|being sent|being transmitted)',clause)
                # Multiple transitions in one sentence retain their textual
                # order. A fixed enable-then-disable rule changes the meaning
                # of "disable CEC, then enable CEC".
                events=[]
                original_matches=list(adopted_relation(r'restore.{0,20}(?:CEC|SIMPLINK).{0,35}original (?:state|setting)',clause))
                patterns=[('cec',True,r'\benable\b.{0,30}(?:CEC|SIMPLINK)|\b(?:CEC|SIMPLINK)\b.{0,25}(?:enabled|re.enabled)|select.{0,35}CEC.{0,35}(?:system audio|audio)|(?:System Audio|Power Link).{0,20}enabled|enable.{0,35}power.link|verify CEC System Audio mode|\bexercise HDMI.CEC'),('cec',False,r'\bdisable\b.{0,30}(?:CEC|SIMPLINK)|\b(?:CEC|SIMPLINK)\b.{0,25}(?:disabled|off)'),('ir',True,r'\b(?:block|cover|occlude|obstruct|disable)\b.{0,40}\bIR\b|\bIR\b.{0,30}(?:blocked|covered|occluded|disabled)'),('ir',False,ir_restore)]
                for route,state,pattern in patterns:
                    for _,match in adopted_relation(pattern,clause):events.append((match.start(),0,route,state))
                for _,match in original_matches:events.append((match.start(),0,'cec',original_cec_state))
                for _,match in adopted_relation(r'restore.{0,20}(?:CEC|SIMPLINK)',clause):
                    if not any(m.start()==match.start() for _,m in original_matches) and not re.search(r'unknown',clause[match.start():match.end()+35],re.I):events.append((match.start(),0,'cec',True))
                if not re.search(r'\b(?:would|could|hypothetical)\b',clause,re.I):
                    for _,match in adopted_relation(r'\b(?:press|hold|send|issue|repeat|resend|re.issue|exercise|operate|confirm)\b',clause):
                        segment=re.split(r'\bthen\b|,\s*(?=(?:enable|disable|block|unblock|restore|remove|press|hold|send|repeat|resend|operate)\b)',clause[match.start():],maxsplit=1,flags=re.I)[0]
                        events.append((match.start(),1,'command',segment))
                for _,match in adopted_relation(r'(?:confirm|observe|record|verify).{0,70}\bresponse\b|establish.{0,25}route',clause):events.append((match.start(),1,'observation',None))
                for _,match in adopted_relation(r'\brelease\b|\b(?:command|input)\b.{0,25}(?:has finished|has ended|is complete|has completed)|\bstop\b.{0,20}(?:sending|transmitting)',clause):events.append((match.start(),2,'input-end',None))
                for event_position,_,route,state in sorted(events,key=lambda event:event[:2]):
                    if route=='cec':cec_state=state
                    elif route=='ir':ir_state=state
                    elif route=='input-end':ongoing_input=False
                    else:
                        if route=='command':
                            representative=explicit_input(state)
                            if re.match(r'repeat\b',state,re.I):
                                refs=[int(n) for n in re.findall(r'\bstep\s+(\d+)\b',state,re.I)]
                                step_repeat=any(numbered_inputs.get(n,False) for n in refs)
                                command_repeat=bool(re.match(r'repeat\s+(?:(?:the|a|one)\s+)?(?:(?:same|identical|previous|DUT|LG.remote)\s+)*(?:commands?|inputs?|(?:volume|power|mute)(?:\s+commands?)?)\b',state,re.I))
                                implicit_repeat=bool(re.match(r'repeat\s*(?:[.!?]?\s*$|(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:times?|(?:enabled\s+)?trials?)\b|(?:as|with|while|to)\b)',state,re.I))
                                representative=step_repeat or (preceding_input and (command_repeat or implicit_repeat))
                            if not representative:continue
                        # A postfix condition belongs to this command, up to
                        # the next sequenced operation. Prefix conditions have
                        # already updated state in textual order and cannot
                        # override a later unblock/disable before this command.
                        command_condition=re.split(r'\bthen\b|,\s*(?=(?:enable|disable|block|unblock|restore|remove|press|hold|send|repeat|resend|operate)\b)',clause[event_position:],maxsplit=1,flags=re.I)[0]
                        command_cec=cec_state;command_ir=ir_state
                        if route=='command':
                            if f(r'(?:with|while).{0,25}\b(?:IR|infrared)\b.{0,20}(?:blocked|covered|occluded|disabled)',command_condition):command_ir=True
                            if f(r'(?:with|while).{0,25}\b(?:CEC|SIMPLINK)\b.{0,20}(?:enabled|on)',command_condition):command_cec=True
                            if f(r'(?:with|while).{0,25}\b(?:CEC|SIMPLINK)\b.{0,20}(?:disabled|off)',command_condition):command_cec=False
                            preceding_input=True
                            input_route=(command_cec,command_ir)
                            ongoing_input=f(r'\bhold\b|\bcontinuously\b|\bkeep\b.{0,25}(?:held|sending|transmitting)',command_condition)
                        elif not (preceding_input and (ongoing_input or during_input)):
                            # A later observation belongs to the actual input's
                            # route snapshot, not a new setup phase. Historical
                            # inputs remain available for explicit repeats, but
                            # do not become new commands merely by observing.
                            command_cec,command_ir=input_route or (None,False)
                        local_response=all_of(command_condition,r'observ\w*|confirm|verify|record|check|establish',r'respon\w*|external|soundbar|AVR|target|device|CEC|route')
                        if preceding_input and command_cec is True and command_ir and (local_response or expected_response):active_blocked_command=True
            phase_ok=active_blocked_command
            negative_only=cec_state is False and not active_blocked_command
            direct=not negative_only and phase_ok and blocked and (active or active_blocked_command) and all_of(t,r'Power|Volume|Mute|command|exercise',r'observ\w*|confirm|verify|record|check|establish') and all_of(t+' '+outcome,r'CEC|external|soundbar|AVR',r'respond|change|control|mute|volume|power|establish.{0,20}route')
            paired_routes=blocked and all_of(s,r'CEC',r'IR',r'(?:all|both) routes.{0,30}(?:active|available)',r're.enable.{0,30}(?:SIMPLINK|CEC)|restore route a.{0,50}disable route b',r're.issue|resend',r'record') and all_of(outcome,r'matrix|one disabled|single.route',r'consistent route attribution|continues?|continuing|remaining route',r'both.{0,30}(?:disabled|blocked)|all.{0,30}disabled')
            return direct or (paired_routes and phase_ok)
        return False
    result=[]
    for case in cases:
        if not matching(case):continue
        loc=[case['locators'][r] for r in ['steps','preconditions','expected','acceptance'] if case['fields'].get(r)]
        loc+=case.get('shared_setup_locators',[])
        if key=='audio-audible':loc += [c['locators']['steps'] for c in audible_workflow(case)[1]]
        result.append({'case_key':case['case_key'],'component':key,'clauses':[{'locators':list(dict.fromkeys(loc)),'matched_relations':[key],'predicate':'role-bound-business-leaf-v6'}]})
    return result


def wer_used(text):
    """A rejected/out-of-scope mention does not adopt a conditional WER metric."""
    if re.search(r'(?:word.level|word.population|word.metric|WER|word.error.rate).{0,140}out of scope',text,re.I) and not re.search(r'(?:calculate|compute)\s+(?:the\s+)?(?:WER|word error rate)',text,re.I):return False
    mentions=[]
    for sentence in sentences(text):
        if not re.search(r'\b(?:WER|word error rate)\b',sentence,re.I):continue
        if re.search(r'(?:WER|word.error.rate).{0,90}(?:out of scope|not used|not calculated|not adopted|unused|excluded)|(?:do not|never|exclude|not).{0,45}(?:calculate|report|use|adopt).{0,25}(?:WER|word error rate)|\bno WER\b|no word.error calculation|source glossary definition',sentence,re.I):continue
        if re.search(r'(?:calculate|compute|report|collect|record|derive)\b.{0,100}\b(?:WER|word error rate)\b|\b(?:WER|word error rate)\b.{0,45}(?:is |are |will be )?(?:reported|calculated|computed|collected|recorded)',sentence,re.I):mentions.append(sentence)
    return bool(mentions)


def business_damage(key,case):
    """Bind an affirmative adopted measurement error to its object and gate.

    Missing tests, unresolved alternatives and mere endpoint names never suffice.
    Predicates bind the adopted action, measured object and acceptance condition.
    """
    if not case['eligible']:return []
    v=case['business_text']
    t,o,a,r=(v[x] for x in ['steps','expected','acceptance','remarks'])
    p=v.get('resolved_preconditions',v.get('local_preconditions',''))
    outcome=o+' '+a
    def has(pattern,text):return bool(re.search(pattern,text,re.I))
    def positive(pattern,text):return bool(list(adopted_relation(pattern,text)))
    hit=False
    if key=='wrong-voice-clock':
        voice=has(r'\b(?:say|speak|utterance|voice|microphone|mic|command)\b',t) and has(r'\b(?:action|execut|execution|latency|operation)\w*\b',t)
        late=positive(r'(?:from|start\s*=|start at|time from).{0,30}(?:submission|command (?:end|completion)|end of (?:the )?(?:spoken )?(?:command|utterance|speech)|(?:mic|microphone|key|button) release|release of (?:the )?(?:mic|microphone) button).{0,120}(?:action|execution|executed|final.state)',t)
        late=late or positive(r'release and submit.{0,40}command.{0,60}measure.{0,40}command execution',t)
        # A semicolon can separate two affirmative actions in the same numbered
        # step. Preserve their operative sequence without crossing a prohibited
        # timing clause or borrowing a different step's start event.
        for step in re.split(r'\b\d{1,2}[.)]\s+',t):
            submitted=False
            for clause in relation_clauses(step):
                if positive(r'release and submit.{0,40}command',clause):submitted=True
                if submitted and positive(r'(?:measure|time).{0,40}(?:time to )?command execution',clause) and not positive(r'(?:from|start.{0,15}at).{0,40}(?:microphone[ -]LED|mic[ -]LED|LED[ -]on)',clause):late=True
        late=late or positive(r'time from command completion|time from command end|COMMAND COMPLETION.{0,60}to.{0,30}EXECUTED ACTION',t)
        late=late or positive(r'speech[ -]end[ -]to[ -](?:action|execution)|end[ -]of[ -]utterance.{0,40}(?:to|->).{0,45}(?:action|execution)',t)
        late=late or positive(r'(?:time|interval|latency) from (?:the )?(?:microphone.button )?press.{0,85}(?:action completion|completion of.{0,25}(?:operation|action))',t)
        alternate=positive(r'(?:mic.LED.on|microphone LED|LED.on).{0,45}\bor\b.{0,30}(?:key.press|button.press)',t)
        numeric=any(positive(r'(?:<\s*=?|<=|within|latency).{0,25}\d+(?:\.\d+)?\s*(?:ms|s\b|seconds?)|\d+(?:\.\d+)?\s*(?:ms|s\b).{0,25}(?:limit|bound)',clause) and has(r'local|cloud|action|execut|command.{0,15}(?:limit|latency)',clause) for clause in relation_clauses(outcome))
        numeric=numeric or positive(r'every command.{0,90}within its documented latency',a)
        numeric=numeric or positive(r'(?:command execution|action latency).{0,40}(?:meets|within).{0,45}(?:applicable|documented).{0,20}category limit',a)
        numeric=numeric or (positive(r'within.{0,30}documented per.category limits',a) and has(r'\d+(?:\.\d+)?\s*(?:ms|s\b)',a))
        sourced=has(r'BFS|\bSPEC\b|specification|documented.{0,35}(?:category|per.category|latency|limits?)',outcome+' '+r)
        sourced=sourced or has(r'\bS\d+\s+sec(?:tion)?s?\.?\s*\d',outcome+' '+r)
        qualified=has(r'(?:supplemental|lab.selected|lab chosen).{0,60}(?:clock|latency|target)|(?:not|never).{0,35}(?:apply|use).{0,50}(?:spec|source).{0,35}(?:limit|bound)|(?:spec|source).{0,35}(?:limit|bound).{0,25}does not govern|no source action pass/fail bound is applied',t+' '+a+' '+r)
        hit=voice and (late or alternate) and numeric and sourced and not qualified
    elif key=='wrong-recognition-metric':
        voice=has(r'utterance|speak|recogniz|recognition',t)
        source=has(r'\bBFS(?=\b|\d)|\bSPEC(?=\b|\d)|specification|\bSOP\b|\bS\d+\s+sec',a+' '+r+' '+p)
        threshold=has(r'(?:95|85|90)\s*(?:%|percent)|(?:95|85)\s*(?:of|/)\s*100|9\s*(?:of|/)\s*10',a)
        joint=positive(r'\brecognized\b.{0,55}\band\b.{0,55}(?:execute\w*|action\s+(?:is\s+)?executed)',a)
        joint=joint or positive(r'definition of.{0,12}correct.{0,100}recogniz.{0,35}\bAND\b.{0,55}action executed',p)
        joint=joint or positive(r'both correct recognition and correct action|correctly recognized and execute',a)
        execution=positive(r'(?:command.execution success|executed correctly|correctly executed commands|commands execute correctly)',a)
        execution=execution or any(positive(r'commands execute the correct operation.{0,40}\(recognition accuracy|correct operation.{0,25}executed.{0,40}\(recognition accuracy',clause) for clause in relation_clauses(a))
        only_actions=positive(r'compute.{0,25}recognition accuracy',t) and positive(r'record.{0,85}(?:actual operation|intended operation.{0,25}(?:actually )?executed)',t) and not positive(r'record.{0,80}(?:recognized text|recognition result|transcript|intent correctness)',t)
        conflated_label=positive(r'compute.{0,25}recognition/execution accuracy',t)
        recognition_bound=positive(r'(?:95|85)\s*(?:%|percent)|recognition accuracy|recognition success rate',a)
        # SOP semantic-operation checks can state joint correctness explicitly;
        # a conjunction alone does not rename its numerator as recognition.
        joint=joint and recognition_bound
        execution=execution and recognition_bound
        chosen=has(r'lab.selected|lab.chosen|supplemental execution target|not.{0,35}(?:the )?(?:recognition|source) (?:criterion|threshold)',a+' '+r)
        # The specification's recognition threshold must not be applied to a
        # correct-command/action-success numerator. Ordinary SOP action gates
        # retain their own meaning, even when they count joint correctness.
        spec_metric=has(r'\bSPEC(?=\b|\d)|specification|\bBFS(?=\b|\d)',a+' '+r)
        misbound_spec=spec_metric and any(positive(r'correct.command success.{0,35}(?:85|95)\s*(?:%|percent)',clause) for clause in relation_clauses(a))
        hit=voice and source and threshold and (joint or execution or only_actions or conflated_label or misbound_spec) and not chosen
    elif key=='wrong-retention-reset':
        learned=has(r'learned|learn.{0,30}(?:IR|code|key)',t) and has(r'non.volatile|stored.{0,35}(?:mapping|code)|codes persist|mapping persists',outcome+' '+r)
        host=has(r'power.cycle (?:the )?(?:TV|host)\b|host power cycle|reboot (?:the )?host\b',t)
        remote=has(r'power.cycle (?:the )?(?:remote|DUT)\b|remote power cycle|remove.{0,30}(?:cells|batteries)|interrupt.{0,30}(?:remote|DUT).{0,20}power',t)
        ambiguous=has(r'(?:reboot|power.cycle|reset).{0,25}(?:TV/remote|host/remote|TV or remote|host or remote)',t)
        sealed=has(r'branch s.{0,100}disconnect.{0,60}charg|sealed.{0,100}disconnect.{0,60}charg',t)
        sealed=sealed and has(r'DUT power interruption|remote power interruption|reset 2|power interruption',t) and not has(r'approved.{0,40}(?:shutdown|service.power.off)',t)
        limited=has(r'host.reset tolerance only|does not prove.{0,50}(?:remote|non.volatile)|not.{0,25}(?:a|an).{0,25}(?:DUT|remote) power interruption|not durability after.{0,20}remote supply loss|remote.{0,35}non.volatile retention.{0,20}(?:untested|unmeasured)|host.{0,45}not.{0,35}remote.storage persistence|remote.storage persistence.{0,30}(?:not|unproven|unmeasured)',a+' '+r)
        hit=learned and (sealed or (host and not remote and not ambiguous)) and not limited
    elif key=='false-electrical-state':
        electrical=has(r'low.power (?:mode|state|entry)|low.power.{0,25}(?:entered|entry)|enters low.power',outcome)
        proxy=False
        for clause in relation_clauses(t+' '+r):
            pointer_state=re.sub(r'\([^)]*pointer[^)]*\)','(pointer-state)',clause,flags=re.I)
            if has(r'low.power state.{0,40}evidenced by.{0,60}pointer',clause) and positive(r'evidenced by',clause):proxy=True
            if has(r'observable consequence.{0,65}pointer.{0,85}used instead',clause) and positive(r'observable consequence.{0,140}used instead',pointer_state):proxy=True
        for variable in re.findall(r'record\s+(t\d+)\s*=',t,re.I):
            definition=re.search(r'record\s+'+re.escape(variable)+r'\s*=([^;]*?)(?=\b\d\.\s|$)',t,re.I)
            if definition and has(r'indicator changing|ceasing to respond|ceases? to respond',definition.group(1)) and has(re.escape(variable)+r'\s*\(\s*low.power entry',outcome):proxy=True
        waived=has(r'current.drop measurement.{0,70}not required',r) and has(r'time|stopwatch',t+' '+p) and has(r'button press|wake|responsive',t+' '+outcome)
        withheld=has(r'(?:do not|cannot|must not|does not).{0,40}(?:infer|prove|establish).{0,60}(?:power|sleep)|power.sleep.{0,50}(?:unmeasured|unproven|withheld)',a+' '+r)
        hit=electrical and (proxy or waived) and not withheld
    if not hit:return []
    loc=[case['locators'][role] for role in ['steps','preconditions','expected','acceptance','remarks'] if case['fields'].get(role)]
    return [{'locators':loc,'matched_relations':[key],
             'predicate':'affirmative-object-clock-state-relation-v6'}]
