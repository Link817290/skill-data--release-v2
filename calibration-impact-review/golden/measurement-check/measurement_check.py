"""Offline, reproducible review of mass and optical measurement-control records."""
import argparse,csv,json,math,os,sys
from pathlib import Path
import numpy as np
from scipy.stats import f,t
from scipy.special import betainccinv

MASS_COLUMNS=['record_id','decimal_year','balance_id','check_standard_id','check_value_ug','residual_sd_ug','design_id']
OPTICAL_COLUMNS=['record_id','control_day','reference_position','reference_width_um','response_um']
EXCEPTION_COLUMNS=['system','record_id','scope','control_day','measurement','observed','unit','lower_limit','upper_limit','action']

def finite(value,name):
    number=float(value)
    if not math.isfinite(number):raise ValueError(name+' must be finite')
    return number

def read_csv(path,columns):
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream)
        if not reader.fieldnames or len(reader.fieldnames)!=len(set(reader.fieldnames)) or not set(columns)<=set(reader.fieldnames):raise ValueError('Missing or duplicate input column: '+str(path))
        rows=list(reader)
    ids=[r['record_id'].strip() for r in rows]
    if not rows or any(not x for x in ids) or len(ids)!=len(set(ids)):raise ValueError('Record IDs must be present and unique within each input')
    for row,rid in zip(rows,ids):row['record_id']=rid
    return sorted(rows,key=lambda r:r['record_id'])

def calculate(mass_path,optical_path,config_path):
    cfg=json.loads(Path(config_path).read_text(encoding='utf-8-sig'));m=cfg['mass'];o=cfg['optical']
    if o.get('family_method')!='sidak':raise ValueError('Unsupported optical family method; expected sidak')
    cutoff=finite(m['baseline_cutoff_year'],'baseline cutoff');df=finite(m['residual_df_each'],'residual degrees');alpha=finite(m['precision_alpha'],'precision alpha');k=finite(m['bias_sd_multiplier'],'bias multiplier')
    a=finite(o['intercept_um'],'intercept');b=finite(o['slope'],'slope');s=finite(o['fit_residual_sd_um'],'fit residual SD');nu=finite(o['fit_df'],'fit degrees');group=finite(o['controls_per_day'],'controls per day');family=finite(o['family_alpha'],'family alpha')
    if df<=0 or k<=0 or not 0<alpha<1 or b==0 or s<0 or nu<=0 or group<1 or not group.is_integer() or not 0<family<1:raise ValueError('Invalid control parameters')
    mass=read_csv(mass_path,MASS_COLUMNS);optical=read_csv(optical_path,OPTICAL_COLUMNS)
    identities={tuple(r[k].strip() for k in ['balance_id','check_standard_id','design_id']) for r in mass}
    if len(identities)!=1 or any(not item for identity in identities for item in identity):raise ValueError('Mass records must describe one nonempty balance/check-standard/design combination')
    for r in mass:
        for col in ['decimal_year','check_value_ug','residual_sd_ug']:r[col]=finite(r[col],col)
        if r['residual_sd_ug']<0:raise ValueError('Residual SD cannot be negative')
    for r in optical:
        day=finite(r['control_day'],'control day')
        if not day.is_integer() or day<1:raise ValueError('Control day must be a positive integer')
        r['control_day']=int(day)
        for col in ['reference_width_um','response_um']:r[col]=finite(r[col],col)
        if r['reference_position'] not in ['L','M','U']:raise ValueError('Reference position must be L, M or U')
    for day in {r['control_day'] for r in optical}:
        rows=[r for r in optical if r['control_day']==day]
        if len(rows)!=int(group) or len({r['reference_position'] for r in rows})!=int(group):raise ValueError('Incomplete or duplicated daily reference group')
    baseline=[r for r in mass if r['decimal_year']<cutoff];monitor=[r for r in mass if r['decimal_year']>=cutoff]
    if len(baseline)<2 or len(monitor)<2:raise ValueError('At least two baseline and two monitoring records are required')
    x=np.array([r['check_value_ug'] for r in baseline]);res=np.array([r['residual_sd_ug'] for r in baseline])
    mean=float(np.mean(x));sd=float(np.std(x,ddof=1));pool=float(np.sqrt(np.mean(res**2)));degrees=len(baseline)*df
    low=mean-k*sd;high=mean+k*sd
    beta_tail=float(betainccinv(df/2,degrees/2,alpha));upper=pool*math.sqrt(degrees/df*beta_tail/(1-beta_tail))
    one_sided_tail=-math.expm1(math.log1p(-family)/group)/2
    critical=float(t.isf(one_sided_tail,nu));width_limit=abs(s/b)*critical
    mass_out=[];optical_out=[];exceptions=[]
    for r in mass:
        base=r['decimal_year']<cutoff;bias=not low<=r['check_value_ug']<=high;precision=r['residual_sd_ug']>upper
        action=('investigate_baseline' if base else 'repeat_run') if bias or precision else ('retain_baseline' if base else 'within_limits')
        row=dict(record_id=r['record_id'],decimal_year=r['decimal_year'],phase='baseline' if base else 'monitoring',check_value_ug=r['check_value_ug'],residual_sd_ug=r['residual_sd_ug'],bias_lower_ug=low,bias_upper_ug=high,precision_upper_ug=upper,bias_failure=bias,precision_failure=precision,action=action);mass_out.append(row)
        for failed,metric,observed,lower,cap in [(bias,'check_value',r['check_value_ug'],low,high),(precision,'residual_sd',r['residual_sd_ug'],'',upper)]:
            if failed:exceptions.append(dict(system='mass',record_id=r['record_id'],scope=row['phase'],control_day='',measurement=metric,observed=observed,unit='ug',lower_limit=lower,upper_limit=cap,action=action))
    for r in optical:
        corrected=(r['response_um']-a)/b;error=corrected-r['reference_width_um'];fail=abs(error)>width_limit
        row=dict(record_id=r['record_id'],control_day=r['control_day'],reference_position=r['reference_position'],reference_width_um=r['reference_width_um'],response_um=r['response_um'],corrected_width_um=corrected,control_error_um=error,lower_limit_um=-width_limit,upper_limit_um=width_limit,failure=fail);optical_out.append(row)
        if fail:exceptions.append(dict(system='optical',record_id=r['record_id'],scope='control_day',control_day=r['control_day'],measurement='control_error',observed=error,unit='um',lower_limit=-width_limit,upper_limit=width_limit,action='repeat_linked_day'))
    days=[]
    for day in sorted({r['control_day'] for r in optical_out}):
        rows=[r for r in optical_out if r['control_day']==day];failed=sum(r['failure'] for r in rows)
        days.append(dict(control_day=day,controls=len(rows),failed_controls=failed,action='repeat_linked_day' if failed else 'within_limits'))
    monitor_values=np.array([r['check_value_ug'] for r in monitor]);monitor_mean=float(np.mean(monitor_values))
    result=dict(summary=dict(mass_records=len(mass),baseline_records=len(baseline),monitoring_records=len(monitor),baseline_exceptions=sum(r['phase']=='baseline' and (r['bias_failure'] or r['precision_failure']) for r in mass_out),monitoring_exceptions=sum(r['phase']=='monitoring' and (r['bias_failure'] or r['precision_failure']) for r in mass_out),optical_controls=len(optical_out),optical_failed_controls=sum(r['failure'] for r in optical_out),optical_failed_days=sum(r['failed_controls']>0 for r in days)),baseline=dict(count=len(baseline),degrees=degrees,mean_ug=mean,sample_sd_ug=sd,pooled_repeatability_ug=pool,bias_lower_ug=low,bias_upper_ug=high,precision_upper_ug=upper,legacy_count=m['legacy_baseline_count'],legacy_degrees=m['legacy_baseline_df']),optical_limits=dict(simultaneous_t=critical,absolute_limit_um=width_limit),mass_results=mass_out,optical_results=optical_out,daily_results=days,trend=dict(monitoring_mean_ug=monitor_mean,monitoring_sample_sd_ug=float(np.std(monitor_values,ddof=1)),mean_shift_ug=monitor_mean-mean,above_baseline_mean=sum(v>mean for v in monitor_values),monitoring_records=len(monitor)),scope=dict(affected_customer_work_count=None,completed_remeasurement_confirmed=False,product_conformity='not_determined'))
    result['trend']['above_baseline_mean']=int(result['trend']['above_baseline_mean'])
    return result,sorted(exceptions,key=lambda r:(r['system'],r['record_id'],r['measurement']))

def run(args):
    result,exceptions=calculate(args.mass,args.optical,args.config)
    args.output.mkdir(parents=True,exist_ok=True)
    json_tmp=args.output/'review-results.json.tmp';csv_tmp=args.output/'exceptions.csv.tmp'
    json_tmp.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    with csv_tmp.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=EXCEPTION_COLUMNS);writer.writeheader();writer.writerows(exceptions)
    os.replace(json_tmp,args.output/'review-results.json');os.replace(csv_tmp,args.output/'exceptions.csv')
    print(json.dumps(result['summary'],allow_nan=False))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['mass','optical','config','output']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    try:run(args)
    except (ValueError,KeyError,TypeError,OSError) as exc:print('Input review failed: '+str(exc),file=sys.stderr);return 2
    return 0
if __name__=='__main__':raise SystemExit(main())
