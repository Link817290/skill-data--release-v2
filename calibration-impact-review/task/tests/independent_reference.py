"""Independent CSV reconstruction using stdlib statistics and inverse survival tails."""
import csv,json,math
from pathlib import Path
from statistics import mean,stdev
from scipy.stats import f,t
from scipy.optimize import brentq

def reconstruct(mass_path,optical_path,config_path):
    with Path(mass_path).open(encoding='utf-8-sig',newline='') as stream:mass=list(csv.DictReader(stream))
    with Path(optical_path).open(encoding='utf-8-sig',newline='') as stream:optical=list(csv.DictReader(stream))
    cfg=json.loads(Path(config_path).read_text(encoding='utf-8-sig'));m=cfg['mass'];o=cfg['optical']
    baseline=[r for r in mass if float(r['decimal_year'])<m['baseline_cutoff_year']]
    monitor=[r for r in mass if float(r['decimal_year'])>=m['baseline_cutoff_year']]
    values=[float(r['check_value_ug']) for r in baseline];center=mean(values);sigma=stdev(values)
    degrees=len(baseline)*m['residual_df_each']
    pooled=math.sqrt(math.fsum(m['residual_df_each']*float(r['residual_sd_ug'])**2 for r in baseline)/degrees)
    lower=center-m['bias_sd_multiplier']*sigma;upper=center+m['bias_sd_multiplier']*sigma
    alpha=m['precision_alpha'];upper_bracket=1.0
    while f.sf(upper_bracket,m['residual_df_each'],degrees)>alpha:upper_bracket*=2
    quantile=brentq(lambda value:f.logsf(value,m['residual_df_each'],degrees)-math.log(alpha),0,upper_bracket,xtol=1e-13)
    precision=pooled*math.sqrt(quantile)
    tail=-math.expm1(math.log1p(-o['family_alpha'])/o['controls_per_day'])/2
    critical=float(t.isf(tail,o['fit_df']));limit=abs(o['fit_residual_sd_um']/o['slope'])*critical
    mr=[];wr=[];exceptions=[]
    for r in mass:
        value=float(r['check_value_ug']);sd=float(r['residual_sd_ug']);year=float(r['decimal_year']);phase='baseline' if year<m['baseline_cutoff_year'] else 'monitoring'
        bias=value<lower or value>upper;repeat=sd>precision
        action=('investigate_baseline' if phase=='baseline' else 'repeat_run') if bias or repeat else ('retain_baseline' if phase=='baseline' else 'within_limits')
        mr.append(dict(record_id=r['record_id'],decimal_year=year,phase=phase,check_value_ug=value,residual_sd_ug=sd,bias_lower_ug=lower,bias_upper_ug=upper,precision_upper_ug=precision,bias_failure=bias,precision_failure=repeat,action=action))
        for flag,measurement,x,lo,hi in [(bias,'check_value',value,lower,upper),(repeat,'residual_sd',sd,'',precision)]:
            if flag:exceptions.append(dict(system='mass',record_id=r['record_id'],scope=phase,control_day='',measurement=measurement,observed=x,unit='ug',lower_limit=lo,upper_limit=hi,action=action))
    for r in optical:
        day=int(r['control_day']);known=float(r['reference_width_um']);response=float(r['response_um']);corrected=(response-o['intercept_um'])/o['slope'];error=corrected-known;failed=abs(error)>limit
        wr.append(dict(record_id=r['record_id'],control_day=day,reference_position=r['reference_position'],reference_width_um=known,response_um=response,corrected_width_um=corrected,control_error_um=error,lower_limit_um=-limit,upper_limit_um=limit,failure=failed))
        if failed:exceptions.append(dict(system='optical',record_id=r['record_id'],scope='control_day',control_day=day,measurement='control_error',observed=error,unit='um',lower_limit=-limit,upper_limit=limit,action='repeat_linked_day'))
    days=[]
    for day in sorted({r['control_day'] for r in wr}):
        rows=[r for r in wr if r['control_day']==day];bad=sum(r['failure'] for r in rows)
        days.append(dict(control_day=day,controls=len(rows),failed_controls=bad,action='repeat_linked_day' if bad else 'within_limits'))
    later=[float(r['check_value_ug']) for r in monitor];avg=mean(later)
    result=dict(summary=dict(mass_records=len(mass),baseline_records=len(baseline),monitoring_records=len(monitor),baseline_exceptions=sum(r['phase']=='baseline' and (r['bias_failure'] or r['precision_failure']) for r in mr),monitoring_exceptions=sum(r['phase']=='monitoring' and (r['bias_failure'] or r['precision_failure']) for r in mr),optical_controls=len(wr),optical_failed_controls=sum(r['failure'] for r in wr),optical_failed_days=sum(r['failed_controls']>0 for r in days)),baseline=dict(count=len(baseline),degrees=degrees,mean_ug=center,sample_sd_ug=sigma,pooled_repeatability_ug=pooled,bias_lower_ug=lower,bias_upper_ug=upper,precision_upper_ug=precision,legacy_count=m['legacy_baseline_count'],legacy_degrees=m['legacy_baseline_df']),optical_limits=dict(simultaneous_t=critical,absolute_limit_um=limit),mass_results=mr,optical_results=wr,daily_results=days,trend=dict(monitoring_mean_ug=avg,monitoring_sample_sd_ug=stdev(later),mean_shift_ug=avg-center,above_baseline_mean=sum(x>center for x in later),monitoring_records=len(later)),scope=dict(affected_customer_work_count=None,completed_remeasurement_confirmed=False,product_conformity='not_determined'))
    return result,exceptions
