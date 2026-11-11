"""Common business-credit utility and independent-harm settlement."""
from decimal import Decimal

def settle(positive,damage,*,power,retention):
    credit=Decimal(str(positive));debit=Decimal(str(damage))
    exponent=int(power);rho=Decimal(str(retention))
    if exponent<1 or not Decimal(0)<=rho<=Decimal(1):raise ValueError("Invalid common settlement parameters")
    utility=credit**exponent
    raw=utility-debit
    reward=max(rho*utility,raw)
    return {"positive_utility":float(utility),"raw_score":float(raw),"reward":float(reward)}
