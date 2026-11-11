"""Independent SI calculation on the original engineering worksheet interface."""
import math

BASE={'C5':100.4,'C6':33,'C7':29,'C8':2100,'C9':39,'C10':32,'C11':7,'F11':1,'C12':1.3,'F12':1.5,'C13':144,'C14':4.5,'E26':.75,'C36':8,'D119':15,'C124':90}
INPUT_FORMULAS={'C13':'=12*12','C26':'=E26-0.1','D26':'=E26-0.05','F26':'=E26+0.05','G26':'=E26+0.1'}
SCENARIOS={
 'baseline':{},'ambient':{'C5':98.5,'C6':34,'C7':28},
 'water_duty':{'C8':2200,'C9':39.5},'water_outlet':{'C10':31.5},
 'air_path':{'C13':150,'C11':7.2,'C12':1.4},'flow_and_motor':{'C8':2000,'C124':85},
 'motor_rating':{'C124':100},'parallel_fans':{'F11':2},
 'humid_boundary':{'C7':31},'candidate_center':{'E26':.80},
}
GROUPS={
 'P01':{'cells':['F16','F19','D20','F21','F22','D23','H24','H25','J28','E32','F33','D34','D35']},
 'P02':{'cells':['C37']+[f'C{r}'for r in range(39,46)]+[f'D{r}'for r in range(46,54)]+[f'F{r}'for r in range(54,78)]},
 'P03':{'cells':[f'{c}27'for c in 'CDEFG']+['G29']+[f'{c}{r}'for c in 'CDEFG'for r in [31,38,81,83]]+['E97','E99','D101']},
 'P08':{'cells':[f'D{r}'for r in range(105,111)]},
 'P09':{'cells':['D100','C114','C115']},
 'P10':{'cells':['D111','D112','D113','D116','D117','D118','D120']},
 'P11':{'cells':['D121','D122','D123']},
 'P12':{'cells':['B125','D125']},
}
DECISION_CELLS=['E96','H96','H102','E103']


def calculate(p,selected_ratio=None,override_selection=False):
 pressure=p['C5'];db=p['C6'];wb=p['C7'];hot=p['C9'];cold=p['C10'];flow=p['C8'];area=p['C13'];n=int(p['C36'])
 def logpressure(T):return 2.0057173-3142.305/T+3142.305/373.16-.0024804*373.16+.0024804*T+8.2*math.log10(373.16/T)
 def sat(t):return 10**logpressure(273.16+t)
 def enthalpy(t,pv):return 1.005*t+.622*(2500.8+1.846*t)*pv/(pressure-pv)
 v={};v['F16']=273.16+wb;v['F19']=logpressure(v['F16']);v['D20']=sat(wb);v['F21']=273.16+db;v['F22']=logpressure(v['F21']);v['D23']=sat(db)
 vapor=sat(wb)-.000662*pressure*(db-wb);v['H24']=vapor/sat(db);v['H25']=(pressure-vapor)*1000/(287.14*(273+db));v['J28']=enthalpy(db,vapor)
 v['G29']=1-cold/(586-.56*(cold-20));v['E32']=273.16+hot;v['F33']=logpressure(v['E32']);v['D34']=sat(hot);v['D35']=enthalpy(hot,sat(hot));v['C37']=(hot-cold)/n
 for j in range(1,8):v[f'C{38+j}']=hot-j*v['C37'];v[f'D{45+j}']=273.16+v[f'C{38+j}']
 v['D53']=273.16+cold
 for j in range(8):
  temperature=hot-(j+1)*v['C37'];row=54+3*j
  v[f'F{row}']=logpressure(273.16+temperature);v[f'F{row+1}']=sat(temperature);v[f'F{row+2}']=enthalpy(temperature,sat(temperature))
 candidates=[];all_candidates=[]
 for col,ratio in zip('CDEFG',[p['E26']-.1,p['E26']-.05,p['E26'],p['E26']+.05,p['E26']+.1]):
  v[f'{col}27']=flow*1000*ratio/v['H25'];v[f'{col}31']=v['J28']+4.1868*(hot-cold)/(v['G29']*ratio);v[f'{col}38']=(v[f'{col}31']-v['J28'])/n
  driving=[v['D35']-v[f'{col}31']]+[v[f'F{56+3*j}']-(v[f'{col}31']-(j+1)*v[f'{col}38'])for j in range(7)]+[v['F77']-v['J28']]
  required=4.1868*(hot-cold)/(3*n)*sum((1 if j in [0,8]else 4 if j%2 else 2)/d for j,d in enumerate(driving)) if min(driving)>0 else None
  available=1.89*ratio**.67;v[f'{col}81']=required;v[f'{col}83']=available
  required_beta=required*flow*1000/(v['G29']*area*p['F12']) if required is not None else None
  available_beta=4188*(flow*1000*ratio/(3600*area))**.65*(flow/area)**.33
  all_candidates.append((ratio,col,required_beta,available_beta))
  if required is not None and available>=required and available_beta>=required_beta:candidates.append((ratio,col,required_beta,available_beta))
 selected=min(candidates)if candidates else None
 if override_selection:selected=next((c for c in all_candidates if isinstance(selected_ratio,(int,float))and abs(c[0]-selected_ratio)<1e-8),None)
 v['E96']=selected[0]if selected else None;v['H96']='满足'if selected else'不满足'
 v['D100']=flow/area;v['C114']=-.0007*v['D100']**2+.0652*v['D100']+.9824;v['C115']=.0003*v['D100']**2-.0922*v['D100']+2.0273
 v['D106']=area*.9;v['D107']=area*.98;v['D108']=area*.9;v['D109']=(p['C11']**2-p['C12']**2)*3.1416/4*p['F11'];v['D110']=v['H25']+vapor*1000/(461.5*(273.15+db))
 dependent=['E97','E99','D101','D105','D111','D112','D113','D116','D117','D118','D120','D121','D122','D123']
 if selected:
  ratio,col,required_beta,available_beta=selected;air=v[f'{col}27']/3600
  v['E97']=required_beta;v['E99']=flow*1000*ratio/3600/area;v['D101']=available_beta;v['D105']=air/5
  dp=lambda velocity:v['D110']*velocity**2/2
  v['D111']=.55*dp(5);v['D112']=.5*dp(air/area);v['D113']=.000124*dp(air/(.984*area))
  v['D116']=v['H25']*9.81*v['C114']*(air/v['D108'])**v['C115'];v['D117']=.6*((1-.9)**2*1.3+.5)/.9**2*dp(air/v['D106']);v['D118']=((1-.98)**2*2+.5)/.98**2*dp(air/v['D107'])
  v['D120']=sum(v[c]for c in ['D111','D112','D113','D116','D117','D118'])+p['D119'];v['D121']=dp(air/v['D109']);v['D122']=v['D120']+v['D121'];v['D123']=air/p['F11']*v['D122']/(1000*.7)
 else:v.update({c:None for c in dependent})
 v['H102']='满足'if selected and v['E97']is not None and v['D101']>=v['E97']else'不满足';v['E103']='完全达到'if v['H96']=='满足'and v['H102']=='满足'else'达不到';v['B125']=p['C124']*p['F11']/flow;v['D125']='满足'if v['B125']<=.045 else'不满足'
 return v
