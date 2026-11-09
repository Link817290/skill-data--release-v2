"""Generic control-limit helpers; callers supply the approved parameters."""
from math import sqrt,fsum,log1p,expm1
from scipy.stats import f,t
from scipy.special import betainccinv

def pooled_repeatability(standard_deviations,degrees):
    if len(standard_deviations)!=len(degrees) or not degrees or any(d<=0 for d in degrees):raise ValueError("Positive paired degrees are required")
    if any(s<0 for s in standard_deviations):raise ValueError("Negative standard deviation")
    total=fsum(degrees)
    return sqrt(fsum(d*s*s for s,d in zip(standard_deviations,degrees))/total),total

def precision_limit(pool,new_df,baseline_df,alpha):
    if not 0<alpha<1 or min(new_df,baseline_df)<=0:raise ValueError("Invalid control parameters")
    tail=betainccinv(new_df/2,baseline_df/2,alpha)
    return pool*sqrt(baseline_df/new_df*tail/(1-tail))

def simultaneous_t_limit(residual_sd,slope,degrees,points,family_alpha):
    if slope==0 or points<1 or degrees<=0 or not 0<family_alpha<1:raise ValueError("Invalid calibration parameters")
    tail=-expm1(log1p(-family_alpha)/points)/2
    return abs(residual_sd/slope)*t.isf(tail,degrees)
